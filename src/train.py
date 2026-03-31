# Wildlife Monitoring System - Model Training Script
"""
Train a YOLOv8 model on the custom endangered-species dataset.

Usage:
    python src/train.py [--model yolov8n.pt] [--epochs 50] [--imgsz 640] [--batch 16]
"""
import argparse
import logging
import os
from pathlib import Path

from src.utils import setup_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train YOLOv8 on the Wildlife dataset")
    parser.add_argument("--model", default="yolov8n.pt", help="Base YOLOv8 weights (e.g. yolov8n.pt)")
    parser.add_argument("--data", default="dataset.yaml", help="Path to dataset YAML config")
    parser.add_argument("--epochs", type=int, default=50, help="Number of training epochs")
    parser.add_argument("--imgsz", type=int, default=640, help="Input image size")
    parser.add_argument("--batch", type=int, default=16, help="Batch size (-1 = auto)")
    parser.add_argument("--device", default="", help="Device: '' (auto), 'cpu', '0', '0,1', ...")
    parser.add_argument("--project", default="models", help="Output project directory")
    parser.add_argument("--name", default="wildlife_yolov8", help="Experiment name")
    parser.add_argument("--patience", type=int, default=20, help="Early-stopping patience")
    parser.add_argument("--workers", type=int, default=4, help="Number of dataloader workers")
    return parser.parse_args()


def train(args: argparse.Namespace) -> None:
    setup_logging()

    try:
        from ultralytics import YOLO
    except ImportError:
        logger.error("ultralytics is not installed. Run: pip install ultralytics")
        raise

    if not Path(args.data).exists():
        raise FileNotFoundError(f"Dataset config not found: {args.data}")

    logger.info("Loading base model: %s", args.model)
    model = YOLO(args.model)

    logger.info(
        "Starting training  epochs=%d  imgsz=%d  batch=%d",
        args.epochs, args.imgsz, args.batch,
    )

    results = model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        device=args.device or None,
        project=args.project,
        name=args.name,
        patience=args.patience,
        workers=args.workers,
        exist_ok=True,
    )

    best_weights = Path(args.project) / args.name / "weights" / "best.pt"
    if best_weights.exists():
        logger.info("Training complete. Best weights saved at: %s", best_weights)
    else:
        logger.warning("Training finished but best weights not found at expected path.")

    return results


def validate(args: argparse.Namespace) -> None:
    """Run validation using the best trained weights."""
    from ultralytics import YOLO

    best_weights = Path(args.project) / args.name / "weights" / "best.pt"
    if not best_weights.exists():
        logger.error("No trained weights found at %s. Train the model first.", best_weights)
        return

    logger.info("Validating model: %s", best_weights)
    model = YOLO(str(best_weights))
    metrics = model.val(data=args.data, imgsz=args.imgsz)
    logger.info("Validation mAP50: %.4f", metrics.box.map50)
    logger.info("Validation mAP50-95: %.4f", metrics.box.map)


if __name__ == "__main__":
    args = parse_args()
    train(args)
