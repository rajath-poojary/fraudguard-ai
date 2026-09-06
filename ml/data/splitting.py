"""Out-of-Time (OOT) Train/Validation/Test Splitter for Fraud Detection.

Strict temporal partitioning to prevent data leakage (future lookahead bias,
temporal information leakage, or concept drift leakage).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
from typing import Sequence

from ml.data.pipeline import TransactionRecord


@dataclass(frozen=True)
class SplitMetrics:
    total_records: int
    train_records: int
    val_records: int
    test_records: int
    train_fraud_count: int
    val_fraud_count: int
    test_fraud_count: int
    train_fraud_rate: float
    val_fraud_rate: float
    test_fraud_rate: float
    train_start: str
    train_end: str
    val_start: str
    val_end: str
    test_start: str
    test_end: str


@dataclass
class DatasetSplits:
    train: list[TransactionRecord]
    validation: list[TransactionRecord]
    test: list[TransactionRecord]
    metrics: SplitMetrics

    def assert_no_leakage(self) -> None:
        """Verify strict chronological ordering and absence of temporal leakage."""
        if not self.train or not self.validation or not self.test:
            raise ValueError("All splits must contain at least one record to verify temporal boundaries.")

        train_max_time = max(tx.timestamp for tx in self.train)
        val_min_time = min(tx.timestamp for tx in self.validation)
        val_max_time = max(tx.timestamp for tx in self.validation)
        test_min_time = min(tx.timestamp for tx in self.test)

        if train_max_time >= val_min_time:
            raise AssertionError(
                f"Data leakage detected! Train max timestamp ({train_max_time}) "
                f"is not strictly before Validation min timestamp ({val_min_time})."
            )

        if val_max_time >= test_min_time:
            raise AssertionError(
                f"Data leakage detected! Validation max timestamp ({val_max_time}) "
                f"is not strictly before Test min timestamp ({test_min_time})."
            )


class TemporalSplitter:
    """Partitions transactions strictly by time window (e.g. 70% train, 15% val, 15% test)."""

    def __init__(
        self,
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
    ) -> None:
        if not abs((train_ratio + val_ratio + test_ratio) - 1.0) < 1e-6:
            raise ValueError("Split ratios must sum to 1.0")
        self.train_ratio = train_ratio
        self.val_ratio = val_ratio
        self.test_ratio = test_ratio

    def split(self, transactions: Sequence[TransactionRecord]) -> DatasetSplits:
        if len(transactions) < 3:
            raise ValueError("At least 3 transactions are required to perform a 3-way split.")

        # Ensure transactions are sorted chronologically
        sorted_txs = sorted(transactions, key=lambda x: x.timestamp)

        min_time = sorted_txs[0].timestamp
        max_time = sorted_txs[-1].timestamp
        total_duration = max_time - min_time

        # Calculate time cutoff boundaries
        train_cutoff = min_time + total_duration * self.train_ratio
        val_cutoff = min_time + total_duration * (self.train_ratio + self.val_ratio)

        train: list[TransactionRecord] = []
        validation: list[TransactionRecord] = []
        test: list[TransactionRecord] = []

        for tx in sorted_txs:
            if tx.timestamp < train_cutoff:
                train.append(tx)
            elif tx.timestamp < val_cutoff:
                validation.append(tx)
            else:
                test.append(tx)

        # Edge-case fallback if time distribution clustered at exact boundaries
        if not train:
            train.append(sorted_txs[0])
        if not test:
            test.append(sorted_txs[-1])
        if not validation:
            mid_idx = len(sorted_txs) // 2
            validation.append(sorted_txs[mid_idx])

        # Recalculate strict index-based slices if time cutoffs resulted in timestamp ties
        train_max = max(tx.timestamp for tx in train)
        val_min = min(tx.timestamp for tx in validation)
        if train_max >= val_min:
            # Fallback to index-based partition of chronologically sorted records
            n = len(sorted_txs)
            train_end_idx = max(1, int(n * self.train_ratio))
            val_end_idx = max(train_end_idx + 1, int(n * (self.train_ratio + self.val_ratio)))
            train = sorted_txs[:train_end_idx]
            validation = sorted_txs[train_end_idx:val_end_idx]
            test = sorted_txs[val_end_idx:]

        train_fraud = sum(1 for tx in train if tx.is_fraud)
        val_fraud = sum(1 for tx in validation if tx.is_fraud)
        test_fraud = sum(1 for tx in test if tx.is_fraud)

        metrics = SplitMetrics(
            total_records=len(sorted_txs),
            train_records=len(train),
            val_records=len(validation),
            test_records=len(test),
            train_fraud_count=train_fraud,
            val_fraud_count=val_fraud,
            test_fraud_count=test_fraud,
            train_fraud_rate=(train_fraud / len(train) * 100) if train else 0.0,
            val_fraud_rate=(val_fraud / len(validation) * 100) if validation else 0.0,
            test_fraud_rate=(test_fraud / len(test) * 100) if test else 0.0,
            train_start=train[0].timestamp.isoformat() if train else "",
            train_end=train[-1].timestamp.isoformat() if train else "",
            val_start=validation[0].timestamp.isoformat() if validation else "",
            val_end=validation[-1].timestamp.isoformat() if validation else "",
            test_start=test[0].timestamp.isoformat() if test else "",
            test_end=test[-1].timestamp.isoformat() if test else "",
        )

        splits = DatasetSplits(train=train, validation=validation, test=test, metrics=metrics)
        splits.assert_no_leakage()
        return splits


def export_splits_to_csv(splits: DatasetSplits, output_dir: Path | str) -> dict[str, Path]:
    """Export train, validation, and test splits to CSV files, plus metadata JSON."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "transaction_id",
        "user_id",
        "timestamp",
        "amount",
        "currency",
        "merchant_id",
        "merchant_category",
        "device_id",
        "ip_address",
        "location",
        "account_age",
        "payment_method",
        "transaction_status",
        "previous_transaction_id",
        "is_fraud",
        "fraud_scenario",
    ]

    files: dict[str, Path] = {}
    for name, records in [
        ("train", splits.train),
        ("validation", splits.validation),
        ("test", splits.test),
    ]:
        csv_file = out_path / f"{name}.csv"
        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for rec in records:
                row = rec.to_dict()
                filtered_row = {k: row.get(k) for k in fieldnames}
                writer.writerow(filtered_row)
        files[name] = csv_file

    summary_file = out_path / "split_summary.json"
    with open(summary_file, mode="w", encoding="utf-8") as f:
        json.dump(asdict(splits.metrics), f, indent=2)
    files["summary"] = summary_file

    return files
