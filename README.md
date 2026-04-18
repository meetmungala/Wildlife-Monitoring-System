# Wildlife Monitoring System

![Language](https://img.shields.io/badge/Language-Python-3776AB.svg?logo=python&logoColor=white&labelColor=black)
![Language](https://img.shields.io/badge/Language-CSS-1572B6.svg?logo=css3&logoColor=white&labelColor=black)
![Language](https://img.shields.io/badge/Language-JavaScript-F7DF1E.svg?logo=javascript&logoColor=black&labelColor=black)
![Language](https://img.shields.io/badge/Language-HTML-E34F26.svg?logo=html5&logoColor=white&labelColor=black)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.0%2B-black?logo=flask)

## Overview
Wildlife Monitoring System is a Flask-based platform for wildlife observation and analytics. It combines species detection, trajectory tracking, behavior prediction, and a web dashboard to support conservation use cases.

## Features
- Real-time species detection pipeline (YOLOv8-based)
- Behavior prediction and movement trend analysis
- Detection logs and alert management
- Heatmap and activity-zone analytics
- REST API for detections, trajectories, alerts, and predictions
- Responsive dashboard pages for operations and monitoring

## Project Structure
```text
Wildlife-Monitoring-System/
├── app.py                  # Flask app factory, web routes, API routes
├── requirements.txt        # Python dependencies
├── dataset.yaml            # YOLO dataset config
├── .env.example            # Environment variable template
├── dashboard/
│   ├── templates/          # Jinja2 templates (home, dashboard, logs, predictions, heatmap)
│   └── static/             # CSS and JavaScript assets
├── src/                    # Core ML and analytics modules
└── tests/                  # Pytest test suite
```

## Requirements
- Python 3.10+
- pip

## Quick Start
1. Clone the repository
   ```bash
   git clone https://github.com/meetmungala/Wildlife-Monitoring-System.git
   cd Wildlife-Monitoring-System
   ```

2. (Optional) Create and activate a virtual environment
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

4. Configure environment variables
   ```bash
   cp .env.example .env
   ```

5. Run the app
   ```bash
   python app.py
   ```

The app starts at `http://localhost:5000`.

## Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///wildlife.db` | SQLAlchemy database URL |
| `SECRET_KEY` | `change-me-in-production` | Flask secret key |
| `FLASK_DEBUG` | `false` | Enables debug mode when set to `true` |

## Running Tests
```bash
python -m pytest tests/ -v
```

## API Endpoints
### Health
- `GET /api/health`

### Detections
- `GET /api/detections`
- `POST /api/detections`
- `GET /api/detections/<id>`
- `DELETE /api/detections/<id>`

### Alerts
- `GET /api/alerts`
- `PATCH /api/alerts/<id>/resolve`

### Analytics
- `GET /api/analytics/summary`
- `GET /api/analytics/timeline`
- `GET /api/analytics/heatmap`

### Trajectories
- `POST /api/trajectories`
- `GET /api/trajectories/<animal_id>`

### Predictions
- `POST /api/predictions/run`
- `GET /api/predictions`
- `GET /api/predictions/<id>`

### Alert Rules
- `GET /api/alert-rules`
- `POST /api/alert-rules`
- `PATCH /api/alert-rules/<id>`

### Predicted Alerts
- `GET /api/predicted-alerts`
- `PATCH /api/predicted-alerts/<id>/resolve`

## Contributing
1. Fork the repository
2. Create a branch (`git checkout -b feature/my-feature`)
3. Commit your changes
4. Open a pull request

## License
This project is licensed under the MIT License.
