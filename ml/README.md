# Machine learning

Offline training and evaluation for transaction fraud detection. The API can
load the selected artifact from `models/` later.

## Reproduce training

From the repository root, install `backend/requirements.txt`, then run:

```bash
.venv/Scripts/python.exe ml/training/train_fraud_models.py
```

The script downloads the public credit-card fraud dataset on first use, stores
it under `data/raw/`, and writes the selected model, preprocessing pipeline,
version metadata, metrics JSON, and evaluation report. Records are ordered by
`Time` and split chronologically into train, validation, and test partitions.
Class weighting handles imbalance, and the operating threshold is selected on
validation data with recall-weighted F2. Use `--data PATH` to train from a
local CSV instead. The CSV must contain a binary `Class` column. Publish a new
artifact version with `--model-version fraud-classifier-v1.0.1`.

The API exposes `POST /api/predict` and requires a `features` object containing
all feature names recorded in `models/model_version.json`. It returns the
probability, artifact version, thresholded decision, and risk level. Requests
with missing features fail rather than receiving an invented score.

## Unsupervised anomaly detection

`ml/anomaly_detection/isolation_forest.py` provides an independent
`IsolationForestAnomalyDetector`. It learns transaction behavior without using
the `Class` label, returns a higher-is-more-anomalous score, and applies a
configurable threshold. It can later run alongside the supervised classifier;
the two outputs remain separate until an application service combines them.

To score the bundled dataset from the repository root:

```bash
.venv-1/Scripts/python.exe -m ml.training.run_anomaly_detection --threshold 0.0
```

## Layout

| Path | Role |
|------|------|
| `data/` | Raw and processed datasets (large files gitignored) |
| `data/raw/` | Source extracts (e.g. PaySim-style CSV) |
| `data/processed/` | Feature tables ready for training |
| `training/` | Training entrypoints and pipelines |
| `models/` | Serialized fraud model and preprocessing artifacts |
| `evaluation/` | Generated metrics and evaluation report |

Do not commit `.pkl` / `.joblib` binaries; keep the folder with `.gitkeep`.
