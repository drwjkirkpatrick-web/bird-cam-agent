# Bird Cam Agent

A bird feeder camera system that **records, photographs, and identifies** birds in real time on any Raspberry Pi. Uses a [Hermes Agent](https://hermes-agent.nousresearch.com/) vision bridge for identification and sends **SMS alerts** when rare birds appear.

## Features

- **Automatic capture** — takes photos at regular intervals or on motion
- **AI identification** — Hermes Agent vision LLM identifies species, scientific name, and confidence
- **Rarity checking** — compares against a user-supplied rarity list for your location
- **Real-time SMS alerts** — texted the moment a rare bird lands at the feeder
- **Web dashboard** — browse sightings, photos, and stats from your phone
- **Video recording** — captures short video clips of bird behavior
- **Runs on any Pi** — Pi Zero 2 W, Pi 3 B+, Pi 4, Pi 5 (mock mode works on any computer)

## Architecture

```
+------------------+     +-------------------+     +---------------------+
|     Camera       |---->|   Hermes Bridge   |---->|    Identifier       |
| (Pi Cam / USB /  |     | (API / CLI / Mock)|     |  (retry + history)  |
|     Mock)        |     +-------------------+     +---------------------+
+------------------+                                        |
                                                             v
+------------------+     +-------------------+     +---------------------+
|   SQLite DB      |<----|   Orchestrator    |---->|   Rarity Checker    |
| (sightings +     |     |   (main loop)     |     | (user YAML file)    |
|  photos + records|     +-------------------+     +---------------------+
+------------------+                                        |
        ^                                                    |
        |                                                    v
+------------------+     +-------------------+     +---------------------+
|    Dashboard     |<----|    SMS Notifier   |<----|  Rare bird?         |
|  (Flask web UI)  |     | (Twilio / Hermes  |     |  Send alert!        |
|                  |     |  gateway / Mock)  |     |                     |
+------------------+     +-------------------+     +---------------------+
```

## Quick Start

```bash
# Clone or create the project
cd ~/projects/bird-cam-agent

# Install dependencies
pip install -r requirements.txt

# Initialize a config file
python cli.py init

# Run a single capture (mock mode — no hardware needed)
python cli.py capture

# Start the monitoring loop
python cli.py run

# View the dashboard
open http://your-pi-ip:9195
```

## Hardware Requirements

| Component | Supported Hardware | Notes |
|-----------|-------------------|-------|
| Raspberry Pi | Pi Zero 2 W, Pi 3 B+, Pi 4, Pi 5 | Any model works |
| Camera | Pi Camera Module 2/3, USB webcam | Auto-detected |
| Storage | 8GB+ microSD | Photos accumulate over time |
| Network | WiFi or Ethernet | For Hermes API + SMS + Dashboard |
| SMS (optional) | Twilio account or Hermes SMS gateway | For rare bird alerts |

**No hardware?** Mock mode runs the full pipeline on any computer — no camera, no network, no SMS provider needed.

## Configuration

### Config File (`config.yaml`)

```bash
python cli.py init --output config.yaml
```

Edit the generated file to configure:

```yaml
camera:
  mock_mode: false          # Set to false when deploying with real hardware
  camera_type: auto          # auto, picamera, usb, or mock
  capture_interval: 30.0     # seconds between captures
  photo_dir: data/photos

hermes_bridge:
  mode: api                  # api, cli, or mock
  api_url: http://127.0.0.1:9119
  mock_mode: false

sms:
  provider: twilio           # twilio, hermes_gateway, or mock
  to_number: "+15035551234"
  from_number: "+15035550000"
  account_sid: "your_twilio_sid"
  auth_token: "your_twilio_token"
  cooldown_minutes: 30       # min between alerts for same species

rarity:
  rarity_file: data/rarity.yaml  # Your custom rarity list
  location_name: "Pacific Northwest, USA"
```

### Rarity File (`data/rarity.yaml`)

Create a YAML file listing bird species and their rarity for your location. This is **user-supplied** — you know your local birds best.

```yaml
location: "Pacific Northwest, USA"
species:
  - name: "American Robin"
    scientific_name: "Turdus migratorius"
    rarity: "common"
    notes: "Year-round resident"

  - name: "Northern Cardinal"
    scientific_name: "Cardinalis cardinalis"
    rarity: "uncommon"
    notes: "Occasional visitor"

  - name: "Snowy Owl"
    scientific_name: "Bubo scandiacus"
    rarity: "rare"
    notes: "Irruptive winter visitor"

  - name: "Spotted Redshank"
    scientific_name: "Tringa erythropus"
    rarity: "accidental"
    notes: "Extremely rare vagrant"
```

Rarity levels: `common`, `uncommon`, `rare`, `very_rare`, `accidental`

**No rarity file?** All birds default to `common` — no alerts will be sent until you create one.

## Hermes Agent Bridge

The bird identifier uses [Hermes Agent](https://hermes-agent.nousresearch.com/) for vision-based identification. Three modes:

| Mode | How it works | When to use |
|------|-------------|-------------|
| `api` | HTTP POST to Hermes API server | Hermes running as a service on the Pi |
| `cli` | Subprocess call to `hermes chat -q` | Hermes installed but not running as server |
| `mock` | Returns canned results | Development and testing |

**Install Hermes Agent:**
```bash
curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh | bash
hermes setup
```

The vision prompt asks the LLM to identify the bird species, scientific name, confidence level, key attributes (color, size, beak shape), and whether the image actually contains a bird.

## SMS Notifications

Alerts are sent when a bird at or above the `rare` rarity threshold is identified. Rate limiting prevents duplicate alerts (default: 30-minute cooldown per species).

| Provider | Setup |
|----------|-------|
| Twilio | Sign up at twilio.com, add `account_sid`, `auth_token`, `from_number`, `to_number` |
| Hermes Gateway | Configure SMS in Hermes, use `hermes_gateway` provider |
| Mock | Logs the message to console — no setup needed |

**Test SMS:**
```bash
python cli.py test-sms
```

## CLI Commands

```bash
python cli.py run              # Start the monitoring loop
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

## Dashboard

The web dashboard runs on port 9195 by default. View it from any browser on your network:

```
http://your-pi-ip:9195
```

Features:
- Stats cards (total sightings, unique species, rarest bird, last sighting)
- Paginated sighting list with thumbnails
- Individual sighting detail pages with photos
- JSON API endpoints (`/api/sightings`, `/api/stats`)
- Mobile-responsive dark theme

## Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run tests
python -m pytest tests/ -v

# Run tests with coverage
python -m pytest tests/ --cov=modules --cov=core

# Run a specific test file
python -m pytest tests/test_hermes_bridge.py -v
```

### Project Structure

```
bird-cam-agent/
+-- core/
|   +-- types.py          # Data types (BirdSighting, RarityLevel, etc.)
|   +-- config.py         # YAML configuration loader
+-- modules/
|   +-- camera.py         # Camera capture (Pi Camera, USB, Mock)
|   +-- recorder.py       # Video recording (Pi Camera, USB, Mock)
|   +-- database.py       # SQLite storage layer
|   +-- hermes_bridge.py  # Hermes Agent vision bridge
|   +-- identifier.py     # Bird identification coordinator
|   +-- rarity_checker.py # Species rarity lookup
|   +-- sms_notifier.py   # SMS alerts (Twilio, Hermes, Mock)
|   +-- dashboard.py      # Flask web UI
+-- tests/                # 150+ tests (all pass in mock mode)
+-- main.py               # Orchestrator (main capture loop)
+-- cli.py                # Command-line interface
+-- PROMPTS.md            # Testable build prompts for each module
+-- requirements.txt      # Python dependencies
+-- scripts/
    +-- install.sh        # Installation script
```

### Mock Mode

Everything runs in mock mode by default:
- **Camera**: generates placeholder JPEG images
- **Hermes bridge**: returns canned identification results
- **SMS**: logs messages to console instead of sending
- **Database**: uses in-memory SQLite

This lets you develop and test on any machine without hardware.

## License

MIT