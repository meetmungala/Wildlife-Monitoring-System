# Wildlife Monitoring System - Behavior Classifier
"""
BehaviorClassifier: classifies animal behavior from trajectory features.

Uses an ensemble of hand-crafted kinematic features (speed, acceleration,
turning rate, path straightness) to assign one of five behavior labels:
    hunting | migrating | grazing | resting | other

No external training data is required; the rules are calibrated for
normalised image-coordinate trajectories (0–1 range per axis).

Typical usage:
    from src.behavior_classifier import BehaviorClassifier
    classifier = BehaviorClassifier()
    result = classifier.classify(features)
    # result["behavior"]   → str label
    # result["confidence"] → float 0–1
    # result["scores"]     → dict of label → score
"""
from __future__ import annotations

import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


class BehaviorClassifier:
    """
    Feature-based behavior classifier.

    Parameters
    ----------
    thresholds : dict | None
        Override default threshold values for customisation.
    """

    # Default kinematic thresholds (tuned for image-space coords, 0–1 range).
    # These can be overridden via the ``thresholds`` constructor argument.
    _DEFAULTS: Dict[str, float] = {
        # Speed (mean displacement per frame, normalised)
        "speed_resting_max": 0.005,
        "speed_grazing_max": 0.025,
        "speed_migrating_min": 0.04,
        # Turning rate (mean absolute change in heading, radians)
        "turning_hunting_min": 0.4,
        "turning_migrating_max": 0.25,
        # Path straightness (0 = perfectly straight, 1 = completely random)
        "straightness_migrating_max": 0.35,
        # Speed variance
        "speed_var_hunting_min": 0.0002,
    }

    def __init__(self, thresholds: Dict[str, float] | None = None) -> None:
        self.thresholds = {**self._DEFAULTS, **(thresholds or {})}

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def classify(self, features: Dict[str, float]) -> Dict[str, Any]:
        """
        Classify behavior from pre-computed trajectory features.

        Parameters
        ----------
        features : dict
            Expected keys (all floats):
                ``mean_speed``, ``speed_variance``, ``mean_acceleration``,
                ``mean_turning_rate``, ``path_straightness``,
                ``num_points``.
            Missing keys default to 0.0.

        Returns
        -------
        dict with keys:
            ``behavior``   – predicted behavior label (str)
            ``confidence`` – confidence in [0, 1]
            ``scores``     – raw score per label (dict)
        """
        f = {k: float(features.get(k, 0.0)) for k in (
            "mean_speed", "speed_variance", "mean_acceleration",
            "mean_turning_rate", "path_straightness", "num_points",
        )}

        scores = self._score(f)
        best_label = max(scores, key=lambda k: scores[k])
        best_score = scores[best_label]

        # Normalise scores to a confidence via softmax-like rescaling
        total = sum(scores.values()) or 1.0
        confidence = round(best_score / total, 4)

        return {
            "behavior": best_label,
            "confidence": confidence,
            "scores": {k: round(v, 4) for k, v in scores.items()},
        }

    # ------------------------------------------------------------------ #
    #  Internal scoring
    # ------------------------------------------------------------------ #

    def _score(self, f: Dict[str, float]) -> Dict[str, float]:
        t = self.thresholds
        ms = f["mean_speed"]
        sv = f["speed_variance"]
        tr = f["mean_turning_rate"]
        ps = f["path_straightness"]

        scores: Dict[str, float] = {
            "hunting": 0.0,
            "migrating": 0.0,
            "grazing": 0.0,
            "resting": 0.0,
            "other": 0.1,  # small baseline
        }

        # --- Resting ---
        if ms <= t["speed_resting_max"]:
            scores["resting"] += 1.0
        elif ms <= t["speed_resting_max"] * 2:
            scores["resting"] += 0.5

        # --- Grazing ---
        if t["speed_resting_max"] < ms <= t["speed_grazing_max"]:
            scores["grazing"] += 0.8
            if tr > 0.3:
                scores["grazing"] += 0.3   # irregular small movements typical of grazing

        # --- Migrating ---
        if ms >= t["speed_migrating_min"] and ps <= t["straightness_migrating_max"] and tr <= t["turning_migrating_max"]:
            scores["migrating"] += 1.2
        elif ms >= t["speed_migrating_min"] * 0.7 and ps <= t["straightness_migrating_max"] * 1.3:
            scores["migrating"] += 0.6

        # --- Hunting ---
        # High turning rate + speed variance are hallmarks of a hunt
        if tr >= t["turning_hunting_min"] and sv >= t["speed_var_hunting_min"]:
            scores["hunting"] += 1.0
            if ms > t["speed_resting_max"] * 3:
                scores["hunting"] += 0.5
        elif tr >= t["turning_hunting_min"] * 0.7:
            scores["hunting"] += 0.4

        return scores
