# Machine learning

Offline training and evaluation. The API will load artifacts from `models/` later; nothing is trained in this scaffold.

## Layout

| Path | Role |
|------|------|
| `data/` | Raw and processed datasets (large files gitignored) |
| `data/raw/` | Source extracts (e.g. PaySim-style CSV) |
| `data/processed/` | Feature tables ready for training |
| `training/` | Training entrypoints and pipelines |
| `models/` | Serialized Isolation Forest / LightGBM artifacts |
| `evaluation/` | Metrics JSON, plots, evaluation notebooks later |

Do not commit `.pkl` / `.joblib` binaries; keep the folder with `.gitkeep`.
