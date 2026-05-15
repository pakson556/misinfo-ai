#!/usr/bin/env python3
"""
Unified data preparation script.
All data now under ml/data/

✅ This version:
- Keeps RumourEval REMOVED (no stance labels mixed into binary misinfo)
- Adds simple caps (downsampling) for huge datasets (DeathHoaxes, MHMisinfo, Brazil antivax)
- Does NOT create any new files (only overwrites the same existing outputs in processed/ and splits/)
- ✅ FIXES Twitter15/16 binary mapping:
    true -> 0 (non-misinfo)
    everything else (false/unverified/non-rumor/unknown) -> 1 (misinfo)
"""

import json
import csv
import re
import random
from pathlib import Path
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Tuple


# ============================================================================
# Configuration
#===========================================================================

BASE_DIR = Path(__file__).parent.parent  # Points to ml/
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
SPLITS_DIR = PROCESSED_DIR / "splits_unified_all"
MODELS_DIR = DATA_DIR / "models"

# Ensure all directories exist
for d in [RAW_DIR, PROCESSED_DIR, SPLITS_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

print(f"📁 Data directory: {DATA_DIR}")
print(f"📁 Raw data: {RAW_DIR}")
print(f"📁 Processed data: {PROCESSED_DIR}")
print(f"📁 Models will be saved to: {MODELS_DIR}")

# Column names
TEXT_COL = "source_text"
LABEL_COL = "label_binary"
NUM_COLS = [
    "root_outdeg", "num_nodes", "num_edges", "tree_depth",
    "max_breadth", "leaf_nodes", "leaf_ratio", "avg_outdeg",
    "branching_factor"
]

# ----------------------------------------------------------------------------
# Simple capping helper (prevents huge datasets dominating training)
# ----------------------------------------------------------------------------
_RNG = random.Random(42)

def _cap(rows: List[Dict], n: Optional[int]) -> List[Dict]:
    """Shuffle + cap rows to n (deterministic)."""
    if n is None or len(rows) <= n:
        return rows
    _RNG.shuffle(rows)
    return rows[:n]


# ============================================================================
# Twitter15/16 Preparation
# ============================================================================

def parse_tree_edges(tree_path: Path, event_id: str) -> List[Tuple[str, str]]:
    """
    Parse Twitter15/16 tree file format.

    Format: ['ROOT','ROOT','0.0']->['user_id','tweet_id','timestamp']
    Returns list of (parent_id, child_id) edges.
    """
    edges: List[Tuple[str, str]] = []
    if not tree_path.exists():
        return edges

    for line in tree_path.read_text().splitlines():
        line = line.strip()
        if not line or "->" not in line:
            continue

        parts = re.findall(r"\[(.*?)\]", line)
        if len(parts) != 2:
            continue

        left, right = parts
        left_items = [x.strip().strip("'") for x in left.split(",")]
        right_items = [x.strip().strip("'") for x in right.split(",")]

        if len(left_items) >= 2 and len(right_items) >= 2:
            parent = left_items[1] if left_items[1] != "ROOT" else event_id
            child = right_items[1]
            if parent != child:
                edges.append((parent, child))

    return edges


def compute_diffusion_features(edges: List[Tuple[str, str]], root_id: str) -> Dict[str, float]:
    """
    Compute diffusion network features from edges.
    """
    if not edges:
        return {
            "root_outdeg": 0.0,
            "num_nodes": 1.0,
            "num_edges": 0.0,
            "tree_depth": 0.0,
            "max_breadth": 1.0,
            "leaf_nodes": 1.0,
            "leaf_ratio": 1.0,
            "avg_outdeg": 0.0,
            "branching_factor": 0.0,
        }

    children = defaultdict(list)
    nodes = {root_id}
    for u, v in edges:
        children[u].append(v)
        nodes.add(u)
        nodes.add(v)

    from collections import deque
    q = deque([(root_id, 0)])
    seen = {root_id}
    level_counts = Counter()
    max_depth = 0

    while q:
        u, d = q.popleft()
        level_counts[d] += 1
        max_depth = max(max_depth, d)
        for v in children[u]:
            if v not in seen:
                seen.add(v)
                q.append((v, d + 1))

    leaf_nodes = sum(1 for n in nodes if not children[n])
    num_nodes = len(nodes)
    num_edges = len(edges)

    return {
        "root_outdeg": float(len(children[root_id])),
        "num_nodes": float(num_nodes),
        "num_edges": float(num_edges),
        "tree_depth": float(max_depth),
        "max_breadth": float(max(level_counts.values())),
        "leaf_nodes": float(leaf_nodes),
        "leaf_ratio": float(leaf_nodes / num_nodes) if num_nodes > 0 else 0.0,
        "avg_outdeg": float(num_edges / num_nodes) if num_nodes > 0 else 0.0,
        "branching_factor": float(num_edges / max(1, num_nodes - leaf_nodes)),
    }


def load_source_tweets(source_path: Path) -> Dict[str, str]:
    """
    Load source tweets mapping tweet_id -> text.
    """
    mapping: Dict[str, str] = {}
    if not source_path.exists():
        return mapping

    for line in source_path.read_text().splitlines():
        if "\t" in line:
            tid, text = line.split("\t", 1)
            mapping[tid.strip()] = text.strip()

    return mapping


def prepare_twitter_dataset(name: str) -> List[Dict]:
    """
    Prepare Twitter15 or Twitter16 dataset.
    """
    dataset_dir = RAW_DIR / name
    if not dataset_dir.exists():
        print(f"⚠️ Skipping {name}: directory not found at {dataset_dir}")
        return []

    print(f"📂 Processing {name} from {dataset_dir}")

    # Load labels
    label_path = dataset_dir / "label.txt"
    label_map: Dict[str, str] = {}
    if label_path.exists():
        for line in label_path.read_text().splitlines():
            if ":" in line:
                lab, eid = line.split(":", 1)
                lab = lab.strip().lower().replace("_", "-")
                lab = re.sub(r"[^a-z\-]", "", lab)
                label_map[eid.strip()] = lab

    # Load source tweets
    source_map = load_source_tweets(dataset_dir / "source_tweets.txt")

    tree_dir = dataset_dir / "tree"
    rows: List[Dict] = []

    if tree_dir.exists():
        for tree_file in tree_dir.glob("*.txt"):
            event_id = tree_file.stem
            label = label_map.get(event_id, "unknown")

            edges = parse_tree_edges(tree_file, event_id)
            features = compute_diffusion_features(edges, event_id)

            
            # true -> 0 (non-misinfo)
            # false/unverified/non-rumor/unknown -> 1 (misinfo)
            binary_label = 0 if label == "true" else 1

            source_text = source_map.get(event_id, "")

            rows.append({
                "dataset": name,
                "event_id": event_id,
                "label_4class": label,
                "label_binary": binary_label,
                "source_text": source_text,
                **features
            })

    print(f"✅ {name}: {len(rows)} rows")
    return rows


# ============================================================================
# LAIR Dataset Preparation
# ============================================================================

def prepare_lair(raw_dir: Path) -> List[Dict]:
    """
    Prepare LIAR/LAIR dataset.
    """
    lair_dir = raw_dir / "lair"
    if not lair_dir.exists():
        print(f"⚠️ LAIR directory not found: {lair_dir}")
        return []

    fake_labels = {"pants-fire", "false", "barely-true"}

    rows: List[Dict] = []
    for split in ["train", "valid", "test"]:
        tsv_file = lair_dir / f"{split}.tsv"
        if not tsv_file.exists():
            continue

        with open(tsv_file, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for parts in reader:
                if len(parts) < 3:
                    continue

                rid = parts[0].strip()
                label_raw = parts[1].strip().lower()
                text = parts[2].strip()
                if not text:
                    continue

                binary = 1 if label_raw in fake_labels else 0

                rows.append({
                    "dataset": "lair",
                    "split": split,
                    "id": rid,
                    "source_text": text,
                    "label_binary": binary,
                    "root_outdeg": 0.0,
                    "num_nodes": 1.0,
                    "num_edges": 0.0,
                    "tree_depth": 0.0,
                    "max_breadth": 1.0,
                    "leaf_nodes": 1.0,
                    "leaf_ratio": 1.0,
                    "avg_outdeg": 0.0,
                    "branching_factor": 0.0,
                })

    print(f"✅ LAIR: {len(rows)} rows")
    return rows


# ============================================================================
# PHEME Dataset Preparation
# ============================================================================

def prepare_pheme(raw_dir: Path) -> List[Dict]:
    """
    Prepare PHEME dataset with correct path detection.
    """
    pheme_dir = raw_dir / "pheme"
    if not pheme_dir.exists():
        print(f"⚠️ PHEME directory not found: {pheme_dir}")
        return []

    rows: List[Dict] = []
    total_events = 0
    total_rumours = 0
    total_non_rumours = 0

    for event_dir in sorted(pheme_dir.iterdir()):
        if not event_dir.is_dir() or event_dir.name.startswith('.'):
            continue

        print(f"\n📂 Processing PHEME event: {event_dir.name}")
        event_rows = 0

        # rumours = label 1
        rumours_dir = event_dir / "rumours"
        if rumours_dir.exists():
            thread_count = 0
            for thread_dir in rumours_dir.iterdir():
                if not thread_dir.is_dir():
                    continue

                source_dir = thread_dir / "source-tweet"
                if source_dir.exists():
                    for json_file in source_dir.glob("*.json"):
                        try:
                            tweet_data = json.loads(json_file.read_text(encoding="utf-8", errors="ignore"))
                            text = (tweet_data.get("full_text")
                                    or tweet_data.get("text")
                                    or tweet_data.get("body")
                                    or "")
                            if text.strip():
                                rows.append({
                                    "dataset": "pheme",
                                    "event": event_dir.name,
                                    "thread_id": thread_dir.name,
                                    "tweet_id": str(tweet_data.get("id_str") or tweet_data.get("id") or thread_dir.name),
                                    "source_text": text.strip(),
                                    "label_binary": 1,
                                    "root_outdeg": 0.0,
                                    "num_nodes": 1.0,
                                    "num_edges": 0.0,
                                    "tree_depth": 0.0,
                                    "max_breadth": 1.0,
                                    "leaf_nodes": 1.0,
                                    "leaf_ratio": 1.0,
                                    "avg_outdeg": 0.0,
                                    "branching_factor": 0.0,
                                })
                                thread_count += 1
                                event_rows += 1
                        except Exception as e:
                            print(f"   ⚠️ Error reading {json_file}: {e}")
                            continue

            if thread_count > 0:
                print(f"   ✅ Rumours: {thread_count} threads")
                total_rumours += thread_count

        # non-rumours = label 0
        non_rumours_dir = event_dir / "non-rumours"
        if non_rumours_dir.exists():
            thread_count = 0
            for thread_dir in non_rumours_dir.iterdir():
                if not thread_dir.is_dir():
                    continue

                source_dir = thread_dir / "source-tweet"
                if source_dir.exists():
                    for json_file in source_dir.glob("*.json"):
                        try:
                            tweet_data = json.loads(json_file.read_text(encoding="utf-8", errors="ignore"))
                            text = (tweet_data.get("full_text")
                                    or tweet_data.get("text")
                                    or tweet_data.get("body")
                                    or "")
                            if text.strip():
                                rows.append({
                                    "dataset": "pheme",
                                    "event": event_dir.name,
                                    "thread_id": thread_dir.name,
                                    "tweet_id": str(tweet_data.get("id_str") or tweet_data.get("id") or thread_dir.name),
                                    "source_text": text.strip(),
                                    "label_binary": 0,
                                    "root_outdeg": 0.0,
                                    "num_nodes": 1.0,
                                    "num_edges": 0.0,
                                    "tree_depth": 0.0,
                                    "max_breadth": 1.0,
                                    "leaf_nodes": 1.0,
                                    "leaf_ratio": 1.0,
                                    "avg_outdeg": 0.0,
                                    "branching_factor": 0.0,
                                })
                                thread_count += 1
                                event_rows += 1
                        except Exception as e:
                            print(f"   ⚠️ Error reading {json_file}: {e}")
                            continue

            if thread_count > 0:
                print(f"   ✅ Non-rumours: {thread_count} threads")
                total_non_rumours += thread_count

        if event_rows > 0:
            total_events += 1

    print(f"\n✅ PHEME summary: {len(rows)} total rows from {total_events} events")
    print(f"   - Rumours: {total_rumours}")
    print(f"   - Non-rumours: {total_non_rumours}")

    return rows


# ============================================================================
# FakeNewsNet Dataset Preparation
# ============================================================================

def prepare_fakenewsnet(raw_dir: Path) -> List[Dict]:
    """
    Prepare FakeNewsNet dataset.
    """
    fnn_dir = raw_dir / "fakenewsnet"
    if not fnn_dir.exists():
        print(f"⚠️ FakeNewsNet directory not found: {fnn_dir}")
        return []

    rows: List[Dict] = []
    files = [
        ("gossipcop_fake.csv", 1, "gossipcop"),
        ("gossipcop_real.csv", 0, "gossipcop"),
        ("politifact_fake.csv", 1, "politifact"),
        ("politifact_real.csv", 0, "politifact"),
    ]

    total_files_found = 0
    for fname, label, subset in files:
        csv_file = fnn_dir / fname
        if not csv_file.exists():
            continue

        total_files_found += 1
        try:
            import pandas as pd
            df = pd.read_csv(csv_file)

            text_col = None
            for col in ["text", "content", "article", "body", "title"]:
                if col in df.columns:
                    text_col = col
                    break

            if text_col:
                for i, row in df.iterrows():
                    text = str(row.get(text_col, "")).strip()
                    if text:
                        rows.append({
                            "dataset": "fakenewsnet",
                            "subset": subset,
                            "event_id": f"{subset}_{i}",
                            "source_text": text,
                            "label_binary": label,
                            "root_outdeg": 0.0,
                            "num_nodes": 1.0,
                            "num_edges": 0.0,
                            "tree_depth": 0.0,
                            "max_breadth": 1.0,
                            "leaf_nodes": 1.0,
                            "leaf_ratio": 1.0,
                            "avg_outdeg": 0.0,
                            "branching_factor": 0.0,
                        })
        except Exception as e:
            print(f"⚠️ Error processing {fname}: {e}")
            continue

    if total_files_found == 0:
        print("⚠️ No FakeNewsNet CSV files found. Expected: gossipcop_fake.csv, gossipcop_real.csv, politifact_fake.csv, politifact_real.csv")

    print(f"✅ FakeNewsNet: {len(rows)} rows")
    return rows


# ============================================================================
# FakeHealth Dataset Preparation
# ============================================================================

def prepare_fakehealth(raw_dir: Path) -> List[Dict]:
    """
    Prepare FakeHealth dataset.
    """
    fh_dir = raw_dir / "FakeHealth"
    if not fh_dir.exists():
        print(f"⚠️ FakeHealth directory not found: {fh_dir}")
        return []

    rows: List[Dict] = []
    content_dir = fh_dir / "content"
    reviews_dir = fh_dir / "reviews"

    if not content_dir.exists() or not reviews_dir.exists():
        print("⚠️ FakeHealth missing content or reviews directory")
        return []

    for subset in ["HealthStory", "HealthRelease"]:
        subset_content_dir = content_dir / subset
        review_file = reviews_dir / f"{subset}.json"

        if not subset_content_dir.exists() or not review_file.exists():
            continue

        try:
            with open(review_file, "r", encoding="utf-8") as f:
                reviews = json.load(f)

            label_map: Dict[str, int] = {}
            if isinstance(reviews, list):
                for i, review in enumerate(reviews):
                    if isinstance(review, dict):
                        label_val = None
                        for key in ["label", "verdict", "rating"]:
                            if key in review:
                                val = str(review[key]).lower()
                                if "fake" in val or "false" in val or val.strip() == "0":
                                    label_val = 1
                                elif "real" in val or "true" in val or val.strip() == "1":
                                    label_val = 0
                                break

                        if label_val is not None:
                            stem = f"news_reviews_{i+1:05d}"
                            label_map[stem] = label_val

            for json_file in subset_content_dir.glob("*.json"):
                stem = json_file.stem
                if stem not in label_map:
                    continue

                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        content = json.load(f)

                    text = (content.get("text")
                            or content.get("content")
                            or content.get("article")
                            or "")

                    if text.strip():
                        rows.append({
                            "dataset": "fakehealth",
                            "subset": subset,
                            "id": stem,
                            "source_text": text.strip(),
                            "label_binary": label_map[stem],
                            "root_outdeg": 0.0,
                            "num_nodes": 1.0,
                            "num_edges": 0.0,
                            "tree_depth": 0.0,
                            "max_breadth": 1.0,
                            "leaf_nodes": 1.0,
                            "leaf_ratio": 1.0,
                            "avg_outdeg": 0.0,
                            "branching_factor": 0.0,
                        })
                except Exception:
                    continue

        except Exception as e:
            print(f"⚠️ Error processing FakeHealth {subset}: {e}")
            continue

    print(f"✅ FakeHealth: {len(rows)} rows")
    return rows


# ============================================================================
# SciFact Dataset Preparation
# ============================================================================

def prepare_scifact_local() -> List[Dict]:
    """
    Prepare SciFact dataset from local files.
    Expected path: ml/data/raw/scifact-master/
    """
    scifact_dir = RAW_DIR / "scifact-master"
    if not scifact_dir.exists():
        print(f"⚠️ SciFact directory not found: {scifact_dir}")
        return []

    print("\n📂 Processing SciFact dataset from local files...")

    rows: List[Dict] = []
    cross_val_dir = scifact_dir / "cross_validation"
    if not cross_val_dir.exists():
        print("⚠️ SciFact cross_validation directory not found")
        return []

    for fold_dir in sorted(cross_val_dir.glob("fold_*")):
        if not fold_dir.is_dir():
            continue

        print(f"   Processing {fold_dir.name}")

        for file_pattern in ["claims_train_*.jsonl", "claims_dev_*.jsonl"]:
            for claim_file in fold_dir.glob(file_pattern):
                try:
                    with open(claim_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if not line.strip():
                                continue
                            try:
                                item = json.loads(line)
                                claim = item.get("claim", "").strip()
                                if not claim:
                                    continue

                                evidences = item.get("evidence", [])
                                label = 0
                                for evidence in evidences:
                                    if isinstance(evidence, dict):
                                        label_text = evidence.get("label", "")
                                        if label_text == "CONTRADICT":
                                            label = 1
                                            break
                                        elif label_text == "SUPPORT":
                                            label = 0

                                rows.append({
                                    "dataset": "scifact",
                                    "id": str(item.get("id", "")),
                                    "source_text": claim,
                                    "label_binary": label,
                                    "root_outdeg": 0.0,
                                    "num_nodes": 1.0,
                                    "num_edges": 0.0,
                                    "tree_depth": 0.0,
                                    "max_breadth": 1.0,
                                    "leaf_nodes": 1.0,
                                    "leaf_ratio": 1.0,
                                    "avg_outdeg": 0.0,
                                    "branching_factor": 0.0,
                                })
                            except json.JSONDecodeError:
                                continue
                except Exception as e:
                    print(f"      ⚠️ Error reading {claim_file}: {e}")
                    continue

    # Deduplicate by claim text
    unique_rows: List[Dict] = []
    seen_claims = set()
    for row in rows:
        claim = row["source_text"]
        if claim not in seen_claims:
            seen_claims.add(claim)
            unique_rows.append(row)

    print(f"✅ SciFact: {len(unique_rows)} unique rows (from {len(rows)} total)")
    return unique_rows


# ============================================================================
# FakeCovid Dataset Preparation
# ============================================================================

def prepare_fakecovid(raw_dir: Path) -> List[Dict]:
    """
    Prepare FakeCovid dataset from Zenodo.
    """
    covid_dir = raw_dir / "fakecovid"
    csv_path = covid_dir / "FakeCovid_July2020.csv"

    if not csv_path.exists():
        print(f"⚠️ FakeCovid file not found: {csv_path}")
        print("   Download from: https://zenodo.org/record/3965871")
        return []

    print("\n📂 Processing FakeCovid dataset...")
    rows: List[Dict] = []

    try:
        import pandas as pd
        df = pd.read_csv(csv_path)
        print(f"   Total rows in CSV: {len(df)}")

        for idx, row in df.iterrows():
            title = str(row.get("title", "")).strip()
            content = str(row.get("content", "")).strip()

            if title and content:
                text = f"{title}\n\n{content}"
            elif title:
                text = title
            elif content:
                text = content
            else:
                continue

            if len(text) < 20:
                continue

            label_str = str(row.get("label", "")).lower()
            label = 1 if "false" in label_str else 0

            rows.append({
                "dataset": "fakecovid",
                "id": str(row.get("id", idx)),
                "source_text": text[:5000],
                "label_binary": label,
                "root_outdeg": 0.0,
                "num_nodes": 1.0,
                "num_edges": 0.0,
                "tree_depth": 0.0,
                "max_breadth": 1.0,
                "leaf_nodes": 1.0,
                "leaf_ratio": 1.0,
                "avg_outdeg": 0.0,
                "branching_factor": 0.0,
            })

            if (idx + 1) % 1000 == 0:
                print(f"   Processed {idx + 1} rows...")

        print(f"✅ FakeCovid: {len(rows)} rows")

    except Exception as e:
        print(f"⚠️ Error processing FakeCovid: {e}")
        import traceback
        traceback.print_exc()

    return rows


# ============================================================================
# MHMisinfo - Mental Health Misinformation Dataset
# ============================================================================

def prepare_mhmisinfo(raw_dir: Path) -> List[Dict]:
    """
    Prepare MHMisinfo - Mental Health Misinformation Dataset.
    Files: comments_MHMisinfo_Full.csv, comments_MHMisinfo_Gold.csv
    """
    mh_dir = raw_dir / "MHMisinfo"
    if not mh_dir.exists():
        print(f"⚠️ MHMisinfo directory not found: {mh_dir}")
        return []

    print("\n📂 Processing MHMisinfo - Mental Health Misinformation dataset...")
    rows: List[Dict] = []

    try:
        import pandas as pd

        csv_files = [
            ("comments_MHMisinfo_Full.csv", "full"),
            ("comments_MHMisinfo_Gold.csv", "gold")
        ]

        for csv_file, file_type in csv_files:
            file_path = mh_dir / csv_file
            if not file_path.exists():
                print(f"   ⚠️ {csv_file} not found, skipping...")
                continue

            print(f"   Reading {csv_file}...")
            df = pd.read_csv(file_path)
            print(f"   Found {len(df)} rows in {csv_file}")

            for idx, row in df.iterrows():
                text = str(row.get("comment", row.get("text", row.get("content", "")))).strip()

                label = 0
                if "label" in row:
                    label = 1 if str(row["label"]).lower() in ["1", "true", "misinfo", "fake"] else 0
                elif "gold_label" in row:
                    label = 1 if str(row["gold_label"]).lower() in ["1", "true", "misinfo", "fake"] else 0

                if text and len(text) > 20:
                    rows.append({
                        "dataset": f"mhmisinfo_{file_type}",
                        "id": str(row.get("id", idx)),
                        "source_text": text[:5000],
                        "label_binary": label,
                        "root_outdeg": 0.0,
                        "num_nodes": 1.0,
                        "num_edges": 0.0,
                        "tree_depth": 0.0,
                        "max_breadth": 1.0,
                        "leaf_nodes": 1.0,
                        "leaf_ratio": 1.0,
                        "avg_outdeg": 0.0,
                        "branching_factor": 0.0,
                    })

                    if len(rows) % 10000 == 0:
                        print(f"      Processed {len(rows)} rows...")

        print(f"✅ MHMisinfo: {len(rows)} rows")

    except Exception as e:
        print(f"⚠️ Error processing MHMisinfo: {e}")
        import traceback
        traceback.print_exc()

    return rows


# ============================================================================
# Brazilian Anti-Vaccine Telegram Dataset
# ============================================================================

def prepare_brazil_antivax(raw_dir: Path) -> List[Dict]:
    """
    Prepare Brazilian Anti-Vaccine Telegram Dataset.
    File: telegram-vaccine-info-disorder-dataset-2020-2025.jsonl
    Fields: text_content contains the message text
    """
    brazil_dir = raw_dir / "brazil_antivax"
    if not brazil_dir.exists():
        print(f"⚠️ Brazil Anti-Vaccine directory not found: {brazil_dir}")
        return []

    print("\n📂 Processing Brazilian Anti-Vaccine Telegram dataset...")
    rows: List[Dict] = []

    jsonl_file = brazil_dir / "telegram-vaccine-info-disorder-dataset-2020-2025.jsonl"
    if not jsonl_file.exists():
        print(f"⚠️ JSONL file not found: {jsonl_file}")
        return []

    try:
        line_count = 0
        vaccine_related = 0

        with open(jsonl_file, "r", encoding="utf-8") as f:
            for line in f:
                line_count += 1
                if line_count % 100000 == 0:
                    print(f"   Processing line {line_count}... (found {vaccine_related} vaccine-related so far)")

                try:
                    item = json.loads(line.strip())
                    text = item.get("text_content", "").strip()
                    if not text or len(text) < 10:
                        continue

                    is_vaccine = item.get("is_vaccine_related", False)
                    if isinstance(is_vaccine, str):
                        is_vaccine = is_vaccine.lower() == "true"

                    if is_vaccine:
                        vaccine_related += 1
                        text_lower = text.lower()

                        antivax_keywords = [
                            "perigosa", "dangerous", "morte", "death", "kill", "morrer",
                            "autismo", "autism", "doença", "disease", "envenenamento",
                            "poison", "chip", "microchip", "bill gates", "controle",
                            "control", "experimental", "dna", "genético", "genetic",
                            "alterar", "change", "modificar", "modify", "cancer",
                            "infertilidade", "infertility", "esterilização", "sterilization",
                            "matrix", "despertar", "wake up", "they don't want", "cover up",
                            "esconder", "hide", "verdade", "truth", "mentira", "lie"
                        ]

                        label = 1 if any(kw in text_lower for kw in antivax_keywords) else 0

                        rows.append({
                            "dataset": "brazil_antivax",
                            "id": str(item.get("message_id", item.get("id", len(rows)))),
                            "source_text": text[:5000],
                            "label_binary": label,
                            "root_outdeg": 0.0,
                            "num_nodes": 1.0,
                            "num_edges": 0.0,
                            "tree_depth": 0.0,
                            "max_breadth": 1.0,
                            "leaf_nodes": 1.0,
                            "leaf_ratio": 1.0,
                            "avg_outdeg": 0.0,
                            "branching_factor": 0.0,
                        })

                except json.JSONDecodeError:
                    continue
                except Exception:
                    continue

        print(f"✅ Brazil Anti-Vaccine: {len(rows)} rows from {line_count} total lines")
        print(f"   Found {vaccine_related} vaccine-related messages")

    except Exception as e:
        print(f"⚠️ Error processing Brazil Anti-Vaccine: {e}")
        import traceback
        traceback.print_exc()

    return rows


# ============================================================================
# CoAID COVID-19 Misinformation Dataset
# ============================================================================

def prepare_coaid(raw_dir: Path) -> List[Dict]:
    """
    Prepare CoAID COVID-19 misinformation dataset.
    Folder: CoAID-master/ with date subfolders
    """
    coaid_dir = raw_dir / "CoAID-master"
    if not coaid_dir.exists():
        print(f"⚠️ CoAID directory not found: {coaid_dir}")
        return []

    print("\n📂 Processing CoAID COVID-19 misinformation dataset...")
    rows: List[Dict] = []

    try:
        import pandas as pd

        date_folders = ["05-01-2020", "07-01-2020", "09-01-2020", "11-01-2020"]

        for date_folder in date_folders:
            folder_path = coaid_dir / date_folder
            if not folder_path.exists():
                continue

            for csv_file in folder_path.glob("*.csv"):
                print(f"   Reading {date_folder}/{csv_file.name}...")
                try:
                    df = pd.read_csv(csv_file)

                    for _, row in df.iterrows():
                        title = str(row.get("title", "")).strip()
                        content = str(row.get("content", "")).strip()

                        if title and content:
                            text = f"{title}\n\n{content}"
                        elif title:
                            text = title
                        elif content:
                            text = content
                        else:
                            continue

                        if len(text) < 20:
                            continue

                        label = 0
                        if "label" in row:
                            label_val = str(row["label"]).lower()
                            label = 1 if ("fake" in label_val or "false" in label_val) else 0

                        rows.append({
                            "dataset": "coaid",
                            "id": f"coaid_{date_folder}_{len(rows)}",
                            "source_text": text[:5000],
                            "label_binary": label,
                            "root_outdeg": 0.0,
                            "num_nodes": 1.0,
                            "num_edges": 0.0,
                            "tree_depth": 0.0,
                            "max_breadth": 1.0,
                            "leaf_nodes": 1.0,
                            "leaf_ratio": 1.0,
                            "avg_outdeg": 0.0,
                            "branching_factor": 0.0,
                        })
                except Exception as e:
                    print(f"      ⚠️ Error reading {csv_file.name}: {e}")
                    continue

        print(f"✅ CoAID: {len(rows)} rows")

    except Exception as e:
        print(f"⚠️ Error processing CoAID: {e}")

    return rows


# ============================================================================
# Twitter Death Hoaxes Dataset Preparation (folder: death-hoaxes)
# ============================================================================

def prepare_death_hoaxes(raw_dir: Path) -> List[Dict]:
    dh_dir = raw_dir / "death-hoaxes"
    if not dh_dir.exists():
        print(f"⚠️ death-hoaxes directory not found: {dh_dir}")
        return []

    print("\n📂 Processing death-hoaxes dataset...")
    rows: List[Dict] = []

    w2v_dir = dh_dir / "word2vec-rip"
    file_map = [
        (w2v_dir / "rip-fake", 1, "fake"),
        (w2v_dir / "rip-real", 0, "real"),
        (w2v_dir / "rip-commemoration", 0, "commemoration"),
    ]

    for fp, lab, tag in file_map:
        if not fp.exists():
            print(f"   ⚠️ Missing: {fp}")
            continue

        try:
            lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as e:
            print(f"   ⚠️ Could not read {fp}: {e}")
            continue

        added = 0
        for i, line in enumerate(lines):
            text = (line or "").strip()
            if not text or len(text) < 10:
                continue

            rows.append({
                "dataset": f"deathhoaxes_{tag}",
                "id": f"{tag}_{i}",
                "source_text": text[:5000],
                "label_binary": int(lab),
                "root_outdeg": 0.0,
                "num_nodes": 1.0,
                "num_edges": 0.0,
                "tree_depth": 0.0,
                "max_breadth": 1.0,
                "leaf_nodes": 1.0,
                "leaf_ratio": 1.0,
                "avg_outdeg": 0.0,
                "branching_factor": 0.0,
            })
            added += 1

        print(f"   ✅ {fp.name}: {added} rows")

    print(f"✅ death-hoaxes total: {len(rows)} rows")
    return rows


# ============================================================================
# Unify and Split Datasets
# ============================================================================

def unify_datasets(all_rows: List[Dict]) -> List[Dict]:
    """
    Unify all datasets into common format.
    """
    unified: List[Dict] = []

    for r in all_rows:
        text = r.get("source_text") or r.get("text") or ""
        if not text.strip():
            continue

        label = r.get("label_binary")
        if label is None:
            label = r.get("label_binary_rumor", 0)

        unified_row = {
            "dataset": r.get("dataset", "unknown"),
            "id": str(r.get("id") or r.get("event_id") or r.get("thread_id") or ""),
            "source_text": text.strip(),
            "label_binary": int(label),
            "has_struct": 1 if any((c in r) and (float(r.get(c, 0.0)) != 0.0) for c in NUM_COLS) else 0,
        }

        for c in NUM_COLS:
            unified_row[c] = float(r.get(c, 0.0))

        unified.append(unified_row)

    return unified


def split_dataset(rows: List[Dict], seed: int = 42) -> Tuple[List, List, List]:
    """
    Split dataset into train/val/test with stratification.
    """
    rnd = random.Random(seed)

    by_label = {0: [], 1: []}
    for r in rows:
        by_label[int(r["label_binary"])].append(r)

    train: List[Dict] = []
    val: List[Dict] = []
    test: List[Dict] = []

    for _, group in by_label.items():
        rnd.shuffle(group)
        n = len(group)
        n_train = int(n * 0.8)
        n_val = int(n * 0.1)

        train.extend(group[:n_train])
        val.extend(group[n_train:n_train + n_val])
        test.extend(group[n_train + n_val:])

    rnd.shuffle(train)
    rnd.shuffle(val)
    rnd.shuffle(test)

    return train, val, test


def write_jsonl(path: Path, rows: List[Dict]):
    """Write rows to JSONL file."""
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ============================================================================
# Main
# ============================================================================

def main():
    """Main execution function."""
    print("🚀 Starting data preparation...")
    print(f"📁 Looking for raw data in: {RAW_DIR}")

    all_rows: List[Dict] = []

    # 1. Twitter datasets (have structural features)
    print("\n📂 Processing Twitter datasets...")
    all_rows.extend(prepare_twitter_dataset("twitter15"))
    all_rows.extend(prepare_twitter_dataset("twitter16"))

    # 2. LAIR dataset
    print("\n📂 Processing LAIR dataset...")
    all_rows.extend(prepare_lair(RAW_DIR))

    # 3. PHEME dataset
    print("\n📂 Processing PHEME dataset...")
    all_rows.extend(prepare_pheme(RAW_DIR))

    # 4. FakeNewsNet dataset
    print("\n📂 Processing FakeNewsNet dataset...")
    all_rows.extend(prepare_fakenewsnet(RAW_DIR))

    # 5. FakeHealth dataset
    print("\n📂 Processing FakeHealth dataset...")
    all_rows.extend(prepare_fakehealth(RAW_DIR))

    # 6. SciFact dataset
    print("\n📂 Processing SciFact dataset...")
    all_rows.extend(prepare_scifact_local())

    # 7. FakeCovid dataset
    print("\n📂 Processing FakeCovid dataset...")
    all_rows.extend(prepare_fakecovid(RAW_DIR))

    # 8. MHMisinfo (CAP THIS)
    print("\n📂 Processing MHMisinfo dataset...")
    mh_rows = prepare_mhmisinfo(RAW_DIR)
    mh_rows = _cap(mh_rows, 150_000)
    print(f"   🧪 MHMisinfo capped to: {len(mh_rows)} rows")
    all_rows.extend(mh_rows)

    # 9. Brazil antivax (CAP THIS)
    print("\n📂 Processing Brazilian Anti-Vaccine dataset...")
    br_rows = prepare_brazil_antivax(RAW_DIR)
    br_rows = _cap(br_rows, 150_000)
    print(f"   🧪 Brazil antivax capped to: {len(br_rows)} rows")
    all_rows.extend(br_rows)

    # 10. CoAID
    print("\n📂 Processing CoAID dataset...")
    all_rows.extend(prepare_coaid(RAW_DIR))

    # 11. Death hoaxes (CAP THIS)
    print("\n📂 Processing Death Hoaxes dataset...")
    dh_rows = prepare_death_hoaxes(RAW_DIR)
    dh_rows = _cap(dh_rows, 200_000)
    print(f"   🧪 DeathHoaxes capped to: {len(dh_rows)} rows")
    all_rows.extend(dh_rows)

    print(f"\n📊 Total raw rows: {len(all_rows)}")

    if not all_rows:
        print("\n❌ No data found! Please place your raw data in:")
        print(f"   {RAW_DIR}")
        return

    unified = unify_datasets(all_rows)
    print(f"📊 Unified rows: {len(unified)}")

    unified_path = PROCESSED_DIR / "unified_all.jsonl"
    write_jsonl(unified_path, unified)
    print(f"✅ Saved unified dataset: {unified_path}")

    train, val, test = split_dataset(unified)

    write_jsonl(SPLITS_DIR / "train.jsonl", train)
    write_jsonl(SPLITS_DIR / "val.jsonl", val)
    write_jsonl(SPLITS_DIR / "test.jsonl", test)

    label_dist = Counter([r["label_binary"] for r in unified])
    struct_dist = Counter([r["has_struct"] for r in unified])
    dataset_dist = Counter([r["dataset"] for r in unified])

    stats = {
        "total": len(unified),
        "train": len(train),
        "val": len(val),
        "test": len(test),
        "label_distribution": {
            "0": int(label_dist.get(0, 0)),
            "1": int(label_dist.get(1, 0)),
        },
        "has_struct": {
            "0": int(struct_dist.get(0, 0)),
            "1": int(struct_dist.get(1, 0)),
        },
        "datasets": dict(dataset_dist),
        "output_files": {
            "unified": str(unified_path),
            "train": str(SPLITS_DIR / "train.jsonl"),
            "val": str(SPLITS_DIR / "val.jsonl"),
            "test": str(SPLITS_DIR / "test.jsonl"),
        }
    }

    stats_path = PROCESSED_DIR / "preparation_stats.json"
    with open(stats_path, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2)

    print("\n" + "=" * 60)
    print("✅ Data preparation complete!")
    print("=" * 60)
    print(f"   Train: {len(train)} rows")
    print(f"   Val: {len(val)} rows")
    print(f"   Test: {len(test)} rows")
    print(f"\n   Label distribution:")
    print(f"     - NON-MISINFO (0): {label_dist.get(0, 0)}")
    print(f"     - MISINFO (1): {label_dist.get(1, 0)}")
    print(f"\n   Dataset distribution:")
    for ds, count in sorted(dataset_dist.items()):
        print(f"     - {ds}: {count}")
    print(f"\n   Stats saved to: {stats_path}")
    print("=" * 60)


if __name__ == "__main__":
    main()
