# v1 audit

A review of the original dissertation code (the `main` branch) and what v2 changes
because of it. Kept here so the reasoning behind v2 is part of the project.

## Problems that made v1's scores wrong

| # | Problem | Where in v1 | Effect | v2 fix |
|---|---|---|---|---|
| 1 | The "BERT" model was `distilbert-base-uncased-finetuned-sst-2-english`, a **sentiment** model. Index 1 means *positive sentiment*, but the code read it as "misinformation". | `ml/api/bert_classifier.py` | Cheerful text scored as riskier. It had 15% ensemble weight and also overwrote the stance. | Removed. Optional style model is trained on misinformation data, and its role is limited (see below). |
| 2 | Twitter15/16 `non-rumor` mapped to **misinformation**. | `prepare_data.py`, `prepare_twitter_dataset` | Ordinary tweets taught as false. | `non-rumor` and `true` -> 0, `false` -> 1, `unverified` dropped. |
| 3 | CoAID: code looked for a `label` column that doesn't exist (the label is in the filename), so **every CoAID row was labelled real**, including the fake ones. | `prepare_coaid` | Fake COVID news taught as real. | Label from `NewsFake…` / `NewsReal…` file names. |
| 4 | FakeHealth: only ratings exactly `"0"`/`"1"` were accepted, **1 star was treated as real**, and reviews were joined to articles by list position instead of `news_id`. | `prepare_fakehealth` | Most rows dropped; the rest mislabelled or mismatched. | Stars < 3 -> 1, joined on `news_id`. |
| 5 | Brazil anti-vax labels were produced by **keyword matching**. | `prepare_brazil_antivax` | The model learns the keywords back; inflated accuracy. | Dataset excluded. |
| 6 | PHEME `rumour` treated as "false". A rumour is an *unverified* claim. | `prepare_pheme` | Many true rumours labelled false. | Uses the veracity annotation; unverified rumours dropped. |
| 7 | FakeCovid texts are fact-check articles *about* false claims, labelled as misinformation. | `prepare_fakecovid` | Teaches that debunks are misinformation. | Excluded. |
| 8 | Random row-level split; no de-duplication; Twitter15 and 16 overlap; LIAR's official splits discarded. | `split_dataset` | Near-identical texts in train and test inflate scores. | Exact + MinHash near-duplicate removal, group-aware splits (event/story/claim), LIAR splits kept, assertion that no group crosses splits. |
| 9 | Propagation-tree features were always "single node" at inference. | `models.make_feature_frame` | The structural features and the "legacy early" model saw constants. | Removed from serving. |
| 10 | The health model was computed and then never used. | `predict_service.run_predict_auto` | Wasted latency. | Removed. |
| 11 | Threshold never applied: training saved key `threshold`, the API read `best_threshold`, then ignored the value for hardcoded 0.15 / 0.45 bands. | `models.load_model_with_threshold`, `main.startup` | Decision rule unrelated to training. | Threshold chosen on val and stored in `meta.json`; style model is a weak signal, not a decision rule. |
| 12 | Calibration and threshold were both fit on the validation set. | `calibrate_models.py` | Optimistic, miscalibrated probabilities. | Separate `calib` split for temperature/Platt scaling. |
| 13 | Final "probability" = weights x stance multiplier (up to x2.1) x internet adjustment, all hand-tuned. | `predict_service`, `stance_detector` | Not a probability. | Evidence decides; tactics/style are a prior weighted by missing evidence; confidence = evidence coverage. |

Your own results show it: the cleaner run scored **F1 0.63 / ROC-AUC 0.84**; adding
the keyword-labelled data raised accuracy to 0.96 without making the model better.

## Overfitting to demo examples

- Hardcoded evidence for "we only use 10% of our brain" (`internet_verifier.MINIMAL_FALLBACKS`).
- Regexes and branches written for specific test inputs ("pink salt", particular vaccine and climate sentences).
- Substring matching: `"ai"` matched "s**ai**d", `"pass"` matched "**pass**ed", and "actually" counted as debunking.

v2 has no topic-specific code paths; tactic patterns use word boundaries and are unit-tested against these cases.

## Reliability

- One request could make up to 24 sequential DuckDuckGo HTML scrapes (15 s timeout each) plus 4 sequential Ollama calls (90 s each). The frontend aborted after 30 s.
- DuckDuckGo HTML scraping is routinely blocked; `feeds.reuters.com` has been dead since 2020; unauthenticated Reddit JSON is rate-limited.
- "Infection rate", "audience reach" and similar fields were invented by the LLM, not measured.

v2: async parallel retrieval with caching and per-source isolation, an overall time budget, streaming progress, and official APIs only. Invented metrics removed.

## Deployability

- Hardcoded `127.0.0.1` URLs and CORS; Ollama assumed on localhost.
- No Docker, tests or CI.
- `events.jsonl` with users' pasted text committed to git.
- A whole virtualenv committed in history (why the repo is ~70 MB). Consider starting a fresh repository from the v2 branch if size matters.
- `torch`, `transformers` and `huggingface_hub` missing from requirements.

v2: env-based config, Docker + compose, 23 automated tests, GitHub Actions, SQLite/Postgres history with a privacy switch.
