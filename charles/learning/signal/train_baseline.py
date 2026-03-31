from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from learning.signal.schemas import SignalDatasetRecord


def _macro_f1(truth: list[int], pred: list[int], num_classes: int) -> float:
    f1_scores: list[float] = []
    for class_id in range(num_classes):
        tp = sum(1 for t, p in zip(truth, pred, strict=False) if t == class_id and p == class_id)
        fp = sum(1 for t, p in zip(truth, pred, strict=False) if t != class_id and p == class_id)
        fn = sum(1 for t, p in zip(truth, pred, strict=False) if t == class_id and p != class_id)
        if tp == 0 and fp == 0 and fn == 0:
            continue
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        if precision + recall == 0:
            f1_scores.append(0.0)
        else:
            f1_scores.append(2 * precision * recall / (precision + recall))
    return float(sum(f1_scores) / len(f1_scores)) if f1_scores else 0.0


def _load_index(path: str | Path) -> list[SignalDatasetRecord]:
    source = Path(path)
    records: list[SignalDatasetRecord] = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(SignalDatasetRecord.model_validate(json.loads(line)))
    return records


def _load_features(records: list[SignalDatasetRecord]) -> tuple[np.ndarray, np.ndarray]:
    features: list[np.ndarray] = []
    availability_features: list[np.ndarray] = []
    for record in records:
        payload = np.load(record.array_path, allow_pickle=True)
        channels = payload["channels"].astype(np.float32)
        availability = payload["availability"].astype(np.float32)
        features.append(channels)
        availability_features.append(availability)
    return np.stack(features, axis=0), np.stack(availability_features, axis=0)


def train_signal_baseline(
    index_path: str | Path,
    *,
    epochs: int = 8,
    batch_size: int = 8,
    learning_rate: float = 1e-3,
) -> dict[str, object]:
    records = _load_index(index_path)
    train_records = [record for record in records if record.split == "train"]
    eval_records = [record for record in records if record.split == "eval"]
    if not train_records or not eval_records:
        raise RuntimeError("Signal baseline requires both train and eval records.")

    labels = sorted({record.primary_problem_id for record in records})
    label_to_id = {label: idx for idx, label in enumerate(labels)}

    train_x, train_availability = _load_features(train_records)
    eval_x, eval_availability = _load_features(eval_records)
    train_y = np.array([label_to_id[record.primary_problem_id] for record in train_records], dtype=np.int64)
    eval_y = np.array([label_to_id[record.primary_problem_id] for record in eval_records], dtype=np.int64)

    import torch  # type: ignore
    from torch import nn  # type: ignore
    from torch.utils.data import DataLoader, TensorDataset  # type: ignore

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    class WaveformBaseline(nn.Module):
        def __init__(self, channels: int, signal_length: int, availability_size: int, num_classes: int):
            super().__init__()
            self.encoder = nn.Sequential(
                nn.Conv1d(channels, 32, kernel_size=7, padding=3),
                nn.ReLU(),
                nn.Conv1d(32, 64, kernel_size=5, padding=2),
                nn.ReLU(),
                nn.AdaptiveAvgPool1d(1),
            )
            self.head = nn.Sequential(
                nn.Linear(64 + availability_size, 64),
                nn.ReLU(),
                nn.Linear(64, num_classes),
            )

        def forward(self, waves, availability):
            encoded = self.encoder(waves).squeeze(-1)
            merged = torch.cat([encoded, availability], dim=1)
            return self.head(merged)

    model = WaveformBaseline(
        channels=train_x.shape[1],
        signal_length=train_x.shape[2],
        availability_size=train_availability.shape[1],
        num_classes=len(labels),
    ).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    criterion = nn.CrossEntropyLoss()

    train_dataset = TensorDataset(
        torch.tensor(train_x, dtype=torch.float32),
        torch.tensor(train_availability, dtype=torch.float32),
        torch.tensor(train_y, dtype=torch.long),
    )
    eval_dataset = TensorDataset(
        torch.tensor(eval_x, dtype=torch.float32),
        torch.tensor(eval_availability, dtype=torch.float32),
        torch.tensor(eval_y, dtype=torch.long),
    )
    train_loader = DataLoader(train_dataset, batch_size=min(batch_size, len(train_dataset)), shuffle=True)
    eval_loader = DataLoader(eval_dataset, batch_size=min(batch_size, len(eval_dataset)), shuffle=False)

    train_loss_history: list[float] = []
    for _ in range(epochs):
        model.train()
        running_loss = 0.0
        total = 0
        for waves, availability, targets in train_loader:
            waves = waves.to(device)
            availability = availability.to(device)
            targets = targets.to(device)
            optimizer.zero_grad()
            logits = model(waves, availability)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()
            running_loss += float(loss.item()) * int(targets.size(0))
            total += int(targets.size(0))
        train_loss_history.append(running_loss / max(total, 1))

    model.eval()
    truth: list[int] = []
    pred: list[int] = []
    with torch.inference_mode():
        for waves, availability, targets in eval_loader:
            waves = waves.to(device)
            availability = availability.to(device)
            logits = model(waves, availability)
            predictions = torch.argmax(logits, dim=1).cpu().tolist()
            pred.extend(predictions)
            truth.extend(targets.cpu().tolist())

    accuracy = sum(int(t == p) for t, p in zip(truth, pred, strict=False)) / max(len(truth), 1)
    macro_f1 = _macro_f1(truth, pred, len(labels))

    artifacts_dir = Path(index_path).parent / "runs" / "signal_baseline"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = artifacts_dir / "signal_baseline.pt"
    summary_path = artifacts_dir / "signal_baseline_summary.json"
    torch.save(
        {
            "state_dict": model.state_dict(),
            "label_to_id": label_to_id,
            "channel_names": train_records[0].channel_names,
        },
        checkpoint_path,
    )

    summary = {
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "index_path": str(index_path),
        "train_samples": len(train_records),
        "eval_samples": len(eval_records),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "device": str(device),
        "labels": labels,
        "train_loss_history": train_loss_history,
        "eval_accuracy": accuracy,
        "eval_macro_f1": macro_f1,
        "eval_label_counts": dict(sorted(Counter(record.primary_problem_id for record in eval_records).items())),
        "checkpoint_path": str(checkpoint_path),
    }
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Train a raw-waveform baseline classifier.")
    parser.add_argument("--index-path", required=True, help="Path to signal_index.jsonl.")
    parser.add_argument("--epochs", type=int, default=8, help="Number of training epochs.")
    parser.add_argument("--batch-size", type=int, default=8, help="Training batch size.")
    parser.add_argument("--learning-rate", type=float, default=1e-3, help="Optimizer learning rate.")
    args = parser.parse_args()

    summary = train_signal_baseline(
        args.index_path,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
