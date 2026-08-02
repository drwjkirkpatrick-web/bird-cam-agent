🔥 Bird Cam Agent
=================

*Where every feather tells a story, and every visitor gets a standing ovation.*

A bird feeder camera system that records, photographs, and identifies birds in real time on any Raspberry Pi. Powered by a [Hermes Agent](https://hermes-agent.nousresearch.com/) vision bridge and bursting with features that make your backyard feel like a living, breathing nature documentary.

**52 modules. 571 tests. Zero subscription fees.**

---

What Makes This Special
-----------------------

🔥 This isn't just a camera pointed at a feeder. It's a full-scale bird observation station that happens to fit in your hand. Every module exists because real birdwatchers asked, "What if my bird cam could also do *that*?"

Here's what happens when a bird lands at your feeder:

1. **Motion detector** wakes up and triggers a capture
2. **Camera** snaps a photo (Pi Camera, USB webcam, or multi-angle)
3. **Hermes vision bridge** identifies the species, scientific name, and confidence
4. **Rarity checker** compares against your local species list
5. **SMS / WiFi / push / email** alerts fire if it's rare or a favorite
6. **Database** stores the sighting with photo, timestamp, and metadata
7. **Dashboard** updates in real time on your phone or browser
8. **Night vision** adjusts settings automatically when it gets dark
9. **Bird book** adds it to your digital collection
10. **Citizen science** uploads to eBird / iNaturalist if you want

All of this happens automatically. You just watch the alerts roll in.

---

Features at a Glance
--------------------

| Category | What It Does |
|----------|-------------|
| **Camera** | Pi Camera, USB webcam, ESP32-CAM, DSLR, multi-angle, night vision, live stream |
| **Identification** | Hermes Agent vision bridge with retry, caching, and confidence calibration |
| **Audio** | Sound recording, sound identification, spectrograms, audio analysis, call library, **local audio AI** |
| **Alerts** | SMS (Twilio), WiFi (Telegram, Discord, email, webhook, MQTT), push (Pushover, Pushbullet, ntfy) |
| **Analytics** | Species tracker, diversity metrics (Shannon/Simpson), migration tracking, feeder activity, daily/weekly/monthly reports |
| **Bird Data** | Pacific Northwest (McIver State Park, 52 species) + Kenya (Nairobi NP, 51 species) databases |
| **Smart Features** | Motion detection, weather filtering, favorite species alerts, review queue for low-confidence IDs |
| **Infrastructure** | System health monitoring, thermal management, power/solar monitoring, GPS, OTA updates, cloud backup |
| **Integration** | REST API, Home Assistant (MQTT), eBird/iNaturalist export, multi-language (EN/SW/ES/FR) |
| **Media** | Time-lapse GIFs/videos, photo organization, spectrogram visualization, CSV/JSON/eBird export |

---

Hardware Requirements
---------------------

| Component | Supported Hardware | Notes |
|-----------|-------------------|-------|
| Raspberry Pi | Pi Zero 2 W, Pi 3 B+, Pi 4, Pi 5 | Any model works |
| Camera | Pi Camera Module 2/3, USB webcam, ESP32-CAM, DSLR | Auto-detected |
| Storage | 8GB+ microSD | Photos accumulate over time |
| Network | WiFi or Ethernet | For alerts, dashboard, API |
| SMS (optional) | Twilio account | For rare bird text alerts |
| Solar (optional) | 5V solar panel + battery bank | For off-grid deployment |
| GPS (optional) | USB GPS module (NEO-6M) | For citizen science submissions |
| Sensors (optional) | BME280, HC-SR04, INA219 | Temperature, seed level, power |

**No hardware?** Mock mode runs the full pipeline on any computer — no camera, no network, no sensors needed.

---

Quick Start
-----------

```bash
# Clone or create the project
cd ~/projects/bird-cam-agent

# Install dependencies
pip install -r requirements.txt

# Or use the install script
bash scripts/install.sh

# Initialize a config file
python cli.py init

# Build a training dataset (PNW birds)
python cli.py build-dataset --species pnw --output data/training

# Train the local classifier (requires PyTorch)
pip install torch torchvision
python cli.py train-classifier --dataset data/training --epochs 10 --export-onnx

# Run a single capture (mock mode — no hardware needed)
python cli.py capture

# Start the monitoring loop
python cli.py run

# View the dashboard
open http://your-pi-ip:9195
```

---

CLI Commands
------------

```bash
python cli.py run              # Start the camera monitoring loop
python cli.py capture          # Single photo + identification
python cli.py identify <path>  # Identify a bird in an existing photo (two-tier: local → Hermes)
python cli.py local-id <path>  # Identify using ONLY the local classifier
python cli.py local-audio-id <path>  # Identify a bird from audio using ONLY the local audio classifier
python cli.py dashboard        # Start the web dashboard only
python cli.py stats            # Print sighting statistics
python cli.py list             # List recent sightings
python cli.py init             # Create a default config file
python cli.py build-dataset    # Download photos for training (PNW, Kenya, custom)
python cli.py train-classifier # Train MobileNetV3 on your dataset
python cli.py train-audio-classifier --dataset data/audio_training # Train audio CNN on WAV clips
python cli.py export-audio-onnx --model data/models/audio_classifier_cnn.pth ... # Export audio model to ONNX
python cli.py test-sms         # Send a test SMS notification
python cli.py health           # Check health of all subsystems (incl. local AI)
python cli.py --version        # Show version
python cli.py --mock capture   # Force mock mode for any command
```

---

Complete Module List (51 Modules)
---------------------------------

### Core (2 modules)

| Module | Description |
|--------|-------------|
| `core/types.py` | BirdSighting, IdentificationResult, RarityLevel, CameraConfig, SightingRecord |
| `core/config.py` | YAML configuration loader with nested sub-configs |

### Camera & Vision (6 modules)

| Module | Description |
|--------|-------------|
| `modules/camera.py` | Pi Camera, USB webcam, and mock capture with auto-detection |
| `modules/camera_advisor.py` | 9 camera options compared — pros, cons, price, resolution, Pi compatibility |
| `modules/multi_camera.py` | Multi-angle camera management with parallel capture |
| `modules/night_vision.py` | Low-light capture with IR illuminator control and hysteresis mode switching |
| `modules/live_stream.py` | MJPEG live video stream to web dashboard |
| `modules/motion_detector.py` | Frame differencing to trigger captures only when birds are present |

### Identification (4 modules)

| Module | Description |
|--------|-------------|
| `modules/hermes_bridge.py` | Hermes Agent vision bridge — API, CLI, and mock modes |
| `modules/identifier.py` | Retry with backoff, confidence thresholding, history tracking |
| `modules/bird_cache.py` | MD5-based identification result caching with TTL and stats |
| `modules/confidence_calibrator.py` | Learns from user feedback to calibrate LLM confidence scores |

### Local AI (3 modules)

| Module | Description |
|--------|-------------|
| `modules/photo_dataset_builder.py` | Download bird photos from iNaturalist, CUB-200, and local archive for training |
| `modules/local_bird_classifier.py` | Train/run MobileNetV3-Small (<50 MB) for offline bird identification |
| `modules/local_audio_classifier.py` | Train/run small CNN on log-mel spectrograms for offline bird sound identification |

### Audio (5 modules)

| Module | Description |
|--------|-------------|
| `modules/sound_recorder.py` | Thread-safe audio recording with pyaudio, WAV format |
| `modules/sound_identifier.py` | Bird sound identification via Hermes bridge |
| `modules/spectrogram.py` | Audio spectrogram visualization with matplotlib |
| `modules/audio_analyzer.py` | Frequency pattern analysis, call comparison |
| `modules/call_library.py` | Reference bird call audio library (user-supplied audio) |

### Notifications (6 modules)

| Module | Description |
|--------|-------------|
| `modules/sms_notifier.py` | SMS alerts via Twilio, Hermes gateway, or mock — rate-limited |
| `modules/wifi_messenger.py` | WiFi alerts: Telegram, Discord, email, webhook, MQTT — free, no cellular |
| `modules/push_notifier.py` | Mobile push: Pushover, Pushbullet, ntfy.sh |
| `modules/email_notifier.py` | SMTP email alerts with rate limiting and daily reports |
| `modules/favorite_alerts.py` | Instant alerts for user-specified favorite species |
| `modules/review_queue.py` | Human review queue for low-confidence identifications |

### Analytics & Tracking (6 modules)

| Module | Description |
|--------|-------------|
| `modules/species_tracker.py` | Life list, Shannon/Simpson diversity indices, Pielou's evenness |
| `modules/migration_tracker.py` | Spring arrivals, autumn departures, arrival prediction |
| `modules/feeder_monitor.py` | Feeder visitation patterns, hourly activity, species frequency |
| `modules/weather_filter.py` | Weather-based capture interval adjustment |
| `modules/daily_report.py` | Daily activity summary with text and HTML formatting |
| `modules/weekly_report.py` | Weekly and monthly summary reports with trend analysis |

### Bird Databases (2 modules)

| Module | Description |
|--------|-------------|
| `modules/pnw_birds.py` | 52 species at McIver State Park, Clackamas County, Oregon |
| `modules/kenya_birds.py` | 51 species at Nairobi National Park, Kenya |

### Data Management (5 modules)

| Module | Description |
|--------|-------------|
| `modules/database.py` | SQLite storage — full CRUD, search, stats, parameterized queries |
| `modules/photo_organizer.py` | Organizes photos by species/date, duplicate detection, disk cleanup |
| `modules/export_csv.py` | Export to CSV, JSON, eBird import format, summary reports |
| `modules/time_lapse.py` | Animated GIF and MP4 time-lapse from feeder photos |
| `modules/bird_book.py` | Digital bird species collection — life list with photos and stats |

### Infrastructure (7 modules)

| Module | Description |
|--------|-------------|
| `modules/system_health.py` | Pi CPU temp, disk space, memory usage, uptime monitoring |
| `modules/thermal_manager.py` | Thermal management with GPIO fan control and auto-throttling |
| `modules/power_monitor.py` | Solar/battery monitoring with low-power alerts |
| `modules/environmental_sensor.py` | Temperature, humidity, pressure readings (BME280) |
| `modules/feeder_level.py` | Bird seed level monitoring with refill alerts |
| `modules/gps_tracker.py` | GPS location tracking for sighting records |
| `modules/cloud_backup.py` | Backup to Dropbox, Google Drive, or rsync remote server |

### Integration (4 modules)

| Module | Description |
|--------|-------------|
| `modules/dashboard.py` | Flask web UI — stats, sightings, photos, JSON APIs (port 9195) |
| `modules/api_server.py` | REST API for external integrations (port 9196) |
| `modules/citizen_science.py` | Upload to eBird, iNaturalist, BirdWeather |
| `modules/updater.py` | Project self-update via git pull |

### Internationalization (1 module)

| Module | Description |
|--------|-------------|
| `modules/i18n.py` | Multi-language: English, Swahili, Spanish, French |

### Orchestrator (2 modules)

| Module | Description |
|--------|-------------|
| `main.py` | BirdCamAgent orchestrator — full capture-to-alert pipeline |
| `cli.py` | Command-line interface with 12 subcommands |

---

Configuration
-------------

### Config File (`config.yaml`)

```bash
python cli.py init --output config.yaml
```

### Rarity File (`data/rarity.yaml`)

Create a YAML file listing bird species and their rarity for your location. Use the included databases as starting points:

```python
# Generate a PNW rarity file
from modules.pnw_birds import write_rarity_file
write_rarity_file("data/rarity.yaml")

# Or generate a Kenya rarity file
from modules.kenya_birds import write_rarity_file
write_rarity_file("data/rarity.yaml")
```

Rarity levels: `common`, `uncommon`, `rare`, `very_rare`, `accidental`

---

Local AI Classifier (Offline)
-----------------------------

Train a **MobileNetV3-Small** bird identification model that runs entirely on your Jetson or Pi — no internet, no API calls, no subscription.

| Approach | Speed | Size | Accuracy | Requires Network |
|----------|-------|------|----------|----------------|
| **Hermes bridge** (LLM vision) | ~2-5s/photo | N/A (cloud) | High (rare species) | Yes |
| **Local classifier** (this module) | ~30ms/photo | ~5 MB | Good (common species) | **No** |
| **Two-tier** (recommended) | ~30ms + 2-5s fallback | ~5 MB | Best of both | Only on fallback |

### Training Workflow

```bash
# 1. Build dataset from iNaturalist + CUB-200 + your archive
python -c "
from modules.photo_dataset_builder import PhotoDatasetBuilder
from core.config import DatasetBuilderConfig
from modules.pnw_birds import SPECIES_DATA

builder = PhotoDatasetBuilder(DatasetBuilderConfig(output_dir='data/training', mock_mode=False))
builder.build_dataset(SPECIES_DATA)
print(builder.get_dataset_stats())
"

# 2. Train the model (on a workstation with PyTorch)
pip install torch torchvision
python -m modules.local_bird_classifier train \
    --dataset data/training \
    --output-dir data/models \
    --epochs 10

# 3. Export to ONNX for faster Jetson inference
python -m modules.local_bird_classifier export \
    --model data/models/bird_classifier_mobilenet_v3_small.pth \
    --labels data/models/bird_classifier_labels.pkl \
    --output data/models/bird_classifier_mobilenet_v3_small.onnx
```

### Using the Classifier

In `config.yaml`:

```yaml
local_classifier:
  model_dir: "data/models"
  model_name: "mobilenet_v3_small"
  confidence_threshold: 0.7
  mock_mode: false
```

The `BirdIdentifier` will use the local classifier first, and fall back to the Hermes bridge for low-confidence or unknown species.

### How It Works

1. **PhotoDatasetBuilder** downloads CC-licensed photos from iNaturalist (bulk), extracts matching classes from CUB-200-2011 (quality), and copies your own archive photos (real-world).
2. **LocalBirdClassifier.train_model()** loads MobileNetV3-Small pre-trained on ImageNet, freezes the backbone, replaces the classifier head, and fine-tunes on your species.
3. **ONNX export** converts to a format that ONNX Runtime runs ~2-3× faster on Jetson than PyTorch CPU.

### Tips for Best Accuracy

- Aim for 50–200 images per species
- Include variation: different angles, distances, lighting
- Your own feeder photos are the most valuable training data
- If accuracy is low, increase epochs to 20–30 and lower learning_rate to 0.0005

---

Local Audio Classifier (Offline)
--------------------------------

Train a **small CNN on log-mel spectrograms** for bird sound identification that runs entirely on your Jetson or Pi — no internet, no API calls, no subscription.

| Approach | Speed | Size | Accuracy | Requires Network |
|----------|-------|------|----------|----------------|
| **Hermes bridge** (LLM audio) | ~3–8s/clip | N/A (cloud) | High (rare calls) | Yes |
| **Local audio classifier** | ~50ms/clip | ~2–5 MB | Good (common calls) | **No** |
| **Two-tier audio** (recommended) | ~50ms + 3–8s fallback | ~2–5 MB | Best of both | Only on fallback |

### Training Workflow

```bash
# 1. Organize your WAV clips by species
mkdir -p data/audio_training/american_robin data/audio_training/northern_cardinal
# Copy or record .wav files into each folder

# 2. Train the audio model (requires PyTorch)
pip install torch
python -m modules.local_audio_classifier train \
    --dataset data/audio_training \
    --output-dir data/models \
    --epochs 20

# 3. Export to ONNX for faster Jetson inference
python -m modules.local_audio_classifier export \
    --model data/models/audio_classifier_cnn.pth \
    --labels data/models/audio_classifier_labels.pkl \
    --output data/models/audio_classifier_cnn.onnx
```

### Using the Audio Classifier

In `config.yaml`:

```yaml
local_audio_classifier:
  model_dir: "data/models"
  model_name: "cnn"
  confidence_threshold: 0.7
  mock_mode: false
```

The `SoundIdentifier` will automatically use the local audio classifier first, and fall back to the Hermes bridge for low-confidence or unknown species.

### How It Works

1. **Audio preprocessing**: WAV files are resampled to 16 kHz, truncated/padded to 5 s, then converted to log-mel spectrograms (64 mel bins). Uses librosa if installed; falls back to a pure-numpy STFT → mel filterbank implementation.
2. **AudioCNN**: A small 3-layer conv network (~500K params) with adaptive average pooling to handle variable-length clips. Trains from scratch on your dataset.
3. **ONNX export**: Converts to a format that ONNX Runtime runs ~2–3× faster on Jetson than PyTorch CPU.

### Tips for Best Audio Accuracy

- Aim for 30–100 clips per species (2–10 seconds each)
- Include variation: different times of day, distances, background noise
- Filter out clips with excessive wind or traffic noise
- Balance your dataset: similar number of clips per species
- If accuracy is low, increase epochs to 30–50 and reduce LR to 0.0005

---

Hermes Agent Bridge
-------------------

The bird identifier uses [Hermes Agent](https://hermes-agent.nousresearch.com/) for vision-based identification. Three modes:

| Mode | How it works | When to use |
|------|-------------|-------------|
| `api` | HTTP POST to Hermes API server | Hermes running as a service |
| `cli` | Subprocess call to `hermes chat -q` | Hermes installed, no server |
| `mock` | Returns canned results | Development and testing |

```bash
# Install Hermes Agent
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
hermes setup
```

---

Notification Setup
------------------

### SMS (Twilio)
Sign up at twilio.com, add credentials to config.yaml. Rate-limited per species (30-min cooldown).

### WiFi Messaging (Free)
- **Telegram Bot**: Create a bot via @BotFather, add token + chat ID
- **Discord Webhook**: Create a webhook URL in your Discord channel
- **Email (SMTP)**: Use Gmail with an app password
- **Webhook**: POST to IFTTT, n8n, or Home Assistant
- **MQTT**: Publish to an MQTT broker for home automation

### Push Notifications (Free)
- **ntfy.sh**: No signup needed — just pick a topic name
- **Pushover**: $5 one-time purchase, 10k free messages/month
- **Pushbullet**: Free tier available

---

Dashboard
---------

The web dashboard runs on port 9195. View it from any browser:

```
http://your-pi-ip:9195
```

Features: stats cards, paginated sighting list, sighting detail with photos, JSON API, mobile-responsive dark theme.

A separate REST API runs on port 9196 for external integrations:

```
http://your-pi-ip:9196/api/v1/sightings
http://your-pi-ip:9196/api/v1/stats
http://your-pi-ip:9196/api/v1/health
```

---

Development
-----------

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests (571 tests, all pass in mock mode)
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_hermes_bridge.py -v
```

### Project Structure

```
bird-cam-agent/
+-- core/                    # Shared types and configuration
+-- modules/                 # 52 functional modules
+-- tests/                   # 571 tests (12 skip on non-Pi hardware)
+-- main.py                  # Orchestrator
+-- cli.py                   # Command-line interface
+-- PROMPTS.md               # Testable build prompts
+-- requirements.txt         # Python dependencies
+-- scripts/
    +-- install.sh           # Installation script
```

### Mock Mode

Everything runs in mock mode by default — no camera, no Hermes API, no SMS, no sensors. The full pipeline runs on any computer.

---

Gap Analysis: How We Compare
-----------------------------

🔥 Here's where Bird Cam Agent stands against the competition:

| Feature | Birdfy ($170+) | Bird Buddy ($200+) | BirdNET-Pi (free) | **Bird Cam Agent (free)** |
|---------|:---:|:---:|:---:|:---:|
| AI bird ID (vision) | Cloud (subscription) | Cloud (subscription) | No | **Local + Hermes vision** |
| AI bird ID (audio) | No | No | **BirdNET (local)** | **Local CNN + Hermes audio** |
| Camera capture | Yes | Yes | No (audio only) | **Yes** |
| Live stream | Yes | Yes | No | **Yes** |
| Night vision | Yes | Yes | No | **Yes (with IR control)** |
| Multi-camera | No | No | No | **Yes** |
| SMS alerts | Push (app) | Push (app) | No | **Yes (Twilio)** |
| WiFi alerts | Push (app) | Push (app) | No | **Telegram/Discord/email/MQTT/push** |
| Rarity checker | No | No | No | **Yes (user-supplied YAML)** |
| Bird database | Yes (cloud) | Yes (cloud) | No | **PNW + Kenya included** |
| Web dashboard | App | App | Yes | **Flask + REST API** |
| Citizen science | Yes | Yes | No | **eBird/iNaturalist/BirdWeather** |
| Time-lapse | Yes | Yes | No | **Yes (GIF + video)** |
| Diversity metrics | No | No | No | **Shannon/Simpson/evenness** |
| Migration tracking | No | No | No | **Yes** |
| Audio ID | No | No (BirdNET) | **Yes (local)** | **Yes (local + cloud)** |
| Spectrogram | No | No | Yes | **Yes** |
| Solar/battery monitor | Yes (built-in) | Yes (built-in) | No | **Yes (INA219)** |
| Thermal management | N/A | N/A | No | **Yes (GPIO fan)** |
| System health | N/A | N/A | Yes | **Yes** |
| Multi-language | Yes | Yes | No | **EN/SW/ES/FR** |
| GPS | No | No | No | **Yes** |
| Cloud backup | Yes (subscription) | Yes (subscription) | No | **rsync/Dropbox** |
| OTA updates | Yes | Yes | No | **Yes (git pull)** |
| Review queue | No | Yes (corrections) | No | **Yes** |
| Open source | No | No | Yes | **Yes** |
| Runs on any Pi | No (proprietary) | No (proprietary) | Yes | **Yes** |
| Cost | $170+ + subscription | $200+ + subscription | Free | **Free** |

---

License
-------

MIT

---

🔥 *Built with passion for the birds that make our backyards extraordinary. Every module exists because someone said "I wish my bird cam could do that." Now it can.*