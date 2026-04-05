# Wildlife Monitoring System - LSTM Movement Predictor
"""
LSTMPredictor: predicts the next N animal positions from a sequence of
historical (x, y, confidence) observations.

Architecture: two-layer LSTM with an optional attention readout, followed by
a linear projection to the output coordinates.

Usage without pre-trained weights (demo / smoke-test):
    predictor = LSTMPredictor()
    points = [{"x": float, "y": float, "confidence": float}, ...]
    result = predictor.predict(points)
    # result["predicted_positions"]  →  list of {x, y, confidence} dicts
    # result["confidence"]           →  overall prediction confidence (0–1)
"""
from __future__ import annotations

import logging
import math
from typing import List, Dict, Any

import numpy as np
import torch
import torch.nn as nn

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
#  Model definition
# ------------------------------------------------------------------ #

INPUT_SIZE = 3    # (x, y, confidence) per timestep
HIDDEN_SIZE = 64
NUM_LAYERS = 2
OUTPUT_SIZE = 2   # predicted (x, y)


class _AttentionLSTM(nn.Module):
    """Two-layer LSTM with a simple additive attention mechanism."""

    def __init__(self, input_size: int, hidden_size: int, num_layers: int, output_size: int):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_size,
            hidden_size=hidden_size,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.1 if num_layers > 1 else 0.0,
        )
        self.attention = nn.Linear(hidden_size, 1)
        self.fc = nn.Linear(hidden_size, output_size)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (batch, seq_len, input_size)
        lstm_out, _ = self.lstm(x)                    # (batch, seq_len, hidden)
        attn_weights = torch.softmax(self.attention(lstm_out), dim=1)  # (batch, seq_len, 1)
        context = (attn_weights * lstm_out).sum(dim=1)                  # (batch, hidden)
        return self.fc(context)                         # (batch, output_size)


# ------------------------------------------------------------------ #
#  Public API
# ------------------------------------------------------------------ #

class LSTMPredictor:
    """
    Wraps ``_AttentionLSTM`` and exposes a simple ``predict`` method.

    Parameters
    ----------
    weights_path : str | None
        Path to a saved ``state_dict`` (``torch.save``).  When *None* the
        model runs with random weights (useful for integration testing).
    seq_len : int
        Number of historical frames fed as input (default 30).
    forecast_horizon : int
        Number of future frames to predict (default 10).
    """

    def __init__(
        self,
        weights_path: str | None = None,
        seq_len: int = 30,
        forecast_horizon: int = 10,
    ) -> None:
        self.seq_len = seq_len
        self.forecast_horizon = forecast_horizon
        self.device = torch.device("cpu")

        self.model = _AttentionLSTM(INPUT_SIZE, HIDDEN_SIZE, NUM_LAYERS, OUTPUT_SIZE)
        self.model.eval()

        if weights_path:
            try:
                state = torch.load(weights_path, map_location=self.device)
                self.model.load_state_dict(state)
                logger.info("Loaded LSTM weights from %s", weights_path)
            except Exception as exc:
                logger.warning("Could not load weights from %s: %s — using random init", weights_path, exc)

    # ------------------------------------------------------------------ #

    def _normalise(self, points: List[Dict[str, float]]) -> tuple[np.ndarray, float, float, float, float]:
        """Centre and scale the coordinate sequence to [-1, 1]."""
        xs = np.array([p["x"] for p in points], dtype=np.float32)
        ys = np.array([p["y"] for p in points], dtype=np.float32)
        cs = np.array([p.get("confidence", 1.0) for p in points], dtype=np.float32)

        x_mean, y_mean = float(xs.mean()), float(ys.mean())
        scale = max(float(xs.max() - xs.min()), float(ys.max() - ys.min()), 1e-6)

        xs_n = (xs - x_mean) / scale
        ys_n = (ys - y_mean) / scale

        seq = np.stack([xs_n, ys_n, cs], axis=-1)  # (T, 3)
        return seq, x_mean, y_mean, scale

    def _build_input(self, points: List[Dict[str, float]]) -> torch.Tensor:
        """Pad / trim to ``self.seq_len`` and return a (1, seq_len, 3) tensor."""
        seq, x_mean, y_mean, scale = self._normalise(points)
        n = len(seq)
        target_len = self.seq_len

        if n >= target_len:
            seq = seq[-target_len:]
        else:
            pad = np.zeros((target_len - n, seq.shape[1]), dtype=np.float32)
            seq = np.concatenate([pad, seq], axis=0)

        tensor = torch.from_numpy(seq).unsqueeze(0)  # (1, seq_len, 3)
        return tensor, x_mean, y_mean, scale

    # ------------------------------------------------------------------ #

    def predict(self, points: List[Dict[str, float]]) -> Dict[str, Any]:
        """
        Generate movement predictions from a list of coordinate observations.

        Parameters
        ----------
        points : list of dict
            Each dict must have ``x`` and ``y`` keys (floats).  An optional
            ``confidence`` key (0–1) may be provided.

        Returns
        -------
        dict with keys:
            ``predicted_positions`` – list of ``forecast_horizon`` dicts, each
            with ``x``, ``y``, and ``confidence``.
            ``confidence`` – scalar (0–1) summarising overall prediction quality.
        """
        if len(points) < 2:
            return {"predicted_positions": [], "confidence": 0.0}

        tensor, x_mean, y_mean, scale = self._build_input(points)

        predicted_positions = []
        with torch.no_grad():
            # Autoregressively generate forecast_horizon steps.
            # The model's single forward pass predicts one (dx, dy) step;
            # we roll the window forward for each future frame.
            current_input = tensor.clone()  # (1, seq_len, 3)
            last_conf = float(points[-1].get("confidence", 1.0))

            # Retrieve the last normalised position as the "current" anchor.
            seq_np = tensor[0].numpy()  # (seq_len, 3)
            cur_x_n = float(seq_np[-1, 0])
            cur_y_n = float(seq_np[-1, 1])

            for step in range(self.forecast_horizon):
                delta = self.model(current_input)  # (1, 2)
                dx, dy = float(delta[0, 0]), float(delta[0, 1])

                cur_x_n += dx * 0.05  # dampen raw deltas for stability
                cur_y_n += dy * 0.05

                # Denormalise back to original coordinate space
                pred_x = cur_x_n * scale + x_mean
                pred_y = cur_y_n * scale + y_mean

                # Decay confidence with horizon distance
                step_conf = max(0.0, last_conf * math.exp(-0.08 * step))

                predicted_positions.append({
                    "x": round(pred_x, 4),
                    "y": round(pred_y, 4),
                    "confidence": round(step_conf, 4),
                })

                # Slide the window: drop oldest frame, append new prediction
                new_frame = torch.tensor([[[cur_x_n, cur_y_n, step_conf]]])
                current_input = torch.cat([current_input[:, 1:, :], new_frame], dim=1)

        avg_conf = float(np.mean([p["confidence"] for p in predicted_positions])) if predicted_positions else 0.0
        return {
            "predicted_positions": predicted_positions,
            "confidence": round(avg_conf, 4),
        }
