# Bird Cam Agent — Testable Build Prompts

A bird feeder camera system that records, photographs, and identifies birds
in real time on any Raspberry Pi. Uses a Hermes Agent vision bridge for
identification and sends SMS alerts when rare birds appear.

## Architecture

```
Camera → Motion/Interval Trigger → Capture Photo
  → Hermes Bridge (vision LLM) → Identification Result
  → Rarity Checker → Rare? → SMS Notifier → Owner
  → Database (SQLite) → Dashboard (Flask web UI)
```

## Build Order Table

| # | Module | File | Depends On |
|---|--------|------|------------|
| 0.1 | Core Types | core/types.py | — |
| 0.2 | Config | core/config.py | types |
| 1.1 | Database | modules/database.py | types, config |
| 1.2 | Camera | modules/camera.py | types, config |
| 1.3 | Recorder | modules/recorder.py | types, config |
| 2.1 | Hermes Bridge | modules/hermes_bridge.py | types, config |
| 2.2 | Identifier | modules/identifier.py | types, config, hermes_bridge |
| 2.3 | Rarity Checker | modules/rarity_checker.py | types, config |
| 3.1 | SMS Notifier | modules/sms_notifier.py | types, config |
| 4.1 | Dashboard | modules/dashboard.py | types, config, database |
| 5.1 | Orchestrator | main.py | all modules |
| 5.2 | CLI | cli.py | main, config |

## Testing Strategy

- **Mock mode**: Every module works without hardware (no camera, no network,
  no SMS provider). Mock mode is the default for development and testing.
- **pytest**: Each module has a dedicated test file in tests/.
- **Target**: 200+ tests across all modules.
- **Hardware-conditional**: Camera and recorder tests use
  `pytest.importorskip` for picamera / cv2 so they skip cleanly on
  non-Pi development machines.
- **Integration test**: test_orchestrator.py runs the full pipeline in
  mock mode (capture → identify → rarity → notify → store).

---

## Phase 0: Foundation

### Prompt 0.1 — Core Types (`core/types.py`)

Create the core data types used across all modules.

**File**: `core/types.py`
**Depends on**: nothing
**Test**: `tests/test_types.py`

Implement:
- `BirdSighting` dataclass: sighting_id, species, scientific_name,
  confidence, photo_path, timestamp, rarity_level, notes, location
- `IdentificationResult` dataclass: species, scientific_name, confidence,
  attributes (dict), description, is_bird (bool), alternative_species (list)
- `RarityLevel` enum: COMMON, UNCOMMON, RARE, VERY_RARE, ACCIDENTAL
- `CameraConfig` dataclass: device_index, resolution_width, resolution_height,
  capture_interval, photo_dir, video_dir, mock_mode
- `SightingRecord` dataclass: record_id, sighting_id, stored_at, file_size,
  file_hash
- `to_dict()` / `from_dict()` on every dataclass (filter computed properties)
- `__all__` export list

Tests:
- Round-trip serialization (to_dict → from_dict → equality)
- RarityLevel string conversion
- Default values
- Computed property filtering in from_dict

### Prompt 0.2 — Config (`core/config.py`)

Create the YAML configuration loader.

**File**: `core/config.py`
**Depends on**: core/types
**Test**: `tests/test_config.py`

Implement:
- `Config` frozen dataclass with nested sub-configs:
  - `CameraConfig` (from types)
  - `HermesBridgeConfig`: api_url, api_key, model, timeout, mock_mode
  - `SMSConfig`: provider, account_sid, auth_token, from_number, to_number,
    mock_mode
  - `RarityConfig`: rarity_file (path to user-supplied YAML), location_name
  - `DatabaseConfig`: db_path, photo_dir, video_dir
  - `DashboardConfig`: host, port, enabled
  - `OrchestratorConfig`: capture_interval, identification_enabled,
    notification_enabled, mock_mode
