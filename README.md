🔥 Bird Cam Agent
=================

*Where every feather tells a story, and every visitor gets a standing ovation.*

A bird feeder camera system that records, photographs, and identifies birds in real time on any Raspberry Pi. Powered by a [Hermes Agent](https://hermes-agent.nousresearch.com/) vision bridge and bursting with features that make your backyard feel like a living, breathing nature documentary.

**49 modules. 554 tests. Zero subscription fees.**

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
| **Audio** | Sound recording, sound identification, spectrograms, audio analysis, call library |
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
python cli.py identify <path>  # Identify a bird in an existing photo
python cli.py dashboard        # Start the web dashboard only
python cli.py stats            # Print sighting statistics
python cli.py list             # List recent sightings
python cli.py init             # Create a default config file
python cli.py test-sms         # Send a test SMS notification
python cli.py health           # Check health of all subsystems
python cli.py --version        # Show version
python cli.py --mock capture   # Force mock mode for any command
```

---

Complete Module List (49 Modules)
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
| `cli.py` | Command-line interface with 9 subcommands |

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

# Run tests (554 tests, all pass in mock mode)
python -m pytest tests/ -v

# Run a specific test file
python -m pytest tests/test_hermes_bridge.py -v
```

### Project Structure

```
bird-cam-agent/
+-- core/                    # Shared types and configuration
+-- modules/                 # 49 functional modules
+-- tests/                   # 554 tests (12 skip on non-Pi hardware)
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
| AI bird ID | Cloud (subscription) | Cloud (subscription) | Local ML (audio only) | **Hermes vision bridge** |
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
| Audio ID | No | No (BirdNET) | Yes | **Yes (Hermes bridge)** |
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