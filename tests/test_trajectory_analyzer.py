# tests/test_trajectory_analyzer.py
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.trajectory_analyzer import TrajectoryAnalyzer


# ── Helpers ──────────────────────────────────────────────────────────

def make_line(n=20, step=0.05):
    """Straight horizontal walk."""
    return [{"x": i * step, "y": 0.5} for i in range(n)]


def make_circle(n=30, radius=0.2, cx=0.5, cy=0.5):
    """Uniform circular path."""
    return [
        {"x": cx + radius * math.cos(2 * math.pi * i / n),
         "y": cy + radius * math.sin(2 * math.pi * i / n)}
        for i in range(n)
    ]


def make_stationary(n=20, x=0.5, y=0.5):
    return [{"x": x, "y": y} for _ in range(n)]


# ── Tests ─────────────────────────────────────────────────────────────

class TestExtractFeatures:

    def test_returns_all_keys(self):
        points = make_line()
        features = TrajectoryAnalyzer.extract_features(points)
        expected_keys = {
            "mean_speed", "speed_variance", "mean_acceleration",
            "mean_turning_rate", "path_straightness", "num_points",
        }
        assert expected_keys.issubset(features.keys())

    def test_empty_returns_zeros(self):
        features = TrajectoryAnalyzer.extract_features([])
        for key in ["mean_speed", "speed_variance", "path_straightness"]:
            assert features[key] == 0.0
        assert features["num_points"] == 0.0

    def test_single_point_returns_zeros(self):
        features = TrajectoryAnalyzer.extract_features([{"x": 0.5, "y": 0.5}])
        assert features["mean_speed"] == 0.0

    def test_stationary_low_speed(self):
        features = TrajectoryAnalyzer.extract_features(make_stationary())
        assert features["mean_speed"] < 1e-10
        assert features["path_straightness"] == 0.0

    def test_straight_line_low_straightness(self):
        features = TrajectoryAnalyzer.extract_features(make_line())
        # Path is straight → straightness ≈ 0
        assert features["path_straightness"] < 0.05

    def test_straight_line_low_turning(self):
        features = TrajectoryAnalyzer.extract_features(make_line())
        assert features["mean_turning_rate"] < 0.05

    def test_circle_higher_straightness(self):
        features = TrajectoryAnalyzer.extract_features(make_circle())
        # Circle ends where it started → high "tortuosity"
        assert features["path_straightness"] > 0.8

    def test_circle_higher_turning(self):
        features = TrajectoryAnalyzer.extract_features(make_circle())
        assert features["mean_turning_rate"] > 0.1

    def test_num_points_correct(self):
        pts = make_line(15)
        assert TrajectoryAnalyzer.extract_features(pts)["num_points"] == 15.0

    def test_missing_confidence_key_is_ignored(self):
        """Points without 'confidence' should not raise an error."""
        pts = [{"x": i * 0.1, "y": 0.0} for i in range(5)]
        features = TrajectoryAnalyzer.extract_features(pts)
        assert features["mean_speed"] > 0.0


class TestDetectMigrationPattern:

    def test_no_data_not_migrating(self):
        result = TrajectoryAnalyzer.detect_migration_pattern({})
        assert result["is_migrating"] is False
        assert result["net_displacement"] == 0.0

    def test_single_day_not_migrating(self):
        result = TrajectoryAnalyzer.detect_migration_pattern(
            {"2024-01-01": [{"x": 0.1, "y": 0.1}]}
        )
        assert result["is_migrating"] is False

    def test_straight_migration_detected(self):
        data = {
            "2024-01-01": [{"x": 0.0, "y": 0.5}],
            "2024-01-02": [{"x": 0.3, "y": 0.5}],
            "2024-01-03": [{"x": 0.6, "y": 0.5}],
            "2024-01-04": [{"x": 0.9, "y": 0.5}],
        }
        result = TrajectoryAnalyzer.detect_migration_pattern(data)
        assert result["is_migrating"] is True
        assert result["net_displacement"] > 0.5

    def test_looping_path_not_migrating(self):
        # Animal goes east then comes back to start
        data = {
            "2024-01-01": [{"x": 0.0, "y": 0.5}],
            "2024-01-02": [{"x": 0.5, "y": 0.5}],
            "2024-01-03": [{"x": 0.0, "y": 0.5}],
        }
        result = TrajectoryAnalyzer.detect_migration_pattern(data)
        assert result["is_migrating"] is False

    def test_daily_centroids_present(self):
        data = {
            "2024-01-01": [{"x": 0.0, "y": 0.0}, {"x": 0.1, "y": 0.1}],
        }
        result = TrajectoryAnalyzer.detect_migration_pattern(data)
        assert len(result["daily_centroids"]) == 1
        assert abs(result["daily_centroids"][0]["cx"] - 0.05) < 1e-6
