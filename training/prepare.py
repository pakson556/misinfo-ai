"""Build clean, leak-free train/val/calib/test splits.

    python prepare.py --raw /path/to/raw --out data

Steps
  1. Load each dataset with corrected labels (loaders.py).
  2. Normalise text; drop exact and near-duplicate texts across *all* datasets,
     and drop texts that appear with conflicting labels.
  3. Strip giveaway tokens (URLs, @handles, "RT", source-tagged prefixes such as
     "FACT CHECK:") so models can't cheat on formatting artefacts.
  4. Group-aware split: every group (event / story / claim) lands in exactly one
     of train / val / calib / test. LIAR keeps its official split.
  5. Write parquet files + a stats report.

`calib` is a separate slice used only for temperature scaling, so calibration and
threshold choice are never fitted on the same data (a v1 problem).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from loaders import LOADERS

URL = re.compile(r"https?://\S+|www\.\S+")
HANDLE = re.compile(r"@\w+")
RT = re.compile(r"^\s*RT\b[:\s]*", re.I)
# Prefixes that leak the label (fact-check headlines, wire tags)
LEAKY_PREFIX = re.compile(r"^\s*(fact[\s-]?check|false|true|fake|hoax|misleading|debunked|verdict|claim)\s*[:\-–|]\s*", re.I)
SPACE = re.compile(r"\s+")


def clean(text: str) -> str:
    t = unicodedata.normalize("NFKC", str(text))
    t = URL.sub(" ", t)
    t = HANDLE.sub("@user", t)
    t = RT.sub("", t)
    t = LEAKY_PREFIX.sub("", t)
    return SPACE.sub(" ", t).strip()


def norm_key(text: str) -> str:
    t = re.sub(r"[^a-z0-9 ]", "", text.lower())
    return SPACE.sub(" ", t).strip()


def minhash_signature(text: str, n_perm: int = 64, shingle: int = 5) -> tuple[int, ...]:
    toks = text.split()
    grams = {" ".join(toks[i : i + shingle]) for i in range(max(1, len(toks) - shingle + 1))}
    sig = []
    for seed in range(n_perm):
        sig.append(min(int(hashlib.blake2b(f"{seed}:{g}".encode(), digest_size=8).hexdigest(), 16) for g in grams))
    return tuple(sig)


def near_dup_groups(keys: list[str], bands: int = 16, rows: int = 4) -> list[int]:
    """LSH over MinHash. Returns a cluster id per text (texts with ~>=0.8 Jaccard share an id)."""
    parent = list(range(len(keys)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    buckets: dict[tuple, int] = {}
    for i, k in enumerate(keys):
        if len(k.split()) < 8:  # too short for reliable near-dup detection; exact match handles these
            continue
        sig = minhash_signature(k, n_perm=bands * rows)
        for b in range(bands):
            key = (b, sig[b * rows : (b + 1) * rows])
            if key in buckets:
                parent[find(i)] = find(buckets[key])
            else:
                buckets[key] = i
    return [find(i) for i in range(len(keys))]


def dedupe(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    stats = {"before": len(df)}
    df = df.copy()
    df["key"] = df["text"].map(norm_key)
    df = df[df["key"].str.len() >= 15]

    # Conflicting labels for the same text are noise: drop them all.
    conflict = df.groupby("key")["label"].nunique()
    bad = set(conflict[conflict > 1].index)
    stats["conflicting_label_texts"] = len(bad)
    df = df[~df["key"].isin(bad)]

    exact_before = len(df)
    df = df.drop_duplicates("key")
    stats["exact_duplicates_removed"] = exact_before - len(df)

    clusters = near_dup_groups(df["key"].tolist())
    df["cluster"] = clusters
    # Near-duplicates must stay together in one split; we keep them but merge their groups.
    df["group"] = df.groupby("cluster")["group"].transform("first")
    stats["near_duplicate_clusters_merged"] = int((df["cluster"].value_counts() > 1).sum())
    stats["after"] = len(df)
    return df.drop(columns=["key", "cluster"]).reset_index(drop=True), stats


def group_split(df: pd.DataFrame, seed: int, fracs=(0.7, 0.1, 0.05, 0.15)) -> pd.Series:
    """
    Assign train/val/calib/test so that every group lands in exactly ONE split.

    Groups can span datasets (a near-duplicate found in two datasets) or span a
    dataset's official splits (the same LIAR claim in train.tsv and test.tsv).
    So the split is decided per group, once:
      1. Groups touching an official split take the most held-out one
         (test > val > train), so a test claim never has a twin in training.
         A third of the official-val groups become calib.
      2. Remaining groups are shuffled and cut by `fracs`, per dataset, so each
         dataset is represented in every split.
    """
    rng = np.random.default_rng(seed)
    names = ["train", "val", "calib", "test"]
    rank = {"train": 0, "val": 1, "test": 2}
    assign: dict = {}

    official = df[df["split"].isin(rank)]
    if len(official):
        best = official.groupby("group")["split"].agg(lambda s: max(s, key=rank.get))
        assign.update(best.to_dict())
        val_groups = np.array(sorted(g for g, sp in assign.items() if sp == "val"), dtype=object)
        rng.shuffle(val_groups)
        for g in val_groups[: len(val_groups) // 3]:
            assign[g] = "calib"

    for _, part in df.groupby("dataset"):
        groups = np.array([g for g in part["group"].unique() if g not in assign], dtype=object)
        if not len(groups):
            continue
        rng.shuffle(groups)
        cuts = np.cumsum([int(round(f * len(groups))) for f in fracs])[:-1]
        for name, chunk in zip(names, np.split(groups, cuts), strict=True):
            for g in chunk:
                assign[g] = name
    return df["group"].map(assign)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", type=Path, required=True, help="folder containing liar/, twitter15/, pheme/, ...")
    ap.add_argument("--out", type=Path, default=Path("data"))
    ap.add_argument("--datasets", default=",".join(LOADERS), help="comma-separated subset")
    ap.add_argument("--max-per-dataset", type=int, default=40_000, help="cap so one dataset can't dominate")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    frames, per = [], {}
    for name in args.datasets.split(","):
        df = LOADERS[name](args.raw)
        per[name] = {"rows": len(df), "positive_rate": round(float(df["label"].mean()), 3) if len(df) else None}
        print(f"{name:12s} {len(df):7d} rows  pos={per[name]['positive_rate']}")
        if len(df):
            frames.append(df)
    if not frames:
        raise SystemExit(f"No data found under {args.raw}. See training/README.md for the expected layout.")

    df = pd.concat(frames, ignore_index=True)
    df["text"] = df["text"].map(clean)
    df, dstats = dedupe(df)

    capped = []
    for _, part in df.groupby("dataset"):
        if len(part) > args.max_per_dataset:
            keep = part["group"].drop_duplicates().sample(frac=1, random_state=args.seed)
            sizes = part.groupby("group").size()
            cum = sizes.loc[keep].cumsum()
            part = part[part["group"].isin(cum[cum <= args.max_per_dataset].index)]
        capped.append(part)
    df = pd.concat(capped, ignore_index=True)

    df["split"] = group_split(df, args.seed)
    leak = df.groupby("group")["split"].nunique().max()
    assert leak == 1, "a group appears in more than one split"

    args.out.mkdir(parents=True, exist_ok=True)
    for name, part in df.groupby("split"):
        part.reset_index(drop=True).to_parquet(args.out / f"{name}.parquet")

    report = {
        "loaded": per,
        "dedup": dstats,
        "final_rows": len(df),
        "by_split": df["split"].value_counts().to_dict(),
        "by_dataset_split": df.groupby(["dataset", "split"]).size().unstack(fill_value=0).to_dict(orient="index"),
        "positive_rate_by_dataset": df.groupby("dataset")["label"].mean().round(3).to_dict(),
    }
    (args.out / "stats.json").write_text(json.dumps(report, indent=2))
    print(json.dumps({k: report[k] for k in ("dedup", "final_rows", "by_split")}, indent=2))


if __name__ == "__main__":
    main()