- `from_yaml(path)` classmethod — loads YAML, maps to Config
- `from_dict(data)` classmethod
- `to_dict()` method
- `create_default_config()` — returns a Config with sensible Pi defaults
- `write_default_config(path)` — writes a YAML template

Tests:
- Load from YAML string
- Default config has mock_mode=True everywhere
- Round-trip: create_default → to_dict → from_dict → equality
- Missing optional fields use defaults
- Extra unknown fields ignored gracefully

---

## Phase 1: Core Infrastructure

### Prompt 1.1 — Database (`modules/database.py`)

SQLite storage for bird sightings and photo metadata.

**File**: `modules/database.py`
**Depends on**: core/types, core/config
**Test**: `tests/test_database.py`

Implement:
- `SightingDatabase` class:
  - `__init__(self, db_path, mock_mode=True)` — uses `:memory:` in mock
  - `_init_schema()` — creates tables: sightings, photos, records
  - `store_sighting(sighting: BirdSighting) -> str` — returns sighting_id
  - `get_sighting(sighting_id) -> BirdSighting | None`
  - `list_sightings(limit=50, offset=0, species=None) -> list[BirdSighting]`
  - `get_sightings_by_species(species) -> list[BirdSighting]`
  - `get_stats() -> dict` — total count, unique species, by rarity
  - `search_sightings(query) -> list[BirdSighting]` — free-text search
  - `delete_sighting(sighting_id) -> bool`
  - `close()`
- Use sqlite3.Row, parameterized queries, no SQL injection
- DDL as class-level constants
- NOTE/WHY comments for teaching

Tests:
- Store and retrieve a sighting
- List sightings with pagination
- Filter by species
- Search by species or notes
- Stats (count, unique species, rarity breakdown)
- Delete sighting
- Duplicate sighting_id handling

### Prompt 1.2 — Camera (`modules/camera.py`)

Camera capture module supporting Pi Camera, USB webcams, and mock mode.

**File**: `modules/camera.py`
**Depends on**: core/types, core/config
**Test**: `tests/test_camera.py`

Implement:
- `CameraBase` abstract class: `capture_photo() -> str`, `get_camera_info() -> dict`
- `PiCameraCapture(CameraBase)` — uses picamera2 or picamera library
- `USBCameraCapture(CameraBase)` — uses OpenCV cv2.VideoCapture
- `MockCameraCapture(CameraBase)` — generates a placeholder PIL image, saves as JPEG
- `CameraFactory.create(config: CameraConfig) -> CameraBase` — picks the right
  implementation based on config and available hardware
- `capture_photo()` returns the file path to the saved JPEG
- Filenames: `bird_{timestamp}.jpg` in the configured photo_dir
- Hardware detection: try picamera import, then cv2, then fall back to mock
- `pytest.importorskip` pattern for hardware-dependent tests

Tests:
- MockCameraCapture creates a valid JPEG file
- CameraFactory returns MockCameraCapture in mock mode
- CameraFactory falls back to mock when no hardware
- Photo filename contains timestamp
- capture_photo creates file in configured directory
- get_camera_info returns device info dict
- PiCameraCapture tests skip cleanly without picamera
- USBCameraCapture tests skip cleanly without cv2

### Prompt 1.3 — Recorder (`modules/recorder.py`)

Video recording module for capturing bird behavior clips.

**File**: `modules/recorder.py`
**Depends on**: core/types, core/config
**Test**: `tests/test_recorder.py`

Implement:
- `RecorderBase` abstract class: `start_recording(duration_sec) -> str`,
  `stop_recording() -> str`, `is_recording() -> bool`
- `PiCameraRecorder(RecorderBase)` — uses picamera for video
- `USBRecorder(RecorderBase)` — uses cv2.VideoWriter
- `MockRecorder(RecorderBase)` — creates a placeholder .mp4 file
- `RecorderFactory.create(config) -> RecorderBase`
- Recordings saved to configured video_dir with timestamp filenames
- Thread-safe: recording runs in a background thread, stop() joins

