# Wildlife Monitoring System - Utility Functions
import logging
import os
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# Species colour palette for bounding boxes (BGR)
SPECIES_COLOURS: dict[str, tuple[int, int, int]] = {
    "tiger": (0, 165, 255),         # orange
    "elephant": (255, 100, 50),      # blue-ish
    "rhinoceros": (50, 50, 200),     # red
    "snow_leopard": (150, 50, 255),  # purple
}
DEFAULT_COLOUR = (0, 255, 0)  # green


def get_species_colour(species: str) -> tuple[int, int, int]:
    return SPECIES_COLOURS.get(species.lower().replace(" ", "_"), DEFAULT_COLOUR)


def draw_detections(frame: np.ndarray, results, class_names: list[str]) -> np.ndarray:
    """Draw bounding boxes, labels, and confidence scores on a frame."""
    for result in results:
        for box in result.boxes:
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            conf = float(box.conf[0])
            cls_id = int(box.cls[0])
            label = class_names[cls_id] if cls_id < len(class_names) else "unknown"

            colour = get_species_colour(label)
            cv2.rectangle(frame, (x1, y1), (x2, y2), colour, 2)

            display_label = f"{label.replace('_', ' ').title()} {conf:.0%}"
            (tw, th), _ = cv2.getTextSize(display_label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
            cv2.rectangle(frame, (x1, y1 - th - 8), (x1 + tw + 4, y1), colour, -1)
            cv2.putText(
                frame,
                display_label,
                (x1 + 2, y1 - 4),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
                cv2.LINE_AA,
            )
    return frame


def save_detection_frame(frame: np.ndarray, output_dir: str = "outputs") -> str:
    """Save annotated frame to disk and return the file path."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(output_dir, f"detection_{ts}.jpg")
    cv2.imwrite(path, frame)
    return path


def overlay_timestamp(frame: np.ndarray) -> np.ndarray:
    """Overlay current UTC timestamp on a frame."""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    h, w = frame.shape[:2]
    cv2.putText(frame, ts, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return frame


def setup_logging(level: str = "INFO") -> None:
    """Configure root logger with a consistent format."""
    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def preprocess_frame(frame: np.ndarray, target_size: int = 640) -> np.ndarray:
    """Resize frame while preserving aspect ratio by padding."""
    h, w = frame.shape[:2]
    scale = target_size / max(h, w)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h))
    canvas = np.zeros((target_size, target_size, 3), dtype=np.uint8)
    canvas[:new_h, :new_w] = resized
    return canvas


def enhance_low_light(frame: np.ndarray) -> np.ndarray:
    """Enhance low-light frames using CLAHE on the L channel."""
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l_ch = clahe.apply(l_ch)
    enhanced = cv2.merge((l_ch, a_ch, b_ch))
    return cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)


def load_class_names(yaml_path: str = "dataset.yaml") -> list[str]:
    """Load class names from a YOLO dataset YAML file."""
    import yaml

    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)
    names = data.get("names", {})
    if isinstance(names, dict):
        return [names[i] for i in sorted(names)]
    return list(names)
