"""End-to-end check of the training pipeline on synthetic data."""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
TRAINING = HERE.parent
sys.path.insert(0, str(TRAINING))
sys.path.insert(0, str(HERE))

from loaders import load_coaid, load_fakehealth, load_liar, load_twitter1516  # noqa: E402
from make_fake_raw import make  # noqa: E402


def test_label_fixes(tmp_path):
    raw = make(tmp_path / "raw")

    liar = load_liar(raw)
    assert set(liar["label"]) == {0, 1}
    assert set(liar["split"]) == {"train", "val", "test"}

    tw = load_twitter1516(raw)
    assert tw["group"].is_unique  # Twitter15/16 overlap removed
    labels = dict(line.split(":")[::-1] for line in (raw / "twitter15" / "label.txt").read_text().splitlines())
    for _, r in tw.iterrows():
        lab = labels.get(r["group"].split(":")[1])
        if lab == "non-rumor":
            assert r["label"] == 0  # v1 labelled these as misinformation

    coaid = load_coaid(raw)
    assert set(coaid["label"]) == {0, 1}  # v1 labelled every CoAID row 0

    fh = load_fakehealth(raw)
    reviews = {r["news_id"]: r["rating"] for r in json.loads((raw / "FakeHealth/reviews/HealthStory.json").read_text())}
    for _, r in fh.iterrows():
        assert r["label"] == int(reviews[r["group"].split(":")[1]] < 3)


def test_prepare_and_baseline_end_to_end(tmp_path):
    raw = make(tmp_path / "raw")
    data, model = tmp_path / "data", tmp_path / "model"
    run = lambda *a: subprocess.run([sys.executable, *a], cwd=TRAINING, check=True, capture_output=True, text=True)  # noqa: E731

    run("prepare.py", "--raw", str(raw), "--out", str(data))
    splits = {s: pd.read_parquet(data / f"{s}.parquet") for s in ("train", "val", "calib", "test")}
    groups = [set(df["group"]) for df in splits.values()]
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            assert not groups[i] & groups[j], "group leaked across splits"
    texts = pd.concat(splits.values())["text"]
    assert not texts.str.contains("http").any() and not texts.str.contains("@someone").any()

    run("baseline.py", "--data", str(data), "--out", str(model))
    meta = json.loads((model / "meta.json").read_text())
    assert meta["type"] == "sklearn"
    m = json.loads((model / "metrics.json").read_text())
    assert m["test"]["roc_auc"] > 0.7  # synthetic data is learnable
    assert "leave_one_dataset_out" in m
    assert (model / "REPORT.md").exists()
