from flask import Flask, render_template, request, send_file, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
import zipfile
from werkzeug.utils import secure_filename
import shutil
import numpy as np
from scipy.ndimage import gaussian_filter

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'processed'
app.config['GALLERY_FOLDER'] = 'gallery'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
os.makedirs(app.config['GALLERY_FOLDER'], exist_ok=True)

def adjust_shadows_highlights(img, shadows=30, highlights=11):
    """Shadows aur highlights ko adjust karta hai - high quality"""
    arr = np.array(img, dtype=np.float64) / 255.0

    # Shadows adjust karo (dark areas ko brighten)
    shadow_mask = 1.0 - arr
    shadow_boost = shadow_mask ** 2
    arr = arr + (shadow_boost * (shadows / 100.0) * 0.3)

    # Highlights adjust karo (bright areas ko thoda dim)
    highlight_mask = arr
    highlight_adjust = highlight_mask ** 2
    arr = arr + (highlight_adjust * (highlights / 100.0) * 0.1)

    arr = np.clip(arr, 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))

def apply_clarity(img, amount=42):
    """Clarity effect - mid-tone contrast badhata hai - ULTRA HIGH quality for iris detection"""
    arr = np.array(img, dtype=np.float64)

    # Multi-scale clarity for better detail
    blurred1 = np.zeros_like(arr)
    blurred2 = np.zeros_like(arr)
    for i in range(3):
        blurred1[:,:,i] = gaussian_filter(arr[:,:,i], sigma=1.5, mode='reflect')
        blurred2[:,:,i] = gaussian_filter(arr[:,:,i], sigma=3.0, mode='reflect')

    # Multi-scale detail extraction
    detail1 = arr - blurred1
    detail2 = arr - blurred2

    # Enhanced clarity with edge preservation
    enhanced = arr + detail1 * (amount / 100.0) * 1.2 + detail2 * (amount / 100.0) * 0.4

    enhanced = np.clip(enhanced, 0, 255)
    return Image.fromarray(enhanced.astype(np.uint8))

def apply_canva_adjustments(img):
    """Canva ke exact adjustments apply karta hai - HIGH QUALITY"""

    # Original size preserve karo
    original_size = img.size

    # Agar image choti hai toh upscale karo
    if img.size[0] < 1920 or img.size[1] < 1920:
        scale_factor = max(1920 / img.size[0], 1920 / img.size[1])
        new_size = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    # 1. Contrast: -67 (kam karna hai)
    # Slider -100 to +100, toh -67 matlab 0.67 reduction
    contrast = ImageEnhance.Contrast(img)
    img = contrast.enhance(1.0 - (2/200))  # = 0.665

    # 2. Brightness: 85 (badhana hai)
    # Slider -100 to +100, toh +85 matlab moderate increase
    brightness = ImageEnhance.Brightness(img)
    img = brightness.enhance(1.0 + (5/200))  # = 1.425

    # 3. Shadows: 30 aur Highlights: 11
    img = adjust_shadows_highlights(img, shadows=30, highlights=11)

    # 4. Clarity: 42 - BOOSTED for iris detection
    img = apply_clarity(img, amount=65)

    # 5. Sharpness: 72 - ENHANCED for iris scanner
    sharpness = ImageEnhance.Sharpness(img)
    img = sharpness.enhance(2.2)
    
    # 6. Edge enhancement for iris details
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    
    # 7. Final detail sharpening
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))
    
    # 8. Belvedere filter (Desaturate + Purple overlay)
    # Desaturate heavily
    color = ImageEnhance.Color(img)
    img = color.enhance(0.2)
    
    # Strong purple overlay
    arr = np.array(img, dtype=np.float32)
    arr[:,:,0] = np.minimum(arr[:,:,0] + 50, 255)  # Red boost
    arr[:,:,1] = arr[:,:,1] * 0.85  # Green reduce
    arr[:,:,2] = np.minimum(arr[:,:,2] + 70, 255)  # Blue strong boost
    
    arr = np.clip(arr, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    
    return img

def process_images(input_folder, output_folder):
    # Clear gallery folder
    for f in os.listdir(output_folder):
        os.remove(os.path.join(output_folder, f))
    
    processed = []
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
            try:
                img_path = os.path.join(input_folder, filename)
                img = Image.open(img_path).convert('RGB')
                dpi = img.info.get('dpi', (300, 300))
                img = apply_canva_adjustments(img)
                output_path = os.path.join(output_folder, filename)
                img.save(output_path, quality=98, dpi=dpi, optimize=False, subsampling=0)
                processed.append(filename)
            except Exception as e:
                print(f"Error processing {filename}: {e}")
    return processed

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/input')
def input_page():
    return render_template('input.html')

@app.route('/process-page')
def process_page():
    return render_template('process.html')

@app.route('/upload', methods=['POST'])
def upload():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files uploaded'}), 400

    files = request.files.getlist('files[]')
    upload_path = app.config['UPLOAD_FOLDER']
    
    # Clear previous uploads
    for f in os.listdir(upload_path):
        os.remove(os.path.join(upload_path, f))
    
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_path, filename))

    return jsonify({'uploaded': len(files)})

@app.route('/process', methods=['POST'])
def process():
    upload_path = app.config['UPLOAD_FOLDER']
    if not os.listdir(upload_path):
        return jsonify({'error': 'No images to process'}), 400
    
    processed = process_images(upload_path, app.config['GALLERY_FOLDER'])
    return jsonify({'processed': len(processed)})

@app.route('/gallery')
def gallery():
    images = [f for f in os.listdir(app.config['GALLERY_FOLDER']) 
              if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
    return render_template('gallery.html', images=images)

@app.route('/gallery/<filename>')
def serve_image(filename):
    return send_file(os.path.join(app.config['GALLERY_FOLDER'], filename))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
