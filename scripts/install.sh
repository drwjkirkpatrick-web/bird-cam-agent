#!/bin/bash
# install.sh — Bird Cam Agent installation script
# Works on any Raspberry Pi (Pi Zero 2 W, Pi 3, Pi 4, Pi 5) and Linux dev machines.

set -e

echo "=== Bird Cam Agent Installer ==="
echo ""

# --- Determine project directory ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"
echo "Project directory: $PROJECT_DIR"
echo ""

# --- Create virtual environment ---
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
    echo "Virtual environment created."
else
    echo "Virtual environment already exists."
fi

# Activate it
source .venv/bin/activate

# --- Upgrade pip ---
echo ""
echo "Upgrading pip..."
pip install --upgrade pip -q

# --- Install dependencies ---
echo ""
echo "Installing Python dependencies..."
pip install -r requirements.txt -q
echo "Dependencies installed."

# --- Create data directories ---
echo ""
echo "Creating data directories..."
mkdir -p data/photos
mkdir -p data/videos
echo "Data directories created."

# --- Create default config if it doesn't exist ---
if [ ! -f "config.yaml" ]; then
    echo ""
    echo "Creating default config file..."
    python cli.py init --output config.yaml
    echo ""
    echo "Config file created at: $PROJECT_DIR/config.yaml"
    echo "Edit it to configure your camera, Hermes bridge, SMS, and rarity settings."
else
    echo ""
    echo "Config file already exists: config.yaml"
fi

# --- Create default rarity file if it doesn't exist ---
if [ ! -f "data/rarity.yaml" ]; then
    echo ""
    echo "Creating sample rarity file..."
    cat > data/rarity.yaml << 'RARITY_EOF'
location: "Your Location Here"
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
RARITY_EOF
    echo "Sample rarity file created at: data/rarity.yaml"
    echo "Edit it with species relevant to your location."
else
    echo "Rarity file already exists: data/rarity.yaml"
fi

# --- Run tests to verify installation ---
echo ""
echo "Running tests to verify installation..."
python -m pytest tests/ -q --tb=line 2>&1 | tail -5

# --- Done ---
echo ""
echo "=== Installation Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit config.yaml with your settings"
echo "  2. Edit data/rarity.yaml with your local bird species"
echo "  3. Test in mock mode:  python cli.py capture"
echo "  4. Start monitoring:   python cli.py run"
echo "  5. View dashboard:     http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo 'your-pi-ip'):9195"
echo ""
echo "For help: python cli.py --help"