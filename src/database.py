# Wildlife Monitoring System - Database Models
import os
from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Detection(db.Model):
    """Stores each animal detection event."""

    __tablename__ = "detections"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    species = db.Column(db.String(100), nullable=False, index=True)
    confidence = db.Column(db.Float, nullable=False)
    location = db.Column(db.String(255), nullable=True)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    source = db.Column(db.String(255), nullable=True)    # camera/file path
    image_path = db.Column(db.String(500), nullable=True)
    bbox_x1 = db.Column(db.Float, nullable=True)
    bbox_y1 = db.Column(db.Float, nullable=True)
    bbox_x2 = db.Column(db.Float, nullable=True)
    bbox_y2 = db.Column(db.Float, nullable=True)
    alert_sent = db.Column(db.Boolean, default=False)

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "species": self.species,
            "confidence": round(self.confidence, 4),
            "location": self.location,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "source": self.source,
            "image_path": self.image_path,
            "bbox": [self.bbox_x1, self.bbox_y1, self.bbox_x2, self.bbox_y2],
            "alert_sent": self.alert_sent,
        }

    def __repr__(self):
        return f"<Detection {self.species} @ {self.timestamp}>"


class Alert(db.Model):
    """Stores generated alerts for endangered species detections."""

    __tablename__ = "alerts"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    detection_id = db.Column(db.Integer, db.ForeignKey("detections.id"), nullable=False)
    species = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)
    alert_type = db.Column(db.String(50), default="console")  # console / email / sms
    resolved = db.Column(db.Boolean, default=False)

    detection = db.relationship("Detection", backref=db.backref("alerts", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "detection_id": self.detection_id,
            "species": self.species,
            "message": self.message,
            "alert_type": self.alert_type,
            "resolved": self.resolved,
        }

    def __repr__(self):
        return f"<Alert {self.species} [{self.alert_type}] @ {self.timestamp}>"


def init_db(app):
    """Initialise the database and create tables."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
