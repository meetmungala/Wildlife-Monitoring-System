# Wildlife Monitoring System - Alert Generation
import logging
import os
from datetime import datetime

logger = logging.getLogger(__name__)

ENDANGERED_SPECIES = {"tiger", "elephant", "rhinoceros", "snow_leopard"}


def generate_alert(species: str, confidence: float, location: str | None = None) -> str:
    """Build a human-readable alert message for a detected species."""
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    loc_str = f" at {location}" if location else ""
    msg = (
        f"[ALERT] Endangered species detected!\n"
        f"  Species   : {species.replace('_', ' ').title()}\n"
        f"  Confidence: {confidence:.1%}\n"
        f"  Location  : {location or 'unknown'}\n"
        f"  Time      : {ts}"
    )
    return msg


def console_alert(species: str, confidence: float, location: str | None = None) -> str:
    """Print an alert to the console and return the message."""
    msg = generate_alert(species, confidence, location)
    print("\n" + "=" * 60)
    print(msg)
    print("=" * 60 + "\n")
    logger.warning(msg)
    return msg


def log_alert_to_db(app, detection_id: int, species: str, message: str, alert_type: str = "console"):
    """Persist an alert record in the database (requires app context)."""
    try:
        from src.database import Alert, db

        with app.app_context():
            alert = Alert(
                detection_id=detection_id,
                species=species,
                message=message,
                alert_type=alert_type,
            )
            db.session.add(alert)
            db.session.commit()
            logger.info("Alert saved: id=%s species=%s", alert.id, species)
            return alert
    except Exception as exc:
        logger.error("Failed to save alert: %s", exc)
        return None


def should_alert(species: str) -> bool:
    """Return True if the species is in the endangered list."""
    return species.lower().replace(" ", "_") in ENDANGERED_SPECIES


def process_detection_alert(app, detection, species: str, confidence: float, location: str | None = None):
    """Full alert pipeline: check species, print alert, store in DB."""
    if not should_alert(species):
        return None

    message = console_alert(species, confidence, location)

    if app is not None and detection is not None:
        alert = log_alert_to_db(app, detection.id, species, message)
        if alert:
            try:
                from src.database import db

                with app.app_context():
                    detection.alert_sent = True
                    db.session.commit()
            except Exception as exc:
                logger.error("Could not mark detection alert_sent: %s", exc)
        return alert

    return None
