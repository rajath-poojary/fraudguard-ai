"""Score transactions with the independent Isolation Forest detector."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ml.anomaly_detection import IsolationForestAnomalyDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--historical-data",
        type=Path,
        default=Path("ml/data/raw/creditcard.csv"),
        help="CSV used to learn normal transaction behavior",
    )
    parser.add_argument(
        "--new-data",
        type=Path,
        help="CSV to score; defaults to the historical dataset",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("ml/evaluation/anomaly_results.csv"),
        help="CSV path for anomaly scores and decisions",
    )
    parser.add_argument("--threshold", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    historical = pd.read_csv(args.historical_data)
    new_transactions = pd.read_csv(args.new_data or args.historical_data)

    detector = IsolationForestAnomalyDetector(
        threshold=args.threshold,
        contamination="auto",
        random_state=42,
    )
    detector.fit(historical)
    results = detector.predict_anomalies(new_transactions)

    model_path = Path("ml/models/anomaly_detector.joblib")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    detector.save(model_path)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.output, index=False)
    print(f"Scored {len(results)} transactions")
    print(f"Anomalies: {int(results['is_anomaly'].sum())}")
    print(f"Model written to {model_path}")
    print(f"Results written to {args.output}")


if __name__ == "__main__":
    main()
