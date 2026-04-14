# Wildlife Monitoring System - Flask Application
"""
Main Flask application providing the REST API and web dashboard.

Run:
    python app.py
    or
    flask --app app run --debug
"""
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database import Alert, AlertRule, AnimalTrajectory, BehaviorPrediction, PredictedAlert, Detection, db, init_db

logger = logging.getLogger(__name__)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, template_folder="dashboard/templates", static_folder="dashboard/static")

    db_url = os.getenv("DATABASE_URL", "sqlite:///wildlife.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")

    if test_config:
        app.config.update(test_config)

    init_db(app)

    # ------------------------------------------------------------------ #
    #  Dashboard routes
    # ------------------------------------------------------------------ #

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/dashboard")
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/logs")
    def logs_page():
        return render_template("logs.html")

    @app.route("/predictions")
    def predictions_page():
        return render_template("predictions.html")

    @app.route("/heatmap")
    def heatmap_page():
        return render_template("heatmap.html")

    # ------------------------------------------------------------------ #
    #  REST API - Health
    # ------------------------------------------------------------------ #

    @app.route("/api/health", methods=["GET"])
    def health():
        """Simple liveness probe."""
        return jsonify({"status": "ok"})

    # ------------------------------------------------------------------ #
    #  REST API - Detections
    # ------------------------------------------------------------------ #

    @app.route("/api/detections", methods=["GET"])
    def get_detections():
        species = request.args.get("species")
        days = request.args.get("days", type=int)
        limit = request.args.get("limit", 100, type=int)
        page = request.args.get("page", 1, type=int)

        query = Detection.query.order_by(Detection.timestamp.desc())

        if species:
            query = query.filter(Detection.species.ilike(f"%{species}%"))
        if days:
            since = datetime.now(timezone.utc) - timedelta(days=days)
            query = query.filter(Detection.timestamp >= since)

        paginated = query.paginate(page=page, per_page=limit, error_out=False)
        return jsonify({
            "detections": [d.to_dict() for d in paginated.items],
            "total": paginated.total,
            "page": paginated.page,
            "pages": paginated.pages,
        })

    @app.route("/api/detections/<int:det_id>", methods=["GET"])
    def get_detection(det_id):
        det = db.get_or_404(Detection, det_id)
        return jsonify(det.to_dict())

    @app.route("/api/detections/<int:det_id>", methods=["DELETE"])
    def delete_detection(det_id):
        det = db.get_or_404(Detection, det_id)
        db.session.delete(det)
        db.session.commit()
        return jsonify({"deleted": True, "id": det_id})

    @app.route("/api/detections", methods=["POST"])
    def create_detection():
        data = request.get_json(force=True)
        required = {"species", "confidence"}
        if not required.issubset(data):
            return jsonify({"error": f"Missing fields: {required - set(data)}"}), 400

        det = Detection(
            species=data["species"],
            confidence=float(data["confidence"]),
            location=data.get("location"),
            latitude=data.get("latitude"),
            longitude=data.get("longitude"),
            source=data.get("source"),
            image_path=data.get("image_path"),
            bbox_x1=data.get("bbox_x1"),
            bbox_y1=data.get("bbox_y1"),
            bbox_x2=data.get("bbox_x2"),
            bbox_y2=data.get("bbox_y2"),
        )
        db.session.add(det)
        db.session.commit()
        return jsonify(det.to_dict()), 201

    # ------------------------------------------------------------------ #
    #  REST API - Alerts
    # ------------------------------------------------------------------ #

    @app.route("/api/alerts", methods=["GET"])
    def get_alerts():
        resolved = request.args.get("resolved")
        limit = request.args.get("limit", 50, type=int)
        query = Alert.query.order_by(Alert.timestamp.desc())
        if resolved is not None:
            query = query.filter(Alert.resolved == (resolved.lower() == "true"))
        alerts = query.limit(limit).all()
        return jsonify({"alerts": [a.to_dict() for a in alerts]})

    @app.route("/api/alerts/<int:alert_id>/resolve", methods=["PATCH"])
    def resolve_alert(alert_id):
        alert = db.get_or_404(Alert, alert_id)
        alert.resolved = True
        db.session.commit()
        return jsonify(alert.to_dict())

    # ------------------------------------------------------------------ #
    #  REST API - Analytics
    # ------------------------------------------------------------------ #

    @app.route("/api/analytics/summary", methods=["GET"])
    def analytics_summary():
        days = request.args.get("days", 7, type=int)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        total = Detection.query.filter(Detection.timestamp >= since).count()
        unresolved_alerts = Alert.query.filter(Alert.resolved.is_(False)).count()

        species_counts = (
            db.session.query(Detection.species, db.func.count(Detection.id).label("count"))
            .filter(Detection.timestamp >= since)
            .group_by(Detection.species)
            .order_by(db.func.count(Detection.id).desc())
            .all()
        )

        recent = (
            Detection.query
            .filter(Detection.timestamp >= since)
            .order_by(Detection.timestamp.desc())
            .limit(10)
            .all()
        )

        return jsonify({
            "period_days": days,
            "total_detections": total,
            "unresolved_alerts": unresolved_alerts,
            "species_counts": [{"species": s, "count": c} for s, c in species_counts],
            "recent_detections": [d.to_dict() for d in recent],
        })

    @app.route("/api/analytics/timeline", methods=["GET"])
    def analytics_timeline():
        days = request.args.get("days", 7, type=int)
        since = datetime.now(timezone.utc) - timedelta(days=days)

        rows = (
            db.session.query(
                db.func.date(Detection.timestamp).label("date"),
                Detection.species,
                db.func.count(Detection.id).label("count"),
            )
            .filter(Detection.timestamp >= since)
            .group_by(db.func.date(Detection.timestamp), Detection.species)
            .order_by(db.func.date(Detection.timestamp))
            .all()
        )

        return jsonify({
            "timeline": [{"date": str(r.date), "species": r.species, "count": r.count} for r in rows]
        })

    # ------------------------------------------------------------------ #
    #  REST API - Trajectories
    # ------------------------------------------------------------------ #

    @app.route("/api/trajectories", methods=["POST"])
    def create_trajectory_point():
        data = request.get_json(force=True)
        required = {"animal_id", "species", "x", "y"}
        if not required.issubset(data):
            return jsonify({"error": f"Missing fields: {required - set(data)}"}), 400

        point = AnimalTrajectory(
            animal_id=data["animal_id"],
            species=data["species"],
            x=float(data["x"]),
            y=float(data["y"]),
            confidence=data.get("confidence"),
            frame_index=data.get("frame_index"),
            detection_id=data.get("detection_id"),
        )
        db.session.add(point)
        db.session.commit()
        return jsonify(point.to_dict()), 201

    @app.route("/api/trajectories/<animal_id>", methods=["GET"])
    def get_trajectory(animal_id):
        limit = request.args.get("limit", 100, type=int)
        hours = request.args.get("hours", type=int)
        query = (
            AnimalTrajectory.query
            .filter(AnimalTrajectory.animal_id == animal_id)
            .order_by(AnimalTrajectory.timestamp.desc())
        )
        if hours:
            since = datetime.now(timezone.utc) - timedelta(hours=hours)
            query = query.filter(AnimalTrajectory.timestamp >= since)
        points = query.limit(limit).all()
        return jsonify({
            "animal_id": animal_id,
            "points": [p.to_dict() for p in reversed(points)],
        })

    # ------------------------------------------------------------------ #
    #  REST API - Heatmap Analytics
    # ------------------------------------------------------------------ #

    @app.route("/api/analytics/heatmap", methods=["GET"])
    def analytics_heatmap():
        """Get heatmap data for animal movement visualization."""
        days = request.args.get("days", 30, type=int)
        species = request.args.get("species")
        since = datetime.now(timezone.utc) - timedelta(days=days)

        query = AnimalTrajectory.query.filter(AnimalTrajectory.timestamp >= since)

        if species:
            query = query.filter(AnimalTrajectory.species.ilike(f"%{species}%"))

        points = query.all()

        # Aggregate movement data
        heatmap_data = []
        for point in points:
            heatmap_data.append({
                "x": point.x,
                "y": point.y,
                "species": point.species,
                "timestamp": point.timestamp.isoformat(),
            })

        # Calculate activity zones (most active areas)
        activity_zones = {}
        for point in points:
            # Grid-based aggregation (10x10 grid cells)
            grid_x = int(point.x / 10) * 10
            grid_y = int(point.y / 10) * 10
            key = f"{grid_x},{grid_y}"
            if key not in activity_zones:
                activity_zones[key] = {"x": grid_x, "y": grid_y, "count": 0, "species": {}}
            activity_zones[key]["count"] += 1
            species_name = point.species
            activity_zones[key]["species"][species_name] = activity_zones[key]["species"].get(species_name, 0) + 1

        # Get top active areas
        top_zones = sorted(activity_zones.values(), key=lambda z: z["count"], reverse=True)[:10]

        # Calculate migration routes (simplified path analysis)
        migration_routes = {}
        for point in points:
            animal_key = f"{point.animal_id}_{point.species}"
            if animal_key not in migration_routes:
                migration_routes[animal_key] = []
            migration_routes[animal_key].append({
                "x": point.x,
                "y": point.y,
                "timestamp": point.timestamp.isoformat(),
            })

        # Get species statistics
        species_stats = (
            db.session.query(
                AnimalTrajectory.species,
                db.func.count(AnimalTrajectory.id).label("point_count"),
                db.func.count(db.func.distinct(AnimalTrajectory.animal_id)).label("animal_count"),
            )
            .filter(AnimalTrajectory.timestamp >= since)
            .group_by(AnimalTrajectory.species)
            .all()
        )

        return jsonify({
            "period_days": days,
            "total_points": len(points),
            "heatmap_data": heatmap_data,
            "top_active_areas": top_zones,
            "species_stats": [
                {
                    "species": s.species,
                    "point_count": s.point_count,
                    "animal_count": s.animal_count,
                }
                for s in species_stats
            ],
        })

    # ------------------------------------------------------------------ #
    #  REST API - Behavior Predictions
    # ------------------------------------------------------------------ #

    def _get_prediction_service():
        """Lazily initialise and cache the PredictionService on the app."""
        if not hasattr(app, "_prediction_service"):
            from src.behavior_classifier import BehaviorClassifier
            from src.behavior_predictor import LSTMPredictor
            from src.prediction_service import PredictionService
            from src.trajectory_analyzer import TrajectoryAnalyzer
            app._prediction_service = PredictionService(
                db=db,
                classifier=BehaviorClassifier(),
                predictor=LSTMPredictor(),
                analyzer=TrajectoryAnalyzer,
            )
        return app._prediction_service

    @app.route("/api/predictions/run", methods=["POST"])
    def run_prediction():
        data = request.get_json(force=True)
        required = {"animal_id", "species"}
        if not required.issubset(data):
            return jsonify({"error": f"Missing fields: {required - set(data)}"}), 400
        svc = _get_prediction_service()
        result = svc.run(data["animal_id"], data["species"])
        status = 200 if "error" not in result else 422
        return jsonify(result), status

    @app.route("/api/predictions", methods=["GET"])
    def list_predictions():
        limit = request.args.get("limit", 50, type=int)
        animal_id = request.args.get("animal_id")
        query = BehaviorPrediction.query.order_by(BehaviorPrediction.timestamp.desc())
        if animal_id:
            query = query.filter(BehaviorPrediction.animal_id == animal_id)
        preds = query.limit(limit).all()
        return jsonify({"predictions": [p.to_dict() for p in preds]})

    @app.route("/api/predictions/<int:pred_id>", methods=["GET"])
    def get_prediction(pred_id):
        pred = db.get_or_404(BehaviorPrediction, pred_id)
        return jsonify(pred.to_dict())

    # ------------------------------------------------------------------ #
    #  REST API - Alert Rules
    # ------------------------------------------------------------------ #

    @app.route("/api/alert-rules", methods=["GET"])
    def list_alert_rules():
        rules = AlertRule.query.order_by(AlertRule.created_at.desc()).all()
        return jsonify({"alert_rules": [r.to_dict() for r in rules]})

    @app.route("/api/alert-rules", methods=["POST"])
    def create_alert_rule():
        data = request.get_json(force=True)
        if not data.get("name"):
            return jsonify({"error": "Missing required field: name"}), 400
        zone = data.get("zone", {})
        rule = AlertRule(
            name=data["name"],
            species=data.get("species"),
            behavior=data.get("behavior"),
            zone_x1=zone.get("x1"),
            zone_y1=zone.get("y1"),
            zone_x2=zone.get("x2"),
            zone_y2=zone.get("y2"),
            min_confidence=float(data.get("min_confidence", 0.5)),
            active=bool(data.get("active", True)),
        )
        db.session.add(rule)
        db.session.commit()
        return jsonify(rule.to_dict()), 201

    @app.route("/api/alert-rules/<int:rule_id>", methods=["PATCH"])
    def update_alert_rule(rule_id):
        rule = db.get_or_404(AlertRule, rule_id)
        data = request.get_json(force=True)
        for field in ("name", "species", "behavior", "min_confidence", "active"):
            if field in data:
                setattr(rule, field, data[field])
        if "zone" in data:
            z = data["zone"]
            rule.zone_x1, rule.zone_y1 = z.get("x1"), z.get("y1")
            rule.zone_x2, rule.zone_y2 = z.get("x2"), z.get("y2")
        db.session.commit()
        return jsonify(rule.to_dict())

    # ------------------------------------------------------------------ #
    #  REST API - Predicted Alerts
    # ------------------------------------------------------------------ #

    @app.route("/api/predicted-alerts", methods=["GET"])
    def list_predicted_alerts():
        resolved = request.args.get("resolved")
        limit = request.args.get("limit", 50, type=int)
        query = PredictedAlert.query.order_by(PredictedAlert.timestamp.desc())
        if resolved is not None:
            query = query.filter(PredictedAlert.resolved == (resolved.lower() == "true"))
        alerts = query.limit(limit).all()
        return jsonify({"predicted_alerts": [a.to_dict() for a in alerts]})

    @app.route("/api/predicted-alerts/<int:alert_id>/resolve", methods=["PATCH"])
    def resolve_predicted_alert(alert_id):
        alert = db.get_or_404(PredictedAlert, alert_id)
        alert.resolved = True
        db.session.commit()
        return jsonify(alert.to_dict())

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", host="0.0.0.0", port=5000)
