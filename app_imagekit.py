from flask import Flask, render_template, request, send_file, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
import zipfile
from werkzeug.utils import secure_filename
import shutil
import numpy as np
from scipy.ndimage import gaussian_filter
import io
import requests
import base64
from dotenv import load_dotenv
import threading

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# ImageKit credentials from environment
IMAGEKIT_PRIVATE_KEY = os.getenv('IMAGEKIT_PRIVATE_KEY')
IMAGEKIT_PUBLIC_KEY = os.getenv('IMAGEKIT_PUBLIC_KEY')
IMAGEKIT_URL_ENDPOINT = os.getenv('IMAGEKIT_URL_ENDPOINT')

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
    max_size = 1920
    if img.size[0] > max_size or img.size[1] > max_size:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

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
    result = Image.fromarray(arr.astype(np.uint8))
    del arr
    
    return result

def upload_to_imagekit(image, filename):
    try:
        if not IMAGEKIT_PRIVATE_KEY:
            print("ImageKit credentials missing", flush=True)
            return None
        
        if not image or image.size[0] == 0 or image.size[1] == 0:
            print(f"✗ Invalid image: {image}", flush=True)
            return None
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=90)
        img_bytes = buffer.getvalue()
        buffer.close()
        
        if len(img_bytes) < 1000:
            print(f"✗ Image too small: {len(img_bytes)} bytes", flush=True)
            return None
        
        print(f"  - Uploading {len(img_bytes)} bytes to ImageKit...", flush=True)
        
        # Direct API call
        url = "https://upload.imagekit.io/api/v1/files/upload"
        
        files = {
            'file': (f"enhanced_{filename}", img_bytes, 'image/jpeg')
        }
        
        data = {
            'fileName': f"enhanced_{filename}",
            'folder': '/iris/'
        }
        
        auth = (IMAGEKIT_PRIVATE_KEY + ':', '')
        
        response = requests.post(url, files=files, data=data, auth=auth)
        
        print(f"  - Response status: {response.status_code}", flush=True)
        
        if response.status_code == 200:
            result = response.json()
            img_url = result.get('url')
            if img_url:
                print(f"✓ Upload successful: {img_url}", flush=True)
                return img_url
        
        print(f"✗ Upload failed: {response.text}", flush=True)
        return None
        
    except Exception as e:
        print(f"✗ ImageKit error: {type(e).__name__}: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return None

def process_images(input_folder):
    global image_gallery, processing_status
    image_gallery = []
    
    print(f"\n=== Starting to process images from: {input_folder} ===", flush=True)
    processed = []
    failed = []
    
    files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
    print(f"Found {len(files)} image files: {files}", flush=True)
    
    for filename in files:
        img = None
        try:
            print(f"\n[{len(processed)+1}/{len(files)}] Processing {filename}...", flush=True)
            img_path = os.path.join(input_folder, filename)
            img = Image.open(img_path).convert('RGB')
            print(f"  - Image loaded: {img.size}, mode: {img.mode}", flush=True)
            
            if img.size[0] == 0 or img.size[1] == 0:
                print(f"  ✗ Invalid image size", flush=True)
                failed.append(filename)
                continue
            
            img = apply_canva_adjustments(img)
            print(f"  - Adjustments applied: {img.size}, mode: {img.mode}", flush=True)
            
            if not img or img.size[0] == 0:
                print(f"  ✗ Image corrupted after adjustments", flush=True)
                failed.append(filename)
                continue
            
            # Test save locally
            test_path = f"test_{filename}"
            img.save(test_path, format='JPEG', quality=90)
            test_size = os.path.getsize(test_path)
            print(f"  - Test save: {test_size} bytes at {test_path}", flush=True)
            
            img_url = upload_to_imagekit(img, filename)
            if img_url:
                image_gallery.append({'filename': filename, 'url': img_url})
                processed.append(filename)
                processing_status['processed'] = len(processed)
                print(f"  ✓ SUCCESS: {filename} -> {img_url}", flush=True)
            else:
                failed.append(filename)
                print(f"  ✗ FAILED: {filename} upload returned None", flush=True)
                
        except Exception as e:
            failed.append(filename)
            print(f"  ✗ ERROR processing {filename}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if img:
                img.close()
            del img
            import gc
            gc.collect()
    
    print(f"\n=== FINAL RESULTS ===", flush=True)
    print(f"Processed: {len(processed)}", flush=True)
    print(f"Failed: {len(failed)}", flush=True)
    print(f"Gallery has {len(image_gallery)} images", flush=True)
    print(f"Gallery contents: {image_gallery}", flush=True)
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
    
    saved = 0
    for file in files:
        if file.filename and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
            filename = secure_filename(file.filename)
            file.save(os.path.join(upload_path, filename))
            saved += 1

    return jsonify({'uploaded': saved, 'success': True})

processing_status = {'status': 'idle', 'processed': 0, 'total': 0}

def background_process(upload_path):
    global processing_status
    try:
        processing_status['status'] = 'processing'
        processed = process_images(upload_path)
        processing_status['processed'] = len(processed)
        processing_status['status'] = 'completed'
        print(f"=== Processing complete: {len(processed)} images ===")
        
        # Clean up uploads folder
        for f in os.listdir(upload_path):
            try:
                os.remove(os.path.join(upload_path, f))
            except:
                pass
        print("Uploads folder cleaned")
        
    except Exception as e:
        processing_status['status'] = 'failed'
        processing_status['error'] = str(e)
        print(f"Background process error: {e}")
    finally:
        import gc
        gc.collect()

@app.route('/process', methods=['POST'])
def process():
    try:
        print("=== Starting image processing ===")
        upload_path = app.config['UPLOAD_FOLDER']
        
        if not os.path.exists(upload_path):
            return jsonify({'error': 'Upload folder not found', 'success': False}), 400
            
        files = [f for f in os.listdir(upload_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
        if not files:
            return jsonify({'error': 'No images to process', 'success': False}), 400
        
        processing_status['total'] = len(files)
        processing_status['status'] = 'starting'
        
        thread = threading.Thread(target=background_process, args=(upload_path,))
        thread.daemon = True
        thread.start()
        
        return jsonify({'success': True, 'message': 'Processing started', 'total': len(files)}), 200
        
    except Exception as e:
        print(f"Process error: {e}")
        return jsonify({'error': str(e), 'success': False}), 500

@app.route('/status', methods=['GET'])
def status():
    return jsonify(processing_status), 200

@app.route('/gallery')
def gallery():
    print(f"\n=== GALLERY ROUTE CALLED ===")
    print(f"image_gallery has {len(image_gallery)} images")
    print(f"Gallery contents: {image_gallery}")
    return render_template('gallery.html', images=image_gallery)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)