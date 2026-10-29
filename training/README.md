# Training the style model

The style model is **optional**. The app's verdicts come from checking claims
against evidence; the style model only adds a weak "does this read like known
misinformation?" signal. Train it if you want that signal, or to report honest
ML results for a write-up.

## 1. Lay out the raw data

Point `--raw` at a folder like this (only the datasets you have are used):

```
raw/
  liar/            train.tsv valid.tsv test.tsv
  twitter15/       label.txt source_tweets.txt
  twitter16/       label.txt source_tweets.txt
  pheme/           <event>/rumours/<thread>/{source-tweet/*.json, annotation.json}
                   <event>/non-rumours/<thread>/source-tweet/*.json
  fakenewsnet/     politifact_fake.csv politifact_real.csv gossipcop_fake.csv gossipcop_real.csv
  CoAID-master/    <date>/NewsFakeCOVID-19.csv, NewsRealCOVID-19.csv, ...
  FakeHealth/      content/HealthStory/*.json, reviews/HealthStory.json (and HealthRelease)
```

This matches the folders the v1 scripts used, so your existing `ml/data/raw`
folder from iCloud should work as-is.

## 2. Prepare clean splits

```bash
pip install -r requirements.txt   # or just pandas pyarrow scikit-learn for steps 2-3
python prepare.py --raw /path/to/raw --out data
```

What it does: corrected label mappings (see `loaders.py` docstring and
`../docs/V1_AUDIT.md`), removes URLs/handles/label-leaking prefixes, drops exact
and near-duplicate texts and texts with conflicting labels, then splits by group
(event / story / claim) into `train` / `val` / `calib` / `test`. `data/stats.json`
records everything.

## 3. Baseline (CPU, minutes)

```bash
python baseline.py --data data --out ../backend/models/style
```

TF-IDF word + character n-grams with logistic regression, calibrated on `calib`,
threshold chosen on `val`, scored once on `test`. Also runs
**leave-one-dataset-out**: train without dataset X, test on X. That cross-dataset
number is the honest measure of generalisation, and the one to quote.

## 4. Transformer (GPU, e.g. free Colab T4)

```bash
python finetune.py --data data --model microsoft/deberta-v3-base --out ../backend/models/style
# add --lodo for leave-one-dataset-out (one extra training run per dataset)
```

Colab: upload `training/` and your `data/` folder (or mount Drive), then
`!pip install -r requirements.txt` and run the command above. Download the
resulting `style/` folder into `backend/models/`.

It fine-tunes with class-weighted loss and early stopping, temperature-scales on
`calib`, and exports `model.onnx` + `tokenizer.json`, so the server runs it with
`onnxruntime` and needs no PyTorch.

## Reading the results

`REPORT.md` next to the model has overall, per-dataset and cross-dataset tables.
Expect cross-dataset AUC well below in-dataset AUC: style models learn each
dataset's quirks. That gap is exactly why v2 makes evidence, not style, decide
the verdict.

## Tests

```bash
pytest -q tests   # runs prepare + baseline on synthetic data in the real formats
```
