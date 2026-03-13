#!/bin/bash
# DDR Intelligence Engine — Live Demo Runner
# This script validates your environment and starts the web server.

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        DDR Intelligence Engine — Live Demo                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    OS="windows"
else
    OS="unknown"
fi

echo "[1/5] Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 not found. Please install Python 3.11+ first."
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python $PYTHON_VERSION found"
echo ""

echo "[2/5] Checking virtual environment..."
if [[ ! -d ".venv" ]]; then
    echo "✗ Virtual environment not found. Creating one..."
    python3 -m venv .venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi
echo ""

echo "[3/5] Activating virtual environment..."
if [[ "$OS" == "windows" ]]; then
    source .venv/Scripts/activate
else
    source .venv/bin/activate
fi
echo "✓ Virtual environment activated"
echo ""

echo "[4/5] Installing Python dependencies..."
if [[ ! -f "requirements.txt" ]]; then
    echo "✗ requirements.txt not found"
    exit 1
fi
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

echo "[5/5] Validating configuration..."
if [[ ! -f ".env" ]]; then
    echo "⚠ .env file not found. Creating from template..."
    if [[ -f ".env.example" ]]; then
        cp .env.example .env
        echo "✓ .env file created"
    else
        echo "✗ .env.example not found"
        exit 1
    fi
else
    echo "✓ .env file found"
fi

# Check GROQ_API_KEY
if ! grep -q "GROQ_API_KEY=" .env || grep "GROQ_API_KEY=your_api_key_here" .env > /dev/null; then
    echo ""
    echo "⚠ GROQ_API_KEY not configured!"
    echo "  1. Get a free API key from: https://console.groq.com"
    echo "  2. Edit .env and set GROQ_API_KEY=<your-key>"
    echo ""
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    Environment Ready ✓                         ║"
echo "║                                                                ║"
echo "║  Starting Flask web server...                                 ║"
echo "║  Open http://localhost:5000 in your browser                   ║"
echo "║                                                                ║"
echo "║  Upload an inspection PDF and thermal image, then click       ║"
echo "║  'Generate DDR Report' to start the demo.                     ║"
echo "║                                                                ║"
echo "║  Press CTRL+C to stop the server.                             ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

python3 app.py
