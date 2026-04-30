# Wildlife Monitoring System - Real-Time Detection Script
"""
Run YOLOv8 inference on images, video files, or a live camera feed.

Usage:
    python src/detection.py --source 0                     # webcam
    python src/detection.py --source video.mp4
    python src/detection.py --source image.jpg
    python src/detection.py --source /path/to/images/
"""
import argparse
import logging
import sys
from pathlib import Path

# Ensure project root is on the Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.alerts import process_detection_alert, should_alert
from src.utils import draw_detections, enhance_low_light, overlay_timestamp, save_detection_frame, setup_logging

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Wildlife species detection with YOLOv8")
    parser.add_argument("--source", default="0", help="Source: 0 (webcam), file path, or directory")
    parser.add_argument("--weights", default="models/wildlife_yolov8/weights/best.pt",
                        help="Path to trained YOLOv8 weights")
    parser.add_argument("--conf", type=float, default=0.4, help="Confidence threshold")
    parser.add_argument("--iou", type=float, default=0.45, help="IoU threshold for NMS")
    parser.add_argument("--imgsz", type=int, default=640, help="Inference image size")
    parser.add_argument("--device", default="", help="Device: '' (auto), 'cpu', '0' ...")
    parser.add_argument("--output", default="outputs", help="Directory to save annotated frames")
    parser.add_argument("--no-save", action="store_true", help="Do not save output frames")
    parser.add_argument("--no-display", action="store_true", help="Suppress OpenCV window")
    parser.add_argument("--low-light", action="store_true", help="Apply CLAHE low-light enhancement")
    parser.add_argument("--location", default=None, help="Camera trap location label")
    parser.add_argument("--log-db", action="store_true", help="Log detections to database")
    return parser.parse_args()


def _load_model(weights: str, device: str):
    """Load the YOLO model; fall back to yolov8n if weights are missing."""
    from ultralytics import YOLO

    weights_path = Path(weights)
    if not weights_path.exists():
        logger.warning(
            "Trained weights not found at '%s'. Falling back to pretrained yolov8n.pt", weights
        )
        return YOLO("yolov8n.pt")

    logger.info("Loading weights: %s", weights_path)
    return YOLO(str(weights_path))


def _save_and_log(frame, results, class_names, args, app=None):
    """Save annotated frame to disk and log detections to the database if requested."""
    image_path = None
    if not args.no_save:
        image_path = save_detection_frame(frame, args.output)

    if not args.log_db or app is None:
        return image_path

    try:
        from src.database import Detection, db

        with app.app_context():
            for result in results:
                for box in result.boxes:
                    cls_id = int(box.cls[0])
                    species = class_names[cls_id] if cls_id < len(class_names) else "unknown"
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()

                    det = Detection(
                        species=species,
                        confidence=conf,
                        location=args.location,
                        source=str(args.source),
                        image_path=image_path,
                        bbox_x1=x1, bbox_y1=y1,
                        bbox_x2=x2, bbox_y2=y2,
                    )
                    db.session.add(det)
                    db.session.flush()

                    process_detection_alert(app, det, species, conf, args.location)

            db.session.commit()
    except Exception as exc:
        logger.error("DB logging failed: %s", exc)

    return image_path


def run_detection(args: argparse.Namespace, app=None) -> None:
    """Main detection loop."""
    import cv2

    setup_logging()
    model = _load_model(args.weights, args.device)
    class_names = list(model.names.values()) if hasattr(model, "names") else []

    source = args.source
    # Determine if source is a live camera index
    try:
        source = int(source)
    except (ValueError, TypeError):
        pass

    is_video = isinstance(source, int) or str(source).lower().endswith(
        (".mp4", ".avi", ".mov", ".mkv", ".webm")
    )

    if is_video:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            logger.error("Cannot open source: %s", source)
            return

        logger.info("Starting detection on: %s", source)
        frame_count = 0
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1
                if args.low_light:
                    frame = enhance_low_light(frame)

                results = model.predict(
                    frame,
                    conf=args.conf,
                    iou=args.iou,
                    imgsz=args.imgsz,
                    device=args.device or None,
                    verbose=False,
                )

                annotated = draw_detections(frame.copy(), results, class_names)
                annotated = overlay_timestamp(annotated)

                if results[0].boxes and len(results[0].boxes) > 0:
                    detected = [
                        class_names[int(b.cls[0])]
                        for b in results[0].boxes
                        if int(b.cls[0]) < len(class_names)
                    ]
                    for species in set(detected):
                        if should_alert(species):
                            conf = max(
                                float(b.conf[0])
                                for b in results[0].boxes
                                if int(b.cls[0]) < len(class_names)
                                and class_names[int(b.cls[0])] == species
                            )
                            process_detection_alert(app, None, species, conf, args.location)

                    _save_and_log(annotated, results, class_names, args, app)

                if not args.no_display:
                    cv2.imshow("Wildlife Monitor", annotated)
                    if cv2.waitKey(1) & 0xFF == ord("q"):
                        logger.info("User quit.")
                        break
        finally:
            cap.release()
            if not args.no_display:
                cv2.destroyAllWindows()

    else:
        # Image or directory
        logger.info("Running detection on image(s): %s", source)
        results_list = model.predict(
            source,
            conf=args.conf,
            iou=args.iou,
            imgsz=args.imgsz,
            device=args.device or None,
            save=False,
            verbose=True,
        )

        for res in results_list:
            frame = res.orig_img
            if args.low_light:
                frame = enhance_low_light(frame)
            annotated = draw_detections(frame.copy(), [res], class_names)
            annotated = overlay_timestamp(annotated)
            _save_and_log(annotated, [res], class_names, args, app)

            if not args.no_display:
                cv2.imshow("Wildlife Monitor", annotated)
                cv2.waitKey(0)

        if not args.no_display:
            cv2.destroyAllWindows()


if __name__ == "__main__":
    args = parse_args()
    app = None
    if args.log_db:
        # Import here to avoid circular imports if imported elsewhere
        from app import create_app
        app = create_app()
    run_detection(args, app=app)
