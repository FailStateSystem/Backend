#!/bin/bash

# FailState Backend Startup Script

echo "🚀 Starting FailState Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "📝 Please copy .env.example to .env and configure it:"
    echo "   cp .env.example .env"
    echo ""
    read -p "Do you want to create .env now? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cp .env.example .env
        echo "✅ Created .env file. Please edit it with your credentials."
        exit 0
    else
        echo "❌ Cannot start without .env file. Exiting."
        exit 1
    fi
fi

# Start the server
echo "✨ Starting FastAPI server..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