Tests:
- MockRecorder creates a file after recording
- start/stop lifecycle
- is_recording state transitions
- Factory returns correct type based on config
- Hardware tests skip cleanly without picamera/cv2

---

## Phase 2: Identification

### Prompt 2.1 — Hermes Bridge (`modules/hermes_bridge.py`)

Bridge to Hermes Agent for vision-based bird identification.

**File**: `modules/hermes_bridge.py`
**Depends on**: core/types, core/config
**Test**: `tests/test_hermes_bridge.py`

Implement:
- `HermesBridge` class:
  - `__init__(self, config: HermesBridgeConfig)` — stores config, sets up
    HTTP session or CLI path
  - `identify_bird(photo_path: str) -> IdentificationResult` — sends the
    photo to Hermes vision LLM with a bird-identification prompt, parses
    the structured response
  - `_build_prompt() -> str` — returns the system/user prompt asking the
    vision model to identify the bird species, scientific name, confidence,
    and key attributes
  - `_parse_response(raw: str) -> IdentificationResult` — extracts
    species, scientific_name, confidence, attributes, description,
    is_bird, alternative_species from the LLM response
  - `_call_api(photo_path) -> str` — POST the image to the Hermes API
    server endpoint (configurable URL)
  - `_call_cli(photo_path) -> str` — use `hermes chat -q` with the image
    path as a subprocess call
  - `mock_identify(photo_path) -> IdentificationResult` — returns a
    canned result for testing
  - `health_check() -> dict` — check if the Hermes API/CLI is reachable
- Support three modes: `api` (HTTP), `cli` (subprocess), `mock`
- The prompt should ask the vision model to respond in JSON format:
  ```json
  {
    "species": "string",
    "scientific_name": "string",
    "confidence": 0.0-1.0,
    "is_bird": true/false,
    "attributes": {"color": "...", "size": "...", "beak_shape": "..."},
    "description": "string",
    "alternative_species": ["species1", "species2"]
  }
  ```
- Error handling: timeout, connection refused, malformed response,
  non-bird detection (is_bird=false → return result with species="Unknown")
- Requests library for API mode, subprocess for CLI mode

Tests:
- Mock mode returns valid IdentificationResult
- _build_prompt contains bird identification instructions
- _parse_response extracts fields from JSON response
- _parse_response handles malformed JSON gracefully
- _parse_response handles is_bird=false
- health_check returns status dict
- API mode constructs correct request (mock HTTP)
- CLI mode constructs correct command (mock subprocess)
- Timeout handling
- Non-bird detection returns is_bird=False

### Prompt 2.2 — Identifier (`modules/identifier.py`)

High-level bird identification coordinator that uses the Hermes bridge.

**File**: `modules/identifier.py`
**Depends on**: core/types, core/config, modules/hermes_bridge
**Test**: `tests/test_identifier.py`

Implement:
- `BirdIdentifier` class:
  - `__init__(self, hermes_bridge: HermesBridge, config: Config)`
  - `identify(photo_path: str) -> IdentificationResult` — delegates to
    HermesBridge, adds timestamp, logs the identification
  - `identify_batch(photo_paths: list[str]) -> list[IdentificationResult]`
  - `identify_with_retry(photo_path, max_retries=3) -> IdentificationResult`
    — retry with exponential backoff on failure
  - `get_identification_history() -> list[IdentificationResult]` —
    in-memory history of recent identifications
  - `_log_identification(result)` — structured logging
  - Confidence threshold: results below configurable threshold get
    flagged as "low confidence"

Tests:
- identify() delegates to hermes_bridge
- identify_batch processes multiple photos
- identify_with_retry retries on failure
- identify_with_retry succeeds on second attempt (mock)
- Low confidence flagging
- History tracking
- Empty batch returns empty list

### Prompt 2.3 — Rarity Checker (`modules/rarity_checker.py`)

Check if an identified bird is rare for the user's location.

**File**: `modules/rarity_checker.py`
**Depends on**: core/types, core/config
**Test**: `tests/test_rarity_checker.py`

