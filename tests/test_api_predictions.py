# tests/test_api_predictions.py
"""Integration tests for the prediction REST API endpoints."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(test_config={
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path}/test.db",
    })
    with app.test_client() as c:
        yield c


# ── Trajectory endpoints ───────────────────────────────────────────────

class TestTrajectoryEndpoints:

    def test_create_trajectory_point(self, client):
        resp = client.post("/api/trajectories", json={
            "animal_id": "tiger-001", "species": "tiger",
            "x": 0.4, "y": 0.6, "confidence": 0.9,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["animal_id"] == "tiger-001"
        assert data["x"] == 0.4

    def test_create_trajectory_missing_fields(self, client):
        resp = client.post("/api/trajectories", json={"animal_id": "tiger-001"})
        assert resp.status_code == 400

    def test_get_trajectory_empty(self, client):
        resp = client.get("/api/trajectories/unknown-animal")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["points"] == []

    def test_get_trajectory_returns_points(self, client):
        for i in range(3):
            client.post("/api/trajectories", json={
                "animal_id": "elephant-001", "species": "elephant",
                "x": float(i) * 0.1, "y": 0.5,
            })
        resp = client.get("/api/trajectories/elephant-001")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["points"]) == 3


# ── Alert rules endpoints ──────────────────────────────────────────────

class TestAlertRuleEndpoints:

    def test_list_rules_empty(self, client):
        resp = client.get("/api/alert-rules")
        assert resp.status_code == 200
        assert resp.get_json()["alert_rules"] == []

    def test_create_rule(self, client):
        resp = client.post("/api/alert-rules", json={
            "name": "Tiger near village",
            "species": "tiger",
            "behavior": "hunting",
            "min_confidence": 0.6,
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["name"] == "Tiger near village"
        assert data["active"] is True

    def test_create_rule_missing_name(self, client):
        resp = client.post("/api/alert-rules", json={"species": "tiger"})
        assert resp.status_code == 400

    def test_update_rule(self, client):
        create = client.post("/api/alert-rules", json={"name": "Test Rule"})
        rule_id = create.get_json()["id"]
        resp = client.patch(f"/api/alert-rules/{rule_id}", json={"active": False})
        assert resp.status_code == 200
        assert resp.get_json()["active"] is False

    def test_list_rules_after_creation(self, client):
        client.post("/api/alert-rules", json={"name": "Rule A"})
        client.post("/api/alert-rules", json={"name": "Rule B"})
        resp = client.get("/api/alert-rules")
        rules = resp.get_json()["alert_rules"]
        assert len(rules) == 2


# ── Predicted alerts endpoints ─────────────────────────────────────────

class TestPredictedAlertsEndpoints:

    def test_list_predicted_alerts_empty(self, client):
        resp = client.get("/api/predicted-alerts")
        assert resp.status_code == 200
        assert resp.get_json()["predicted_alerts"] == []


# ── Predictions list endpoint ──────────────────────────────────────────

class TestPredictionsListEndpoints:

    def test_list_predictions_empty(self, client):
        resp = client.get("/api/predictions")
        assert resp.status_code == 200
        assert resp.get_json()["predictions"] == []


# ── Run prediction endpoint ────────────────────────────────────────────

class TestRunPredictionEndpoint:

    def test_run_prediction_missing_fields(self, client):
        resp = client.post("/api/predictions/run", json={"animal_id": "tiger-001"})
        assert resp.status_code == 400

    def test_run_prediction_no_trajectory_returns_422(self, client):
        resp = client.post("/api/predictions/run", json={
            "animal_id": "no-data-animal", "species": "tiger"
        })
        # No trajectory data → service returns error key → 422
        assert resp.status_code == 422

    def test_run_prediction_with_trajectory_data(self, client):
        # Seed trajectory data
        animal_id = "tiger-test"
        for i in range(15):
            client.post("/api/trajectories", json={
                "animal_id": animal_id, "species": "tiger",
                "x": float(i) * 0.05, "y": 0.5, "confidence": 0.9,
            })
        resp = client.post("/api/predictions/run", json={
            "animal_id": animal_id, "species": "tiger",
        })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["animal_id"] == animal_id
        assert data["behavior"] in {"hunting", "migrating", "grazing", "resting", "other"}
        assert 0.0 <= data["confidence"] <= 1.0
        assert isinstance(data["predicted_positions"], list)
        assert data["prediction_id"] is not None

    def test_run_prediction_stored_in_list(self, client):
        animal_id = "elephant-test"
        for i in range(10):
            client.post("/api/trajectories", json={
                "animal_id": animal_id, "species": "elephant",
                "x": float(i) * 0.1, "y": float(i) * 0.05,
            })
        client.post("/api/predictions/run", json={
            "animal_id": animal_id, "species": "elephant"
        })
        resp = client.get(f"/api/predictions?animal_id={animal_id}")
        preds = resp.get_json()["predictions"]
        assert len(preds) >= 1
        assert preds[0]["animal_id"] == animal_id


# ── Predictions page route ─────────────────────────────────────────────

class TestPredictionsPageRoute:

    def test_predictions_page_returns_200(self, client):
        resp = client.get("/predictions")
        assert resp.status_code == 200
        assert b"Behavior Predictions" in resp.data


# ── Health endpoint ────────────────────────────────────────────────────

class TestHealthEndpoint:

    def test_health_returns_200(self, client):
        resp = client.get("/api/health")
        assert resp.status_code == 200

    def test_health_returns_ok_status(self, client):
        data = client.get("/api/health").get_json()
        assert data["status"] == "ok"


# ── Detection delete endpoint ──────────────────────────────────────────

class TestDetectionDeleteEndpoint:

    def _create_detection(self, client, species="lion", confidence=0.85):
        resp = client.post("/api/detections", json={
            "species": species,
            "confidence": confidence,
        })
        assert resp.status_code == 201
        return resp.get_json()["id"]

    def test_delete_detection_returns_200(self, client):
        det_id = self._create_detection(client)
        resp = client.delete(f"/api/detections/{det_id}")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["deleted"] is True
        assert data["id"] == det_id

    def test_delete_detection_removes_it(self, client):
        det_id = self._create_detection(client)
        client.delete(f"/api/detections/{det_id}")
        resp = client.get(f"/api/detections/{det_id}")
        assert resp.status_code == 404

    def test_delete_nonexistent_detection_returns_404(self, client):
        resp = client.delete("/api/detections/999999")
        assert resp.status_code == 404
