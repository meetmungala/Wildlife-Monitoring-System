# tests/test_behavior_predictor.py
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.behavior_predictor import LSTMPredictor


def make_points(n=15):
    return [{"x": float(i) * 0.05, "y": float(i) * 0.03, "confidence": 0.9} for i in range(n)]


class TestLSTMPredictor:

    def setup_method(self):
        self.predictor = LSTMPredictor(weights_path=None, seq_len=10, forecast_horizon=5)

    # ── Return structure ───────────────────────────────────────────────

    def test_returns_expected_keys(self):
        result = self.predictor.predict(make_points())
        assert {"predicted_positions", "confidence"}.issubset(result.keys())

    def test_predicted_positions_count(self):
        result = self.predictor.predict(make_points())
        assert len(result["predicted_positions"]) == 5

    def test_each_position_has_x_y_confidence(self):
        result = self.predictor.predict(make_points())
        for pos in result["predicted_positions"]:
            assert "x" in pos and "y" in pos and "confidence" in pos

    def test_confidence_in_range(self):
        result = self.predictor.predict(make_points())
        assert 0.0 <= result["confidence"] <= 1.0
        for pos in result["predicted_positions"]:
            assert 0.0 <= pos["confidence"] <= 1.0

    # ── Edge cases ─────────────────────────────────────────────────────

    def test_single_point_returns_empty(self):
        result = self.predictor.predict([{"x": 0.5, "y": 0.5}])
        assert result["predicted_positions"] == []
        assert result["confidence"] == 0.0

    def test_empty_input_returns_empty(self):
        result = self.predictor.predict([])
        assert result["predicted_positions"] == []

    def test_short_sequence_padded(self):
        """Fewer points than seq_len should still produce predictions."""
        result = self.predictor.predict(make_points(3))
        assert len(result["predicted_positions"]) == 5

    def test_long_sequence_trimmed(self):
        """More points than seq_len should still produce predictions."""
        result = self.predictor.predict(make_points(50))
        assert len(result["predicted_positions"]) == 5

    def test_missing_confidence_key(self):
        pts = [{"x": float(i) * 0.05, "y": 0.5} for i in range(10)]
        result = self.predictor.predict(pts)
        assert len(result["predicted_positions"]) == 5

    def test_confidence_decays_with_horizon(self):
        result = self.predictor.predict(make_points())
        confs = [p["confidence"] for p in result["predicted_positions"]]
        # Each step should be <= the previous (monotonically non-increasing)
        for i in range(1, len(confs)):
            assert confs[i] <= confs[i - 1] + 1e-9

    def test_nonexistent_weights_path_fallback(self):
        """Loading a non-existent weights file should not raise."""
        pred = LSTMPredictor(weights_path="/tmp/nonexistent_weights.pt")
        result = pred.predict(make_points())
        assert "predicted_positions" in result

    def test_deterministic_with_eval_mode(self):
        """Two calls with the same input should return the same positions."""
        pts = make_points()
        r1 = self.predictor.predict(pts)
        r2 = self.predictor.predict(pts)
        assert r1["predicted_positions"] == r2["predicted_positions"]