Implement:
- `RarityChecker` class:
  - `__init__(self, config: RarityConfig)` — loads user-supplied rarity
    YAML file
  - `check_rarity(species: str, scientific_name: str = "") -> RarityLevel`
  - `is_rare(species: str, threshold: RarityLevel = RARE) -> bool`
  - `load_rarity_data(path: str) -> dict` — loads YAML with species →
    rarity mapping
  - `get_rarity_info(species: str) -> dict` — returns rarity level +
    notes + best viewing season if available
  - `add_species(species, rarity_level, notes="")` — add/update entry
  - `list_all() -> dict` — returns full rarity database
- The rarity file is user-supplied (NOT hardcoded). If no file exists,
  all birds default to COMMON.
- Case-insensitive species matching with fuzzy fallback
- The rarity file format (user creates this):
  ```yaml
  location: "Pacific Northwest, USA"
  species:
    - name: "American Robin"
      scientific_name: "Turdus migratorius"
      rarity: "common"
      notes: "Year-round resident"
    - name: "Snowy Owl"
      scientific_name: "Bubo scandiacus"
      rarity: "rare"
      notes: "Irruptive winter visitor"
  ```

Tests:
- Common species returns COMMON
- Rare species returns RARE
- Unknown species defaults to COMMON
- is_rare returns True for RARE and above
- is_rare returns False for COMMON and UNCOMMON
- Case-insensitive matching
- Fuzzy matching for slight name variations
- load_rarity_data from YAML file
- No rarity file → all COMMON
- add_species updates the database
- list_all returns all entries

---

## Phase 3: Notifications

### Prompt 3.1 — SMS Notifier (`modules/sms_notifier.py`)

SMS alerts when rare birds are detected.

**File**: `modules/sms_notifier.py`
**Depends on**: core/types, core/config
**Test**: `tests/test_sms_notifier.py`

Implement:
- `SMSNotifier` class:
  - `__init__(self, config: SMSConfig)` — stores config
  - `send_rare_bird_alert(sighting: BirdSighting) -> bool` — sends SMS
    with species, rarity, timestamp, and photo info
  - `send_message(body: str, to_number: str = None) -> bool` — generic
    SMS send
  - `_format_alert(sighting) -> str` — formats the alert message text
  - `_send_twilio(body, to_number) -> bool` — Twilio API implementation
  - `_send_hermes_gateway(body, to_number) -> bool` — use Hermes SMS
    gateway if configured
  - `mock_send(body, to_number) -> bool` — logs the message, returns True
  - `test_notification() -> bool` — sends a test message
- Three modes: `twilio`, `hermes_gateway`, `mock`
- Alert format: "🐦 Rare bird alert! A {species} ({rarity}) was spotted
  at {timestamp}. Photo: {photo_path}"
- Rate limiting: don't send duplicate alerts for the same species within
  a configurable cooldown window (default 30 min)
- Error handling: API failures, invalid numbers, rate limits

Tests:
- Mock mode sends and logs message
- _format_alert contains species and rarity
- Rate limiting prevents duplicate alerts
- Rate limiting allows alerts after cooldown
- Twilio mode constructs correct API call (mock HTTP)
- Hermes gateway mode (mock subprocess)
- test_notification returns True in mock mode
- Invalid phone number handling
- Empty body handling

---

## Phase 4: Dashboard

### Prompt 4.1 — Dashboard (`modules/dashboard.py`)

Flask web UI for viewing bird sightings.

**File**: `modules/dashboard.py`
**Depends on**: core/types, core/config, modules/database
**Test**: `tests/test_dashboard.py`

Implement:
- `create_app(db: SightingDatabase, config: DashboardConfig) -> Flask`
  factory pattern
- Routes:
  - `GET /` — dashboard home with recent sightings + stats
  - `GET /sightings` — paginated sighting list
  - `GET /sighting/<id>` — single sighting detail with photo
  - `GET /api/sightings` — JSON API for sighting data
  - `GET /api/stats` — JSON API for statistics
  - `GET /photo/<filename>` — serve photo files from photo_dir
  - `POST /api/test-sms` — trigger a test SMS notification
