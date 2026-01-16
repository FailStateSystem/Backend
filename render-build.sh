#!/usr/bin/env bash
# Render build script for installing system dependencies

set -o errexit

# Install Tesseract OCR (for screenshot detection)
echo "Installing Tesseract OCR..."
apt-get update
apt-get install -y tesseract-ocr tesseract-ocr-eng

# Install Python dependencies
echo "Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Build completed successfully!"

