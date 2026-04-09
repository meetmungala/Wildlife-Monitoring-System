# Wildlife Monitoring System - Database Models
import os
from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Behavior labels used throughout the prediction pipeline
BEHAVIOR_LABELS = ["hunting", "migrating", "grazing", "resting", "other"]


class Detection(db.Model):
    """Stores each animal detection event."""

    __tablename__ = "detections"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
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
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
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


class AnimalTrajectory(db.Model):
    """Records a single coordinate observation for an animal track."""

    __tablename__ = "animal_trajectories"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.String(100), nullable=False, index=True)
    species = db.Column(db.String(100), nullable=False, index=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    x = db.Column(db.Float, nullable=False)
    y = db.Column(db.Float, nullable=False)
    confidence = db.Column(db.Float, nullable=True)
    frame_index = db.Column(db.Integer, nullable=True)
    detection_id = db.Column(db.Integer, db.ForeignKey("detections.id"), nullable=True)

    detection = db.relationship("Detection", backref=db.backref("trajectories", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "animal_id": self.animal_id,
            "species": self.species,
            "timestamp": self.timestamp.isoformat(),
            "x": self.x,
            "y": self.y,
            "confidence": self.confidence,
            "frame_index": self.frame_index,
            "detection_id": self.detection_id,
        }

    def __repr__(self):
        return f"<AnimalTrajectory {self.animal_id} ({self.species}) @ {self.timestamp}>"


class BehaviorPrediction(db.Model):
    """Stores a behavior prediction result for an animal."""

    __tablename__ = "behavior_predictions"

    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.String(100), nullable=False, index=True)
    species = db.Column(db.String(100), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    behavior = db.Column(db.String(50), nullable=False)   # hunting/migrating/grazing/resting/other
    confidence = db.Column(db.Float, nullable=False)
    predicted_positions = db.Column(db.Text, nullable=True)  # JSON list of {x, y} dicts
    input_trajectory_ids = db.Column(db.Text, nullable=True)  # JSON list of trajectory IDs used

    def to_dict(self):
        import json
        return {
            "id": self.id,
            "animal_id": self.animal_id,
            "species": self.species,
            "timestamp": self.timestamp.isoformat(),
            "behavior": self.behavior,
            "confidence": round(self.confidence, 4),
            "predicted_positions": json.loads(self.predicted_positions) if self.predicted_positions else [],
            "input_trajectory_ids": json.loads(self.input_trajectory_ids) if self.input_trajectory_ids else [],
        }

    def __repr__(self):
        return f"<BehaviorPrediction {self.animal_id} → {self.behavior} ({self.confidence:.0%})>"


class AlertRule(db.Model):
    """Configurable rule that triggers a predicted alert for a species/behavior combination."""

    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    species = db.Column(db.String(100), nullable=True)   # None means any species
    behavior = db.Column(db.String(50), nullable=True)   # None means any behavior
    # Danger zone defined as a bounding box in image/map coordinates
    zone_x1 = db.Column(db.Float, nullable=True)
    zone_y1 = db.Column(db.Float, nullable=True)
    zone_x2 = db.Column(db.Float, nullable=True)
    zone_y2 = db.Column(db.Float, nullable=True)
    min_confidence = db.Column(db.Float, default=0.5, nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "species": self.species,
            "behavior": self.behavior,
            "zone": {
                "x1": self.zone_x1,
                "y1": self.zone_y1,
                "x2": self.zone_x2,
                "y2": self.zone_y2,
            },
            "min_confidence": self.min_confidence,
            "active": self.active,
            "created_at": self.created_at.isoformat(),
        }

    def __repr__(self):
        return f"<AlertRule '{self.name}' species={self.species} behavior={self.behavior}>"


class PredictedAlert(db.Model):
    """Logs an alert generated by the prediction engine."""

    __tablename__ = "predicted_alerts"

    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    animal_id = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(100), nullable=False)
    behavior = db.Column(db.String(50), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text, nullable=False)
    rule_id = db.Column(db.Integer, db.ForeignKey("alert_rules.id"), nullable=True)
    prediction_id = db.Column(db.Integer, db.ForeignKey("behavior_predictions.id"), nullable=True)
    resolved = db.Column(db.Boolean, default=False, nullable=False)

    rule = db.relationship("AlertRule", backref=db.backref("triggered_alerts", lazy=True))
    prediction = db.relationship("BehaviorPrediction", backref=db.backref("alerts", lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "animal_id": self.animal_id,
            "species": self.species,
            "behavior": self.behavior,
            "confidence": round(self.confidence, 4),
            "message": self.message,
            "rule_id": self.rule_id,
            "prediction_id": self.prediction_id,
            "resolved": self.resolved,
        }

    def __repr__(self):
        return f"<PredictedAlert {self.animal_id} [{self.behavior}] @ {self.timestamp}>"


def init_db(app):
    """Initialise the database and create tables."""
    db.init_app(app)
    with app.app_context():
        db.create_all()