- Inline HTML template (string-returning) — no external template files
- Responsive CSS for mobile viewing (check from phone)
- Stats cards: total sightings, unique species, rarest bird, last sighting
- Recent sightings table with thumbnails
- `html.escape()` on all user/dynamic content
- No external dependencies beyond Flask

Tests:
- GET / returns 200 with stats
- GET /sightings returns sighting list
- GET /sighting/<id> returns detail page
- GET /api/sightings returns JSON
- GET /api/stats returns JSON stats
- Photo serving route
- html.escape on species names with special chars
- Empty database shows placeholder text
- POST /api/test-sms triggers notification (mock)

---

## Phase 5: Orchestrator

### Prompt 5.1 — Main Orchestrator (`main.py`)

Main loop that ties all modules together.

**File**: `main.py`
**Depends on**: all modules
**Test**: `tests/test_orchestrator.py`

Implement:
- `BirdCamAgent` class:
  - `__init__(self, config_path: str = None)` — loads config, initializes
    all modules based on config
  - `run()` — main capture loop: capture photo → identify → check rarity →
    notify if rare → store in DB → repeat
  - `run_single_capture()` — one capture cycle (for testing/CLI)
  - `start_dashboard()` — start Flask dashboard in background thread
  - `stop()` — graceful shutdown
  - `_handle_sighting(photo_path, result)` — store + notify + log
  - `_should_notify(species) -> bool` — check rarity + rate limiting
- Signal handling: SIGINT/SIGTERM for clean shutdown
- Thread-safe: dashboard runs in background, main loop in foreground
- Mock mode: full pipeline runs without any hardware
- Structured logging throughout

Tests:
- Mock mode full pipeline (capture → identify → rarity → notify → store)
- run_single_capture completes without error in mock mode
- Rare bird triggers notification
- Common bird does not trigger notification
- Dashboard starts in background
- stop() cleans up resources
- Multiple captures don't duplicate alerts (rate limiting)

### Prompt 5.2 — CLI (`cli.py`)

Command-line interface for the bird cam agent.

**File**: `cli.py`
**Depends on**: main, core/config
**Test**: `tests/test_cli.py`

Implement:
- `main()` entry point with argparse
- Subcommands:
  - `run` — start the camera monitoring loop
  - `capture` — take a single photo and identify
  - `identify <photo_path>` — identify a bird in an existing photo
  - `dashboard` — start the web dashboard only
  - `stats` — print sighting statistics
  - `list` — list recent sightings
  - `init` — create default config file
  - `test-sms` — send a test SMS notification
- `--config` flag for custom config path
- `--mock` flag to force mock mode
- `--verbose` flag for debug logging
- `--version` flag

Tests:
- `init` creates a config file
- `capture` runs a single capture cycle in mock mode
- `identify` identifies a photo via Hermes bridge (mock)
- `stats` prints statistics
- `list` prints sighting list
- `test-sms` sends a test notification (mock)
- `--mock` flag forces mock mode
- Missing config file gives helpful error

---

## Phase 6: Local AI Training (Optional)

### Prompt 6.1 — Photo Dataset Builder (`modules/photo_dataset_builder.py`)

Download and curate bird photos from iNaturalist, CUB-200-2011, and local archive for training a local classifier.

**File**: `modules/photo_dataset_builder.py`
**Depends on**: core/config
**Test**: `tests/test_photo_dataset_builder.py`

