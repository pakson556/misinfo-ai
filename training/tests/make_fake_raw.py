"""Generate a tiny synthetic raw-data folder in the real datasets' on-disk formats.

Used by test_pipeline.py and CI to prove prepare.py -> baseline.py -> backend
loading works without downloading anything. The text is random filler; the
numbers it produces mean nothing.
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

FALSE_WORDS = ["secret", "cure", "hidden", "banned", "shocking", "hoax", "they", "exposed", "miracle", "truth"]
TRUE_WORDS = ["report", "council", "study", "published", "according", "data", "officials", "percent", "annual", "survey"]
FILLER = ["the", "a", "in", "of", "and", "to", "on", "for", "with", "city", "people", "week", "year", "new"]


def sent(rng: random.Random, label: int, n: int = 14) -> str:
    vocab = FALSE_WORDS if label else TRUE_WORDS
    words = [rng.choice(vocab if rng.random() < 0.35 else FILLER) for _ in range(n)]
    return " ".join(words).capitalize() + f" {rng.randint(1, 10**6)}."


def make(root: Path, seed: int = 0) -> Path:
    rng = random.Random(seed)
    # LIAR
    d = root / "liar"
    d.mkdir(parents=True, exist_ok=True)
    labs = ["pants-fire", "false", "barely-true", "half-true", "mostly-true", "true"]
    for split, n in (("train", 300), ("valid", 60), ("test", 60)):
        with open(d / f"{split}.tsv", "w") as f:
            for i in range(n):
                lab = rng.choice(labs)
                y = 1 if lab in labs[:3] else 0
                f.write(f"{split}{i}.json\t{lab}\t{sent(rng, y)}\tsubject\tspeaker\n")
    # Twitter15/16 (with overlap between the two)
    shared = [(str(10**9 + i), rng.choice(["false", "true", "non-rumor", "unverified"])) for i in range(40)]
    for name in ("twitter15", "twitter16"):
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        items = shared + [
            (str(2 * 10**9 + i + (0 if name == "twitter15" else 500)), rng.choice(["false", "true", "non-rumor"]))
            for i in range(80)
        ]
        (d / "label.txt").write_text("\n".join(f"{lab}:{tid}" for tid, lab in items))
        (d / "source_tweets.txt").write_text(
            "\n".join(f"{tid}\t{sent(rng, int(lab == 'false'))} @someone http://t.co/x" for tid, lab in items)
        )
    # CoAID: label in filename
    d = root / "CoAID-master" / "05-01-2020"
    d.mkdir(parents=True, exist_ok=True)
    for fname, y in (("NewsFakeCOVID-19.csv", 1), ("NewsRealCOVID-19.csv", 0)):
        rows = ["news_url,title"] + [f"https://x.com/{fname}/{i},{sent(rng, y).replace(',', '')}" for i in range(120)]
        (d / fname).write_text("\n".join(rows))
    # FakeHealth: stars, joined on news_id
    d = root / "FakeHealth"
    (d / "content" / "HealthStory").mkdir(parents=True, exist_ok=True)
    (d / "reviews").mkdir(parents=True, exist_ok=True)
    reviews = []
    for i in range(150):
        nid = f"story_reviews_{i:05d}"
        rating = rng.randint(0, 5)
        reviews.append({"news_id": nid, "rating": rating})
        y = int(rating < 3)
        (d / "content" / "HealthStory" / f"{nid}.json").write_text(
            json.dumps({"title": sent(rng, y, 6), "text": " ".join(sent(rng, y) for _ in range(4))})
        )
    rng.shuffle(reviews)  # order must not matter (v1 bug)
    (d / "reviews" / "HealthStory.json").write_text(json.dumps(reviews))
    return root


if __name__ == "__main__":
    print(make(Path(sys.argv[1] if len(sys.argv) > 1 else "fake_raw")))
