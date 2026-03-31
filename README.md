# 🐾 Wildlife Monitoring System using YOLOv8

An AI-powered solution that detects and monitors endangered animal species in real-time using **YOLOv8** object detection, a **Flask** web dashboard, and a persistent detection database.

---

## 🚀 Features

| Feature | Details |
|---|---|
| 🎯 Real-time detection | YOLOv8 on live camera feeds or recorded video |
| 🐅 Species support | Tiger · Elephant · Rhinoceros · Snow Leopard |
| 🔔 Alert system | Console + DB alert when endangered species detected |
| 🗂️ Data logging | Timestamp, species, confidence, location, bounding box |
| 📊 Web dashboard | Analytics charts, detection logs, unresolved alerts |
| 🌙 Low-light mode | CLAHE enhancement for night-vision frames |

---

## 🛠️ Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.10+ |
| AI Model | YOLOv8 (Ultralytics) |
| Computer Vision | OpenCV · PyTorch |
| Backend | Flask + Flask-SQLAlchemy |
| Database | SQLite (default) · PostgreSQL · MongoDB |
| Frontend | Vanilla JS · Chart.js |
| Deployment | Local · Docker · AWS / GCP (optional) |

---

## 📂 Project Structure

```
Wildlife-Monitoring-System/
├── app.py                     # Flask application entry point
├── dataset.yaml               # YOLO dataset configuration
├── requirements.txt           # Python dependencies
├── .env.example               # Environment variable template
│
├── src/
│   ├── __init__.py
│   ├── detection.py           # Real-time YOLOv8 detection script
│   ├── train.py               # Model training script
│   ├── utils.py               # Drawing, logging, preprocessing helpers
│   ├── database.py            # SQLAlchemy models (Detection, Alert)
│   └── alerts.py              # Alert generation pipeline
│
├── dataset/                   # YOLO-format dataset
│   ├── images/
│   │   ├── train/
│   │   ├── val/
│   │   └── test/
│   └── labels/
│       ├── train/
│       ├── val/
│       └── test/
│
├── models/                    # Trained YOLOv8 weights
├── outputs/                   # Saved annotated detection frames
│
└── dashboard/
    ├── templates/
    │   ├── index.html         # Landing page
    │   ├── dashboard.html     # Analytics dashboard
    │   └── logs.html          # Detection logs & alerts
    └── static/
        ├── css/style.css
        └── js/
            ├── dashboard.js
            └── logs.js
```

---

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/your-username/Wildlife-Monitoring-System.git
cd Wildlife-Monitoring-System
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env to set SECRET_KEY, DATABASE_URL, etc.
```

---

## 📊 Dataset Preparation

Organise your images and YOLO-format annotation files under `dataset/`:

```
dataset/
  images/train/   <- training images (.jpg / .png)
  images/val/     <- validation images
  labels/train/   <- YOLO .txt annotation files
  labels/val/
```

Each `.txt` label file contains one detection per line:
```
<class_id> <cx> <cy> <width> <height>
```

Class mapping (defined in `dataset.yaml`):
```
0: tiger
1: elephant
2: rhinoceros
3: snow_leopard
```

Public datasets for endangered species: [iNaturalist](https://www.inaturalist.org/), [GBIF](https://www.gbif.org/), [Wildlife Insights](https://www.wildlifeinsights.org/).

---

## 🧠 Model Training

```bash
python src/train.py \
    --model yolov8n.pt \
    --data dataset.yaml \
    --epochs 50 \
    --imgsz 640 \
    --batch 16
```

Or via the Ultralytics CLI:

```bash
yolo task=detect mode=train model=yolov8n.pt data=dataset.yaml epochs=50 imgsz=640
```

Trained weights are saved to `models/wildlife_yolov8/weights/best.pt`.

---

## 🎥 Run Detection

### On a webcam (camera index 0)

```bash
python src/detection.py --source 0
```

### On a video file

```bash
python src/detection.py --source /path/to/video.mp4
```

### On an image or directory of images

```bash
python src/detection.py --source /path/to/image.jpg
python src/detection.py --source /path/to/images/
```

### With database logging and alerts

```bash
python src/detection.py --source 0 --log-db --location "Camera-Trap-A"
```

### Low-light / night vision enhancement

```bash
python src/detection.py --source 0 --low-light
```

### All options

```
--source        Source: 0 (webcam), file path, or directory
--weights       Path to trained weights (default: models/wildlife_yolov8/weights/best.pt)
--conf          Confidence threshold (default: 0.4)
--iou           IoU threshold (default: 0.45)
--imgsz         Inference image size (default: 640)
--device        Device: '' auto, 'cpu', '0' for GPU
--output        Output directory for saved frames (default: outputs/)
--no-save       Suppress saving annotated frames
--no-display    Suppress OpenCV window
--low-light     Apply CLAHE low-light enhancement
--location      Camera trap location label
--log-db        Log detections and alerts to the database
```

---

## 📈 Dashboard

Start the Flask server:

```bash
python app.py
```

Open [http://localhost:5000](http://localhost:5000) in your browser.

| URL | Description |
|---|---|
| `/` | Landing page |
| `/dashboard` | Analytics: species chart, 7-day timeline, recent detections |
| `/logs` | Full detection log with filters and alert panel |

### REST API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/detections` | List detections (filterable by species/days) |
| POST | `/api/detections` | Create detection record |
| GET | `/api/detections/<id>` | Get single detection |
| GET | `/api/alerts` | List alerts |
| PATCH | `/api/alerts/<id>/resolve` | Mark alert as resolved |
| GET | `/api/analytics/summary` | Summary stats for N days |
| GET | `/api/analytics/timeline` | Per-day per-species counts |

---

## 🔔 Alert System

When an endangered species is detected:

1. A formatted alert is printed to the console.
2. An `Alert` record is written to the database (when `--log-db` is active).
3. The detection is flagged `alert_sent = True`.

Unresolved alerts appear at the top of the **Logs** page.

To extend alerts (e.g. email / SMS), add a notifier to `src/alerts.py`.

---

## 🌍 Applications

- Wildlife conservation monitoring
- Anti-poaching surveillance
- Ecological research & species census
- National park management

---

## 🔮 Future Enhancements

- IoT integration with smart camera traps
- GPS geolocation tagging per detection
- Advanced night-vision (IR frame support)
- Mobile app integration
- Cloud deployment (AWS Rekognition / GCP Vision API)
- Heatmap overlay of animal activity

---

## 🤝 Contributing

Contributions are welcome! Fork the repository and open a pull request.

---

## 📜 License

This project is licensed under the **MIT License**.

---

## 👨‍💻 Author

AI & Computer Vision Enthusiast — Built with love for wildlife conservation.
