# Wildlife Monitoring System - Trajectory Analyzer
"""
TrajectoryAnalyzer: extracts kinematic features from a sequence of
(x, y[, confidence]) observations for use by the BehaviorClassifier.

Features computed
-----------------
mean_speed          – mean Euclidean displacement per frame
speed_variance      – variance of per-frame speeds
mean_acceleration   – mean absolute change in speed per frame
mean_turning_rate   – mean absolute change in heading direction (radians)
path_straightness   – 1 − (straight-line distance / path length), i.e.
                      0 = perfectly straight, 1 = completely random
num_points          – number of input observations
"""
from __future__ import annotations

import math
import logging
from typing import List, Dict, Any

import numpy as np

logger = logging.getLogger(__name__)


class TrajectoryAnalyzer:
    """Extracts kinematic features from a list of coordinate dicts."""

    @staticmethod
    def extract_features(points: List[Dict[str, float]]) -> Dict[str, float]:
        """
        Compute trajectory features.

        Parameters
        ----------
        points : list of dict
            Each entry must contain ``x`` and ``y`` (floats).  An optional
            ``confidence`` key is accepted but not required.

        Returns
        -------
        dict of feature name → float value.  Returns zeros for all features
        when fewer than two points are provided.
        """
        n = len(points)
        empty = {
            "mean_speed": 0.0,
            "speed_variance": 0.0,
            "mean_acceleration": 0.0,
            "mean_turning_rate": 0.0,
            "path_straightness": 0.0,
            "num_points": float(n),
        }

        if n < 2:
            return empty

        xs = np.array([p["x"] for p in points], dtype=np.float64)
        ys = np.array([p["y"] for p in points], dtype=np.float64)

        # Per-frame displacement
        dx = np.diff(xs)
        dy = np.diff(ys)
        speeds = np.sqrt(dx ** 2 + dy ** 2)  # (n-1,)

        mean_speed = float(np.mean(speeds))
        speed_variance = float(np.var(speeds))

        # Acceleration = change in speed magnitude
        if len(speeds) > 1:
            mean_acceleration = float(np.mean(np.abs(np.diff(speeds))))
        else:
            mean_acceleration = 0.0

        # Heading angles and turning rate
        headings = np.arctan2(dy, dx)  # (n-1,)
        if len(headings) > 1:
            turning = np.diff(headings)
            # Wrap to [-π, π]
            turning = (turning + math.pi) % (2 * math.pi) - math.pi
            mean_turning_rate = float(np.mean(np.abs(turning)))
        else:
            mean_turning_rate = 0.0

        # Path straightness
        path_length = float(np.sum(speeds))
        straight_dist = math.sqrt((xs[-1] - xs[0]) ** 2 + (ys[-1] - ys[0]) ** 2)
        if path_length > 0:
            path_straightness = 1.0 - min(straight_dist / path_length, 1.0)
        else:
            path_straightness = 0.0

        return {
            "mean_speed": mean_speed,
            "speed_variance": speed_variance,
            "mean_acceleration": mean_acceleration,
            "mean_turning_rate": mean_turning_rate,
            "path_straightness": path_straightness,
            "num_points": float(n),
        }

    @staticmethod
    def detect_migration_pattern(
        trajectories_by_day: Dict[str, List[Dict[str, float]]]
    ) -> Dict[str, Any]:
        """
        Identify long-term migration trends from multi-day trajectory data.

        Parameters
        ----------
        trajectories_by_day : dict
            Mapping of ISO date string → list of (x, y) point dicts, ordered
            chronologically.

        Returns
        -------
        dict with keys:
            ``is_migrating``   – bool
            ``net_displacement`` – Euclidean distance between first and last
                                   observed centroid
            ``direction_degrees`` – bearing (0 = north/up, clockwise)
            ``daily_centroids`` – list of {date, cx, cy} dicts
        """
        daily_centroids: List[Dict[str, Any]] = []
        for date in sorted(trajectories_by_day.keys()):
            pts = trajectories_by_day[date]
            if not pts:
                continue
            cx = float(np.mean([p["x"] for p in pts]))
            cy = float(np.mean([p["y"] for p in pts]))
            daily_centroids.append({"date": date, "cx": cx, "cy": cy})

        if len(daily_centroids) < 2:
            return {
                "is_migrating": False,
                "net_displacement": 0.0,
                "direction_degrees": 0.0,
                "daily_centroids": daily_centroids,
            }

        first = daily_centroids[0]
        last = daily_centroids[-1]
        ddx = last["cx"] - first["cx"]
        ddy = last["cy"] - first["cy"]
        net_displacement = float(math.sqrt(ddx ** 2 + ddy ** 2))

        # Bearing: atan2(dx, -dy) so that "up" (negative y in image coords) → 0°
        direction_degrees = float(math.degrees(math.atan2(ddx, -ddy)) % 360)

        # Heuristic: migrating if net displacement is > 20 % of total path length
        total_path = sum(
            math.sqrt((daily_centroids[i + 1]["cx"] - daily_centroids[i]["cx"]) ** 2
                      + (daily_centroids[i + 1]["cy"] - daily_centroids[i]["cy"]) ** 2)
            for i in range(len(daily_centroids) - 1)
        )
        is_migrating = total_path > 0 and (net_displacement / total_path) > 0.20

        return {
            "is_migrating": is_migrating,
            "net_displacement": round(net_displacement, 4),
            "direction_degrees": round(direction_degrees, 2),
            "daily_centroids": daily_centroids,
        }
