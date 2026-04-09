# Wildlife Monitoring System - Prediction Service
"""
PredictionService: orchestrates the full prediction pipeline.

1. Fetches recent trajectory points for an animal from the database.
2. Extracts kinematic features via TrajectoryAnalyzer.
3. Classifies behavior with BehaviorClassifier.
4. Generates future positions with LSTMPredictor.
5. Persists a BehaviorPrediction record.
6. Evaluates active AlertRules and creates PredictedAlert records when triggered.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class PredictionService:
    """
    High-level service that wraps trajectory lookup, classification,
    movement prediction, and alert evaluation.

    Parameters
    ----------
    db : SQLAlchemy db instance
    classifier : BehaviorClassifier instance
    predictor  : LSTMPredictor instance
    analyzer   : TrajectoryAnalyzer class (or instance with extract_features)
    lookback_hours : int
        How many hours of trajectory history to consider.
    """

    def __init__(self, db, classifier, predictor, analyzer, lookback_hours: int = 24) -> None:
        self.db = db
        self.classifier = classifier
        self.predictor = predictor
        self.analyzer = analyzer
        self.lookback_hours = lookback_hours

    # ------------------------------------------------------------------ #
    #  Primary entry point
    # ------------------------------------------------------------------ #

    def run(self, animal_id: str, species: str) -> Dict[str, Any]:
        """
        Execute the full prediction pipeline for one animal.

        Returns
        -------
        dict with keys:
            ``animal_id``, ``species``, ``behavior``, ``confidence``,
            ``predicted_positions``, ``alerts_generated``,
            ``prediction_id``.
        """
        from src.database import AnimalTrajectory, BehaviorPrediction, AlertRule, PredictedAlert

        since = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours)
        traj_rows = (
            AnimalTrajectory.query
            .filter(AnimalTrajectory.animal_id == animal_id)
            .filter(AnimalTrajectory.timestamp >= since)
            .order_by(AnimalTrajectory.timestamp.asc())
            .all()
        )

        if not traj_rows:
            return {
                "animal_id": animal_id,
                "species": species,
                "behavior": "other",
                "confidence": 0.0,
                "predicted_positions": [],
                "alerts_generated": 0,
                "prediction_id": None,
                "error": "No trajectory data found",
            }

        points = [{"x": r.x, "y": r.y, "confidence": r.confidence or 1.0} for r in traj_rows]
        traj_ids = [r.id for r in traj_rows]

        # Feature extraction
        features = self.analyzer.extract_features(points)

        # Behavior classification
        classification = self.classifier.classify(features)

        # Movement prediction
        prediction = self.predictor.predict(points)

        # Persist prediction
        bp = BehaviorPrediction(
            animal_id=animal_id,
            species=species,
            behavior=classification["behavior"],
            confidence=classification["confidence"],
            predicted_positions=json.dumps(prediction["predicted_positions"]),
            input_trajectory_ids=json.dumps(traj_ids),
        )
        self.db.session.add(bp)
        self.db.session.flush()  # get bp.id before evaluating rules

        # Evaluate alert rules
        alerts_generated = self._evaluate_rules(bp, points, prediction["predicted_positions"])

        self.db.session.commit()

        return {
            "animal_id": animal_id,
            "species": species,
            "behavior": classification["behavior"],
            "confidence": classification["confidence"],
            "predicted_positions": prediction["predicted_positions"],
            "alerts_generated": alerts_generated,
            "prediction_id": bp.id,
        }

    # ------------------------------------------------------------------ #
    #  Alert rule evaluation
    # ------------------------------------------------------------------ #

    def _evaluate_rules(
        self,
        prediction: Any,
        current_points: List[Dict],
        predicted_positions: List[Dict],
    ) -> int:
        """Check all active rules; create PredictedAlert rows when triggered."""
        from src.database import AlertRule, PredictedAlert

        active_rules = AlertRule.query.filter(AlertRule.active == True).all()  # noqa: E712
        count = 0

        for rule in active_rules:
            if not self._rule_matches_species(rule, prediction.species):
                continue
            if not self._rule_matches_behavior(rule, prediction.behavior):
                continue
            if prediction.confidence < rule.min_confidence:
                continue

            # Check if any predicted position falls inside the danger zone
            if not self._any_in_zone(rule, predicted_positions):
                # Also check the most recent actual position
                if current_points and not self._point_in_zone(rule, current_points[-1]):
                    continue

            message = self._build_alert_message(rule, prediction)
            alert = PredictedAlert(
                animal_id=prediction.animal_id,
                species=prediction.species,
                behavior=prediction.behavior,
                confidence=prediction.confidence,
                message=message,
                rule_id=rule.id,
                prediction_id=prediction.id,
            )
            self.db.session.add(alert)
            count += 1
            logger.warning("Predicted alert triggered: rule=%s animal=%s behavior=%s",
                           rule.name, prediction.animal_id, prediction.behavior)

        return count

    # ------------------------------------------------------------------ #
    #  Helpers
    # ------------------------------------------------------------------ #

    @staticmethod
    def _rule_matches_species(rule: Any, species: str) -> bool:
        return rule.species is None or rule.species.lower() == species.lower()

    @staticmethod
    def _rule_matches_behavior(rule: Any, behavior: str) -> bool:
        return rule.behavior is None or rule.behavior.lower() == behavior.lower()

    @staticmethod
    def _point_in_zone(rule: Any, point: Dict) -> bool:
        if any(v is None for v in [rule.zone_x1, rule.zone_y1, rule.zone_x2, rule.zone_y2]):
            return True  # No zone restriction → always "in zone"
        px, py = point["x"], point["y"]
        return rule.zone_x1 <= px <= rule.zone_x2 and rule.zone_y1 <= py <= rule.zone_y2

    @classmethod
    def _any_in_zone(cls, rule: Any, positions: List[Dict]) -> bool:
        return any(cls._point_in_zone(rule, p) for p in positions)

    @staticmethod
    def _build_alert_message(rule: Any, prediction: Any) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        return (
            f"[PREDICTED ALERT] Rule: '{rule.name}'\n"
            f"  Animal    : {prediction.animal_id}\n"
            f"  Species   : {prediction.species.replace('_', ' ').title()}\n"
            f"  Behavior  : {prediction.behavior.capitalize()}\n"
            f"  Confidence: {prediction.confidence:.1%}\n"
            f"  Time      : {ts}"
        )
