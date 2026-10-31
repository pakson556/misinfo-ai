"""Dataset loaders with corrected, documented label mappings.

Every loader returns a DataFrame with columns:
  text      the content
  label     1 = misinformation / false, 0 = credible / true
  dataset   dataset name
  group     unit that must never be split across train/test (event, story, claim)
  split     the dataset's official split if it has one, else ""

Fixes vs v1 (see ../docs/V1_AUDIT.md):
  * Twitter15/16: "non-rumor" was labelled misinformation. Now: false -> 1,
    true / non-rumor -> 0, unverified -> dropped (unknown truth value).
  * PHEME: "rumour" was treated as "false". A rumour is an unverified claim;
    we now use the veracity annotation (misinformation / true) and drop unverified.
  * CoAID: label comes from the file name (Fake/Real). v1 looked for a missing
    "label" column and so labelled every row as real.
  * FakeHealth: label from 0-5 review stars (< 3 -> 1), joined on news_id.
    v1 only accepted ratings "0"/"1", treated 1 star as real, and joined by row order.
  * LIAR: official train/valid/test splits are kept; "half-true" is dropped
    as genuinely ambiguous rather than forced into a class.
  * Excluded entirely: datasets whose labels were produced by keyword rules
    (Brazil anti-vax), and FakeCovid, whose texts are fact-check articles
    *about* false claims (labelling a debunk as misinformation teaches the opposite).
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path

import pandas as pd

COLUMNS = ["text", "label", "dataset", "group", "split"]


def _frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows, columns=COLUMNS)
    df["text"] = df["text"].astype(str).str.strip()
    return df[df["text"].str.len() >= 15].reset_index(drop=True)


# ----------------------------------------------------------------------------- LIAR

LIAR_FALSE = {"pants-fire", "false", "barely-true"}
LIAR_TRUE = {"true", "mostly-true"}


def load_liar(raw: Path) -> pd.DataFrame:
    d = next((p for p in (raw / "liar", raw / "lair", raw / "LIAR") if p.exists()), None)
    if d is None:
        return _frame([])
    rows = []
    for split in ("train", "valid", "test"):
        f = d / f"{split}.tsv"
        if not f.exists():
            continue
        with open(f, encoding="utf-8") as fh:
            for parts in csv.reader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
                if len(parts) < 3:
                    continue
                lab = parts[1].strip().lower()
                if lab in LIAR_FALSE:
                    y = 1
                elif lab in LIAR_TRUE:
                    y = 0
                else:
                    continue  # half-true: ambiguous
                rows.append(
                    {
                        "text": parts[2],
                        "label": y,
                        "dataset": "liar",
                        "group": f"liar:{parts[0]}",
                        "split": {"valid": "val"}.get(split, split),
                    }
                )
    return _frame(rows)


# ----------------------------------------------------------------------------- Twitter15/16


def load_twitter1516(raw: Path) -> pd.DataFrame:
    rows, seen = [], set()
    for name in ("twitter15", "twitter16"):
        d = raw / name
        if not d.exists():
            continue
        labels = {}
        for line in (d / "label.txt").read_text().splitlines():
            if ":" in line:
                lab, eid = line.split(":", 1)
                labels[eid.strip()] = re.sub(r"[^a-z]", "", lab.lower())
        for line in (d / "source_tweets.txt").read_text(encoding="utf-8", errors="ignore").splitlines():
            if "\t" not in line:
                continue
            tid, text = line.split("\t", 1)
            tid = tid.strip()
            lab = labels.get(tid)
            if lab == "false":
                y = 1
            elif lab in {"true", "nonrumor"}:
                y = 0
            else:
                continue  # unverified / missing
            if tid in seen:  # Twitter15 and 16 overlap; keep one copy
                continue
            seen.add(tid)
            rows.append({"text": text, "label": y, "dataset": "twitter1516", "group": f"tw:{tid}", "split": ""})
    return _frame(rows)


# ----------------------------------------------------------------------------- PHEME


def _tweet_text(path: Path) -> str:
    try:
        d = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except json.JSONDecodeError:
        return ""
    return d.get("full_text") or d.get("text") or ""


def load_pheme(raw: Path, include_non_rumours: bool = True) -> pd.DataFrame:
    d = raw / "pheme"
    if not d.exists():
        return _frame([])
    rows = []
    for event in sorted(p for p in d.iterdir() if p.is_dir() and not p.name.startswith(".")):
        ev = event.name.replace("-all-rnr-threads", "")
        for kind in ("rumours", "non-rumours"):
            kdir = event / kind
            if not kdir.exists() or (kind == "non-rumours" and not include_non_rumours):
                continue
            for thread in kdir.iterdir():
                src = next((thread / "source-tweet").glob("*.json"), None) if (thread / "source-tweet").exists() else None
                if src is None:
                    continue
                if kind == "non-rumours":
                    y = 0
                else:
                    ann = thread / "annotation.json"
                    if not ann.exists():
                        continue
                    a = json.loads(ann.read_text())
                    if str(a.get("misinformation")) == "1":
                        y = 1
                    elif str(a.get("true")) == "1":
                        y = 0
                    else:
                        continue  # unverified rumour
                # group by event: all tweets about one breaking event share topic words
                rows.append({"text": _tweet_text(src), "label": y, "dataset": "pheme", "group": f"pheme:{ev}", "split": ""})
    # The 5-event PHEME release has rumour/non-rumour folders but no veracity
    # annotation.json files. Then only non-rumours (label 0) survive, and the model
    # would learn "PHEME-style tweet = real". Skip the dataset instead.
    if rows and not any(r["label"] == 1 for r in rows):
        print("pheme: no veracity annotations found (need the 9-event 'all-rnr-annotated-threads' release); skipped")
        return _frame([])
    return _frame(rows)


# ----------------------------------------------------------------------------- FakeNewsNet


def load_fakenewsnet(raw: Path) -> pd.DataFrame:
    d = raw / "fakenewsnet"
    rows = []
    for fname, y in (
        ("politifact_fake.csv", 1),
        ("politifact_real.csv", 0),
        ("gossipcop_fake.csv", 1),
        ("gossipcop_real.csv", 0),
    ):
        f = d / fname
        if not f.exists():
            continue
        df = pd.read_csv(f)
        sub = fname.split("_")[0]
        col = next((c for c in ("text", "content", "title") if c in df.columns), None)
        if col is None:
            continue
        for i, r in df.iterrows():
            rows.append(
                {
                    "text": str(r[col]),
                    "label": y,
                    "dataset": f"fnn_{sub}",
                    "group": f"fnn:{r.get('id', f'{sub}{y}_{i}')}",
                    "split": "",
                }
            )
    return _frame(rows)


# ----------------------------------------------------------------------------- CoAID


def load_coaid(raw: Path) -> pd.DataFrame:
    d = next((p for p in (raw / "CoAID-master", raw / "CoAID", raw / "coaid") if p.exists()), None)
    if d is None:
        return _frame([])
    rows = []
    for f in d.rglob("*.csv"):
        name = f.name
        if "tweets" in name.lower() or "replies" in name.lower():
            continue
        if "Fake" in name:
            y = 1
        elif "Real" in name:
            y = 0
        else:
            continue
        df = pd.read_csv(f)
        for i, r in df.iterrows():
            title = str(r.get("title", "") or "").strip()
            if title.lower() in {"", "nan"}:
                continue
            rows.append(
                {"text": title, "label": y, "dataset": "coaid", "group": f"coaid:{r.get('news_url', name + str(i))}", "split": ""}
            )
    return _frame(rows)


# ----------------------------------------------------------------------------- FakeHealth


def load_fakehealth(raw: Path) -> pd.DataFrame:
    d = raw / "FakeHealth"
    rows = []
    for subset in ("HealthStory", "HealthRelease"):
        rf = d / "reviews" / f"{subset}.json"
        cdir = d / "content" / subset
        if not rf.exists() or not cdir.exists():
            continue
        for rev in json.loads(rf.read_text()):
            nid, rating = rev.get("news_id"), rev.get("rating")
            if nid is None or rating is None:
                continue
            f = cdir / f"{nid}.json"
            if not f.exists():
                continue
            c = json.loads(f.read_text(encoding="utf-8", errors="ignore"))
            body = f"{c.get('title', '')}\n\n{c.get('text', '')}".strip()
            rows.append(
                {"text": body[:6000], "label": int(float(rating) < 3), "dataset": "fakehealth", "group": f"fh:{nid}", "split": ""}
            )
    return _frame(rows)


LOADERS = {
    "liar": load_liar,
    "twitter1516": load_twitter1516,
    "pheme": load_pheme,
    "fakenewsnet": load_fakenewsnet,
    "coaid": load_coaid,
    "fakehealth": load_fakehealth,
}
