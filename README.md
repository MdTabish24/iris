# 🎨 Image Automation System

Professional automation system for batch image processing with Canva-style adjustments.

## Features
- Web-based interface accessible from any device
- Drag & drop or browse to upload images
- Automatic processing with preset adjustments:
  - Sharpness: 75
  - Clarity: 50
  - Shadows: 30
  - Highlights: 10
  - Contrast: -95
  - Brightness: 90
  - Temperature: 20
- Download processed images as ZIP

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Application
```bash
python app.py
```

### 3. Access Locally
Open browser: `http://localhost:5000`

### 4. Access from Any Device (Optional)

#### Option A: Using ngrok (Recommended)
1. Download ngrok: https://ngrok.com/download
2. Run ngrok:
```bash
ngrok http 5000
```
3. Share the ngrok URL (e.g., `https://xxxx-xx-xx-xx-xx.ngrok.io`)

#### Option B: Local Network Access
- Find your IP: `ipconfig` (Windows) or `ifconfig` (Mac/Linux)
- Access from other devices: `http://YOUR_IP:5000`

## Usage
1. Open the web interface
2. Upload images (drag & drop or browse)
3. Click "Process Images"
4. Download the processed ZIP file

## Supported Formats
- PNG, JPG, JPEG, WEBP, BMP

## Notes
- Maximum upload size: 500MB
- Processed files are automatically cleaned after download
- All adjustments are applied automatically based on Canva presets
