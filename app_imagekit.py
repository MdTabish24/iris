from flask import Flask, render_template, request, send_file, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
import zipfile
from werkzeug.utils import secure_filename
import shutil
import numpy as np
from scipy.ndimage import gaussian_filter
import io
from imagekitio import ImageKit
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# ImageKit credentials from environment
IMAGEKIT_PRIVATE_KEY = os.getenv('IMAGEKIT_PRIVATE_KEY')
IMAGEKIT_PUBLIC_KEY = os.getenv('IMAGEKIT_PUBLIC_KEY')
IMAGEKIT_URL_ENDPOINT = os.getenv('IMAGEKIT_URL_ENDPOINT')

imagekit = ImageKit(
    private_key=IMAGEKIT_PRIVATE_KEY,
    public_key=IMAGEKIT_PUBLIC_KEY,
    url_endpoint=IMAGEKIT_URL_ENDPOINT
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Store image URLs
image_gallery = []

def adjust_shadows_highlights(img, shadows=30, highlights=11):
    arr = np.array(img, dtype=np.float64) / 255.0
    shadow_mask = 1.0 - arr
    shadow_boost = shadow_mask ** 2
    arr = arr + (shadow_boost * (shadows / 100.0) * 0.3)
    highlight_mask = arr
    highlight_adjust = highlight_mask ** 2
    arr = arr + (highlight_adjust * (highlights / 100.0) * 0.1)
    arr = np.clip(arr, 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))

def apply_clarity(img, amount=42):
    arr = np.array(img, dtype=np.float64)
    blurred1 = np.zeros_like(arr)
    blurred2 = np.zeros_like(arr)
    for i in range(3):
        blurred1[:,:,i] = gaussian_filter(arr[:,:,i], sigma=1.5, mode='reflect')
        blurred2[:,:,i] = gaussian_filter(arr[:,:,i], sigma=3.0, mode='reflect')
    detail1 = arr - blurred1
    detail2 = arr - blurred2
    enhanced = arr + detail1 * (amount / 100.0) * 1.2 + detail2 * (amount / 100.0) * 0.4
    enhanced = np.clip(enhanced, 0, 255)
    return Image.fromarray(enhanced.astype(np.uint8))

def apply_canva_adjustments(img):
    if img.size[0] < 1920 or img.size[1] < 1920:
        scale_factor = max(1920 / img.size[0], 1920 / img.size[1])
        new_size = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    contrast = ImageEnhance.Contrast(img)
    img = contrast.enhance(0.665)
    brightness = ImageEnhance.Brightness(img)
    img = brightness.enhance(1.425)
    img = adjust_shadows_highlights(img, shadows=30, highlights=11)
    img = apply_clarity(img, amount=65)
    sharpness = ImageEnhance.Sharpness(img)
    img = sharpness.enhance(2.2)
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
    img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))
    
    color = ImageEnhance.Color(img)
    img = color.enhance(0.2)
    arr = np.array(img, dtype=np.float32)
    arr[:,:,0] = np.minimum(arr[:,:,0] + 50, 255)
    arr[:,:,1] = arr[:,:,1] * 0.85
    arr[:,:,2] = np.minimum(arr[:,:,2] + 70, 255)
    arr = np.clip(arr, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8))
    
    return img

def upload_to_imagekit(image, filename):
    try:
        if not IMAGEKIT_PRIVATE_KEY:
            print("ImageKit credentials missing")
            return None
            
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=95)
        img_bytes = buffer.getvalue()
        
        upload = imagekit.upload_file(
            file=img_bytes,
            file_name=f"enhanced_{filename}",
            options={"folder": "/iris/"},
            timeout=30
        )
        
        if upload and hasattr(upload, 'url'):
            print(f"Upload successful: {upload.url}")
            return upload.url
        elif upload and isinstance(upload, dict) and 'url' in upload:
            print(f"Upload successful: {upload['url']}")
            return upload['url']
        print(f"Upload failed: {upload}")
        return None
    except Exception as e:
        print(f"ImageKit upload error: {e}")
        return None

def process_images(input_folder):
    global image_gallery
    image_gallery = []
    
    processed = []
    failed = []
    for filename in os.listdir(input_folder):
        if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
            try:
                print(f"Processing {filename}...")
                img_path = os.path.join(input_folder, filename)
                img = Image.open(img_path).convert('RGB')
                img = apply_canva_adjustments(img)
                
                img_url = upload_to_imagekit(img, filename)
                if img_url:
                    image_gallery.append({'filename': filename, 'url': img_url})
                    processed.append(filename)
                    print(f"✓ {filename} processed")
                else:
                    failed.append(filename)
                    print(f"✗ {filename} upload failed")
                    
            except Exception as e:
                failed.append(filename)
                print(f"Error processing {filename}: {e}")
    
    print(f"Processed: {len(processed)}, Failed: {len(failed)}")
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
    
    for f in os.listdir(upload_path):
        os.remove(os.path.join(upload_path, f))
    
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_path, filename))

    return jsonify({'uploaded': len(files), 'redirect': '/process-page'})

@app.route('/process', methods=['POST'])
def process():
    try:
        print("=== Starting image processing ===")
        upload_path = app.config['UPLOAD_FOLDER']
        
        if not os.path.exists(upload_path):
            print(f"Upload path does not exist: {upload_path}")
            return jsonify({'error': 'Upload folder not found', 'success': False}), 400
            
        files = os.listdir(upload_path)
        if not files:
            print("No files in upload folder")
            return jsonify({'error': 'No images to process', 'success': False}), 400
        
        print(f"Found {len(files)} files to process")
        processed = process_images(upload_path)
        
        print(f"=== Processing complete: {len(processed)} images ===")
        return jsonify({'processed': len(processed), 'success': True}), 200
        
    except Exception as e:
        print(f"Process error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'{type(e).__name__}: {str(e)}', 'success': False}), 500

@app.route('/gallery')
def gallery():
    return render_template('gallery.html', images=image_gallery)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)