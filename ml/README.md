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
metrics JSON, and evaluation report. Use `--data PATH` to train from a local
CSV instead. The CSV must contain a binary `Class` column.

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
