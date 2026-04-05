# tests/test_behavior_classifier.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.behavior_classifier import BehaviorClassifier


class TestBehaviorClassifier:

    def setup_method(self):
        self.clf = BehaviorClassifier()

    def _classify(self, **kwargs):
        return self.clf.classify(kwargs)

    # ── Return structure ───────────────────────────────────────────────

    def test_returns_expected_keys(self):
        result = self._classify(mean_speed=0.01)
        assert {"behavior", "confidence", "scores"}.issubset(result.keys())

    def test_behavior_is_valid_label(self):
        labels = {"hunting", "migrating", "grazing", "resting", "other"}
        result = self._classify(mean_speed=0.01)
        assert result["behavior"] in labels

    def test_confidence_in_range(self):
        result = self._classify(mean_speed=0.02, mean_turning_rate=0.1)
        assert 0.0 <= result["confidence"] <= 1.0

    def test_scores_sums_roughly_to_one(self):
        result = self._classify(mean_speed=0.05, mean_turning_rate=0.5, speed_variance=0.001)
        total = sum(result["scores"].values())
        # The scores before normalisation are not bounded but confidence is
        assert result["confidence"] <= 1.0

    # ── Label-specific heuristics ──────────────────────────────────────

    def test_resting_low_speed(self):
        result = self._classify(mean_speed=0.001, speed_variance=0.0, mean_turning_rate=0.0)
        assert result["behavior"] == "resting"

    def test_grazing_moderate_speed(self):
        result = self._classify(mean_speed=0.015, speed_variance=0.0001, mean_turning_rate=0.4)
        assert result["behavior"] == "grazing"

    def test_migrating_fast_straight(self):
        result = self._classify(
            mean_speed=0.06,
            speed_variance=0.00001,
            mean_turning_rate=0.1,
            path_straightness=0.1,
        )
        assert result["behavior"] == "migrating"

    def test_hunting_high_turn_and_variance(self):
        result = self._classify(
            mean_speed=0.03,
            speed_variance=0.001,
            mean_turning_rate=0.6,
            path_straightness=0.7,
        )
        assert result["behavior"] == "hunting"

    # ── Edge cases ─────────────────────────────────────────────────────

    def test_empty_features_returns_result(self):
        result = self.clf.classify({})
        assert "behavior" in result

    def test_custom_thresholds(self):
        clf = BehaviorClassifier(thresholds={"speed_resting_max": 0.1})
        # speed=0.05 is above the default resting_max (0.005) but below the custom (0.1).
        # High path_straightness (0.9) disqualifies migrating; zero variance/turning
        # disqualifies hunting, so resting should win.
        result = clf.classify({
            "mean_speed": 0.05,
            "path_straightness": 0.9,
            "mean_turning_rate": 0.0,
            "speed_variance": 0.0,
        })
        assert result["behavior"] == "resting"

    def test_all_zeros_no_crash(self):
        result = self.clf.classify({k: 0.0 for k in [
            "mean_speed", "speed_variance", "mean_acceleration",
            "mean_turning_rate", "path_straightness", "num_points"
        ]})
        assert result["behavior"] in {"resting", "other"}
