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
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.database import Alert, Detection, db, init_db

logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="dashboard/templates", static_folder="dashboard/static")

    db_url = os.getenv("DATABASE_URL", "sqlite:///wildlife.db")
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "change-me-in-production")

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
            since = datetime.utcnow() - timedelta(days=days)
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
        since = datetime.utcnow() - timedelta(days=days)

        total = Detection.query.filter(Detection.timestamp >= since).count()
        unresolved_alerts = Alert.query.filter(Alert.resolved == False).count()

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
        since = datetime.utcnow() - timedelta(days=days)

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

    return app


app = create_app()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    app.run(debug=os.getenv("FLASK_DEBUG", "false").lower() == "true", host="0.0.0.0", port=5000)
