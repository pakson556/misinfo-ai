# Style model results (31 Oct 2026)

Trained with `training/prepare.py` + `training/baseline.py` on the dissertation datasets: LIAR, Twitter15/16, FakeNewsNet (PolitiFact, GossipCop), CoAID and FakeHealth. 40,844 texts after cleaning (1,606 exact duplicates and 156 near-duplicate clusters removed, 113 texts with contradicting labels dropped). Splits are by group, so no story or claim appears in both training and test.

Not used: PHEME (this copy is the 5-event release with no true/false annotations), Brazil anti-vax (keyword-made labels), FakeCovid (debunk articles, not misinformation).

## TF-IDF baseline

## Overall test set

| Metric | Value |
|---|---|
| n | 5624 |
| roc_auc | 0.855 |
| pr_auc | 0.717 |
| macro_f1 | 0.758 |
| f1 | 0.663 |
| precision | 0.635 |
| recall | 0.693 |
| accuracy | 0.795 |
| brier | 0.135 |
| ece | 0.022 |
| threshold | 0.380 |

## Per dataset (test split)

| Dataset | n | ROC-AUC | Macro-F1 |
|---|---|---|---|
| coaid | 852 | 0.937 | 0.846 |
| fakehealth | 326 | 0.707 | 0.630 |
| fnn_gossipcop | 3046 | 0.864 | 0.777 |
| fnn_politifact | 143 | 0.765 | 0.671 |
| liar | 1016 | 0.639 | 0.579 |
| twitter1516 | 241 | 0.899 | 0.782 |

## Leave-one-dataset-out (trained without that dataset)

This is the honest number: how well the model handles a source it has never seen.

| Held-out dataset | ROC-AUC | Macro-F1 |
|---|---|---|
| coaid | 0.722 | 0.619 |
| fakehealth | 0.478 | 0.506 |
| fnn_gossipcop | 0.540 | 0.525 |
| fnn_politifact | 0.595 | 0.533 |
| liar | 0.537 | 0.439 |
| twitter1516 | 0.591 | 0.506 |

**Mean cross-dataset ROC-AUC: 0.577**

## What it means

- On a held-out test from the same sources the model is decent (ROC-AUC 0.86).
- On a source it has never seen it is close to a coin flip (mean ROC-AUC 0.58). Writing style alone does not generalise; that is why the app decides verdicts from evidence.
- The app scales the model's influence by this number (reliability 0.26), so it can only nudge the risk score slightly.
- Next step: fine-tune a transformer (training/finetune.py) on a GPU and compare the cross-dataset score.