Implement:
- `PhotoDatasetBuilder` class:
  - `__init__(self, config: DatasetBuilderConfig)` — stores config, initializes dedup hash set
  - `build_dataset(species_list, sources) -> list[SpeciesDownloadResult]` — main entry point
  - `_build_species(species, scientific_name, sources) -> SpeciesDownloadResult` — per-species download loop
  - `_download_inaturalist(...)` — iNaturalist API with rate limiting, image validation
  - `_download_cub200(...)` — Download/extract CUB-200 archive, match by species name
  - `_copy_from_archive(...)` — Copy from PhotoOrganizer output directories
  - `_save_image(url, dest_dir, result) -> bool` — download, validate, deduplicate, save
  - `_copy_valid_image(src, dest_dir, result) -> bool` — copy local file with validation
  - `_mock_download(...)` — create synthetic JPEGs for testing
  - `get_dataset_stats() -> dict` — total images, species counts, minimum met
  - `clean_dataset() -> int` — remove all files from output directory
- `SpeciesDownloadResult` dataclass: species, downloaded, skipped_dup, invalid, errors, source_counts
- Generic: accepts any species list (PNW, Kenya, custom)
- Three sources: `inaturalist`, `cub200`, `archive`
- Rate limiting (0.7s between iNaturalist requests), retry with backoff
- Deduplication via MD5 hash across all sources
- Image validation via Pillow
- Mock mode creates synthetic images without network

Tests:
- Build creates species directories with images
- Respects max_images_per_species
- Returns SpeciesDownloadResult per species
- Skips empty-name entries
- Stats after build show correct counts
- Clean removes all files
- Mock mode creates synthetic images
- Multi-source build with fake archive
- Constants test for ALL_SOURCES

### Prompt 6.2 — Local Bird Classifier (`modules/local_bird_classifier.py`)

Lightweight MobileNetV3-Small classifier for offline bird identification.

**File**: `modules/local_bird_classifier.py`
**Depends on**: core/config, core/types
**Test**: `tests/test_local_bird_classifier.py`

Implement:
- `LocalBirdClassifier` class:
  - `__init__(self, config: LocalClassifierConfig)` — stores config, lazy-load model
  - `load() -> bool` — load PyTorch or ONNX model + label map from disk
  - `identify(photo_path) -> IdentificationResult` — classify image, return top-3 results
  - `is_ready() -> bool` — model loaded?
  - `get_supported_species() -> list[str]` — known class labels
  - `_try_load_pytorch() -> bool` — load .pth checkpoint
  - `_try_load_onnx() -> bool` — load .onnx with ONNX Runtime
  - `_predict_pytorch(photo_path) -> IdentificationResult` — PyTorch inference
  - `_predict_onnx(photo_path) -> IdentificationResult` — ONNX inference
  - `_mock_identify(photo_path) -> IdentificationResult` — deterministic mock by filename hash
  - `_create_model(num_classes) -> Any` — MobileNetV3-Small with fresh classifier head
  - `TRAINING_DIRECTIONS` — embedded markdown with step-by-step training instructions
- `@classmethod train_model(...)` — transfer learning with frozen backbone, 80/20 split
- `@classmethod export_onnx(...)` — export trained model to ONNX
- CLI entry point: `python -m modules.local_bird_classifier [train|export]`
- Model <50MB (MobileNetV3-Small ~5MB)
- Mock mode works without PyTorch

Tests:
- Mock load returns True
- Mock identify returns valid IdentificationResult with alternatives
- Missing photo returns Unknown
- Supported species list populated
- Deterministic mock by filename hash
- Different files may yield different results
- High/low confidence threshold tests
- Training directions contain key steps
- Load without model returns False
- Identify without model returns Unknown
- Config round-trip (to_dict/from_dict)

## Post-Build

### Prompt 7.1 — README (`README.md`)

Update README with:
- New module descriptions (Photo Dataset Builder, Local Bird Classifier)
- Training workflow: build dataset → train → export ONNX
- Comparison: Hermes bridge vs local classifier vs two-tier approach
- Hardware note: training on workstation, inference on Jetson/Pi

### Prompt 7.2 — Install Script (`scripts/install.sh`)

Shell script that:
- Creates a virtual environment
- Installs Python dependencies
- Creates default config
- Creates data directories
- Optionally sets up systemd service