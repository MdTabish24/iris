# from flask import Flask, render_template, request, jsonify
# import os
# from PIL import Image, ImageEnhance, ImageFilter
# from werkzeug.utils import secure_filename
# import numpy as np
# from scipy.ndimage import gaussian_filter
# import io
# import requests
# from dotenv import load_dotenv
# import threading
# import gc

# load_dotenv()

# app = Flask(__name__)
# app.config['UPLOAD_FOLDER'] = 'uploads'
# app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# # ImageKit credentials from environment
# IMAGEKIT_PRIVATE_KEY = os.getenv('IMAGEKIT_PRIVATE_KEY')
# IMAGEKIT_PUBLIC_KEY = os.getenv('IMAGEKIT_PUBLIC_KEY')
# IMAGEKIT_URL_ENDPOINT = os.getenv('IMAGEKIT_URL_ENDPOINT')

# os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# # Store image URLs
# image_gallery = []

# def adjust_shadows_highlights(img, shadows=30, highlights=11):
#     arr = np.array(img, dtype=np.float64) / 255.0
#     shadow_mask = 1.0 - arr
#     shadow_boost = shadow_mask ** 2
#     arr = arr + (shadow_boost * (shadows / 100.0) * 0.3)
#     highlight_mask = arr
#     highlight_adjust = highlight_mask ** 2
#     arr = arr + (highlight_adjust * (highlights / 100.0) * 0.1)
#     arr = np.clip(arr, 0, 1)
#     return Image.fromarray((arr * 255).astype(np.uint8))

# def apply_clarity(img, amount=42):
#     arr = np.array(img, dtype=np.float64)
#     blurred1 = np.zeros_like(arr)
#     blurred2 = np.zeros_like(arr)
#     for i in range(3):
#         blurred1[:,:,i] = gaussian_filter(arr[:,:,i], sigma=1.5, mode='reflect')
#         blurred2[:,:,i] = gaussian_filter(arr[:,:,i], sigma=3.0, mode='reflect')
#     detail1 = arr - blurred1
#     detail2 = arr - blurred2
#     enhanced = arr + detail1 * (amount / 100.0) * 1.2 + detail2 * (amount / 100.0) * 0.4
#     enhanced = np.clip(enhanced, 0, 255)
#     return Image.fromarray(enhanced.astype(np.uint8))

# def apply_canva_adjustments(img):
#     # Limit max size to prevent memory issues on free tier
#     max_size = 1200
#     if img.size[0] > max_size or img.size[1] > max_size:
#         ratio = min(max_size / img.size[0], max_size / img.size[1])
#         new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
#         img = img.resize(new_size, Image.Resampling.LANCZOS)
#     elif img.size[0] < 800 and img.size[1] < 800:
#         scale_factor = min(2.0, max(800 / img.size[0], 800 / img.size[1]))
#         new_size = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
#         img = img.resize(new_size, Image.Resampling.LANCZOS)

#     # Contrast: -67
#     contrast = ImageEnhance.Contrast(img)
#     img = contrast.enhance(1.0 - (67/200))

#     # Brightness: 85
#     brightness = ImageEnhance.Brightness(img)
#     img = brightness.enhance(1.0 + (85/200))

#     # Shadows: 30, Highlights: 11
#     img = adjust_shadows_highlights(img, shadows=30, highlights=11)

#     # Clarity: 42 (reduced to 45 for memory efficiency)
#     img = apply_clarity(img, amount=45)

#     # Sharpness: 72 (enhanced to 2.2)
#     sharpness = ImageEnhance.Sharpness(img)
#     img = sharpness.enhance(2.2)

#     # Edge enhancement
#     img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

#     # Final sharpening
#     img = img.filter(ImageFilter.UnsharpMask(radius=1.5, percent=180, threshold=2))

#     # Belvedere filter (Desaturate + Purple overlay)
#     color = ImageEnhance.Color(img)
#     img = color.enhance(0.2)

#     arr = np.array(img, dtype=np.float32)
#     arr[:,:,0] = np.minimum(arr[:,:,0] + 50, 255)  # Red boost
#     arr[:,:,1] = arr[:,:,1] * 0.85  # Green reduce
#     arr[:,:,2] = np.minimum(arr[:,:,2] + 70, 255)  # Blue boost

#     arr = np.clip(arr, 0, 255)
#     result = Image.fromarray(arr.astype(np.uint8))
#     del arr

#     return result

# def upload_to_imagekit(image, filename):
#     try:
#         if not IMAGEKIT_PRIVATE_KEY:
#             print("ImageKit credentials missing", flush=True)
#             return None

#         if not image or image.size[0] == 0 or image.size[1] == 0:
#             print(f"✗ Invalid image: {image}", flush=True)
#             return None

#         buffer = io.BytesIO()
#         image.save(buffer, format='JPEG', quality=85, optimize=True)
#         img_bytes = buffer.getvalue()
#         buffer.close()
#         del buffer

#         if len(img_bytes) < 1000:
#             print(f"✗ Image too small: {len(img_bytes)} bytes", flush=True)
#             return None

#         print(f"  - Uploading {len(img_bytes)} bytes to ImageKit...", flush=True)

#         # Direct API call
#         url = "https://upload.imagekit.io/api/v1/files/upload"

#         files = {
#             'file': (f"enhanced_{filename}", img_bytes, 'image/jpeg')
#         }

#         data = {
#             'fileName': f"enhanced_{filename}",
#             'folder': '/iris/'
#         }

#         auth = (IMAGEKIT_PRIVATE_KEY + ':', '')

#         response = requests.post(url, files=files, data=data, auth=auth, timeout=30)

#         print(f"  - Response status: {response.status_code}", flush=True)

#         if response.status_code == 200:
#             result = response.json()
#             img_url = result.get('url')
#             if img_url:
#                 print(f"✓ Upload successful: {img_url}", flush=True)
#                 return img_url

#         print(f"✗ Upload failed: {response.text}", flush=True)
#         return None

#     except requests.exceptions.Timeout:
#         print(f"✗ ImageKit timeout after 30s", flush=True)
#         return None
#     except Exception as e:
#         print(f"✗ ImageKit error: {type(e).__name__}: {e}", flush=True)
#         return None

# def process_images(input_folder):
#     global image_gallery, processing_status
#     image_gallery = []

#     print(f"\n=== Starting to process images from: {input_folder} ===", flush=True)
#     processed = []
#     failed = []

#     files = [f for f in os.listdir(input_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
#     print(f"Found {len(files)} image files: {files}", flush=True)

#     for filename in files:
#         img = None
#         try:
#             print(f"\n[{len(processed)+1}/{len(files)}] Processing {filename}...", flush=True)
#             img_path = os.path.join(input_folder, filename)
#             img = Image.open(img_path).convert('RGB')
#             print(f"  - Image loaded: {img.size}, mode: {img.mode}", flush=True)

#             if img.size[0] == 0 or img.size[1] == 0:
#                 print(f"  ✗ Invalid image size", flush=True)
#                 failed.append(filename)
#                 continue

#             print(f"  - Starting adjustments...", flush=True)
#             img = apply_canva_adjustments(img)
#             print(f"  - Adjustments applied: {img.size}, mode: {img.mode}", flush=True)
#             gc.collect()

#             if not img or img.size[0] == 0:
#                 print(f"  ✗ Image corrupted after adjustments", flush=True)
#                 failed.append(filename)
#                 continue

#             img_url = upload_to_imagekit(img, filename)
#             if img_url:
#                 image_gallery.append({'filename': filename, 'url': img_url})
#                 processed.append(filename)
#                 processing_status['processed'] = len(processed)
#                 print(f"  ✓ SUCCESS: {filename} -> {img_url}", flush=True)
#             else:
#                 failed.append(filename)
#                 print(f"  ✗ FAILED: {filename} upload returned None", flush=True)

#         except Exception as e:
#             failed.append(filename)
#             print(f"  ✗ ERROR processing {filename}: {e}", flush=True)
#         finally:
#             if img:
#                 img.close()
#             del img
#             gc.collect()

#     print(f"\n=== FINAL RESULTS ===", flush=True)
#     print(f"Processed: {len(processed)}", flush=True)
#     print(f"Failed: {len(failed)}", flush=True)
#     print(f"Gallery has {len(image_gallery)} images", flush=True)
#     print(f"Gallery contents: {image_gallery}", flush=True)
#     return processed

# @app.route('/')
# def index():
#     return render_template('index.html')

# @app.route('/input')
# def input_page():
#     return render_template('input.html')

# @app.route('/process-page')
# def process_page():
#     return render_template('process.html')

# @app.route('/upload', methods=['POST'])
# def upload():
#     if 'files[]' not in request.files:
#         return jsonify({'error': 'No files uploaded'}), 400

#     files = request.files.getlist('files[]')
#     upload_path = app.config['UPLOAD_FOLDER']

#     for f in os.listdir(upload_path):
#         os.remove(os.path.join(upload_path, f))

#     saved = 0
#     for file in files:
#         if file.filename and file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp')):
#             filename = secure_filename(file.filename)
#             file.save(os.path.join(upload_path, filename))
#             saved += 1

#     return jsonify({'uploaded': saved, 'success': True})

# processing_status = {'status': 'idle', 'processed': 0, 'total': 0}

# def background_process(upload_path):
#     global processing_status
#     try:
#         processing_status['status'] = 'processing'
#         processed = process_images(upload_path)
#         processing_status['processed'] = len(processed)
#         processing_status['status'] = 'completed'
#         print(f"=== Processing complete: {len(processed)} images ===")

#         # Clean up uploads folder
#         for f in os.listdir(upload_path):
#             try:
#                 os.remove(os.path.join(upload_path, f))
#             except:
#                 pass
#         print("Uploads folder cleaned")

#     except Exception as e:
#         processing_status['status'] = 'failed'
#         processing_status['error'] = str(e)
#         print(f"Background process error: {e}", flush=True)
#     finally:
#         gc.collect()

# @app.route('/process', methods=['POST'])
# def process():
#     try:
#         print("=== Starting image processing ===")
#         upload_path = app.config['UPLOAD_FOLDER']

#         if not os.path.exists(upload_path):
#             return jsonify({'error': 'Upload folder not found', 'success': False}), 400

#         files = [f for f in os.listdir(upload_path) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.bmp'))]
#         if not files:
#             return jsonify({'error': 'No images to process', 'success': False}), 400

#         processing_status['total'] = len(files)
#         processing_status['status'] = 'starting'

#         thread = threading.Thread(target=background_process, args=(upload_path,))
#         thread.daemon = True
#         thread.start()

#         return jsonify({'success': True, 'message': 'Processing started', 'total': len(files)}), 200

#     except Exception as e:
#         print(f"Process error: {e}")
#         return jsonify({'error': str(e), 'success': False}), 500

# @app.route('/status', methods=['GET'])
# def status():
#     try:
#         return jsonify(processing_status), 200
#     except:
#         return jsonify({'status': 'idle', 'processed': 0, 'total': 0}), 200

# @app.route('/health', methods=['GET'])
# def health():
#     return jsonify({'status': 'ok'}), 200

# @app.route('/gallery')
# def gallery():
#     print(f"\n=== GALLERY ROUTE CALLED ===")
#     print(f"image_gallery has {len(image_gallery)} images")
#     print(f"Gallery contents: {image_gallery}")
#     return render_template('gallery.html', images=image_gallery)

# if __name__ == '__main__':
#     port = int(os.environ.get('PORT', 5000))
#     app.run(debug=False, host='0.0.0.0', port=port)


from flask import Flask, render_template, request, jsonify
import os
from PIL import Image, ImageEnhance, ImageFilter
from werkzeug.utils import secure_filename
import numpy as np
from scipy.ndimage import gaussian_filter
import io
import requests
from dotenv import load_dotenv
import threading
import gc

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

def adjust_shadows_highlights(img, shadows=50, highlights=5):
    """Enhanced shadows and reduced highlights for darker, richer look"""
    arr = np.array(img, dtype=np.float64) / 255.0

    # Boost shadows more
    shadow_mask = 1.0 - arr
    shadow_boost = shadow_mask ** 2
    arr = arr + (shadow_boost * (shadows / 100.0) * 0.4)

    # Reduce highlights less
    highlight_mask = arr
    highlight_adjust = highlight_mask ** 2
    arr = arr + (highlight_adjust * (highlights / 100.0) * 0.05)

    arr = np.clip(arr, 0, 1)
    return Image.fromarray((arr * 255).astype(np.uint8))

def apply_clarity(img, amount=60):
    """Enhanced clarity for more detail"""
    arr = np.array(img, dtype=np.float64)
    blurred1 = np.zeros_like(arr)
    blurred2 = np.zeros_like(arr)

    for i in range(3):
        blurred1[:,:,i] = gaussian_filter(arr[:,:,i], sigma=1.5, mode='reflect')
        blurred2[:,:,i] = gaussian_filter(arr[:,:,i], sigma=3.0, mode='reflect')

    detail1 = arr - blurred1
    detail2 = arr - blurred2
    enhanced = arr + detail1 * (amount / 100.0) * 1.5 + detail2 * (amount / 100.0) * 0.5
    enhanced = np.clip(enhanced, 0, 255)

    return Image.fromarray(enhanced.astype(np.uint8))

def apply_canva_adjustments(img):
    """Complete enhancement function - matches desired purple eye output"""

    # Limit max size to prevent memory issues on free tier
    max_size = 1200
    if img.size[0] > max_size or img.size[1] > max_size:
        ratio = min(max_size / img.size[0], max_size / img.size[1])
        new_size = (int(img.size[0] * ratio), int(img.size[1] * ratio))
        img = img.resize(new_size, Image.Resampling.LANCZOS)
    elif img.size[0] < 800 and img.size[1] < 800:
        scale_factor = min(2.0, max(800 / img.size[0], 800 / img.size[1]))
        new_size = (int(img.size[0] * scale_factor), int(img.size[1] * scale_factor))
        img = img.resize(new_size, Image.Resampling.LANCZOS)

    # STEP 1: INCREASE Contrast (reversed from -67 to strong boost)
    contrast = ImageEnhance.Contrast(img)
    img = contrast.enhance(1.8)  # Strong contrast for dark, rich look

    # STEP 2: REDUCE Brightness (reversed from +85 to darker)
    brightness = ImageEnhance.Brightness(img)
    img = brightness.enhance(0.85)  # Slightly darker overall

    # STEP 3: Enhanced Shadows & Reduced Highlights
    img = adjust_shadows_highlights(img, shadows=50, highlights=5)

    # STEP 4: High Clarity for detail
    img = apply_clarity(img, amount=60)

    # STEP 5: Strong Sharpness
    sharpness = ImageEnhance.Sharpness(img)
    img = sharpness.enhance(2.5)

    # STEP 6: Edge enhancement
    img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)

    # STEP 7: Strong unsharp mask
    img = img.filter(ImageFilter.UnsharpMask(radius=2.0, percent=200, threshold=1))

    # STEP 8: Keep more saturation (0.7 instead of 0.2)
    color = ImageEnhance.Color(img)
    img = color.enhance(0.7)

    # STEP 9: Apply strong purple/violet overlay
    arr = np.array(img, dtype=np.float32)

    # Enhanced purple tint - more aggressive
    arr[:,:,0] = np.minimum(arr[:,:,0] * 1.15 + 40, 255)  # Red boost
    arr[:,:,1] = arr[:,:,1] * 0.75  # Green reduce for purple
    arr[:,:,2] = np.minimum(arr[:,:,2] * 1.25 + 60, 255)  # Blue boost strong

    arr = np.clip(arr, 0, 255)
    result = Image.fromarray(arr.astype(np.uint8))

    # STEP 10: Final saturation boost for vibrant purple
    color = ImageEnhance.Color(result)
    result = color.enhance(1.3)

    # STEP 11: Final contrast boost for depth
    contrast = ImageEnhance.Contrast(result)
    result = contrast.enhance(1.2)

    del arr
    gc.collect()

    return result

def upload_to_imagekit(image, filename):
    """Upload processed image to ImageKit"""
    try:
        if not IMAGEKIT_PRIVATE_KEY:
            print("ImageKit credentials missing", flush=True)
            return None

        if not image or image.size[0] == 0 or image.size[1] == 0:
            print(f"✗ Invalid image: {image}", flush=True)
            return None

        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=85, optimize=True)
        img_bytes = buffer.getvalue()
        buffer.close()
        del buffer

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

        response = requests.post(url, files=files, data=data, auth=auth, timeout=30)

        print(f"  - Response status: {response.status_code}", flush=True)

        if response.status_code == 200:
            result = response.json()
            img_url = result.get('url')
            if img_url:
                print(f"✓ Upload successful: {img_url}", flush=True)
                return img_url

        print(f"✗ Upload failed: {response.text}", flush=True)
        return None

    except requests.exceptions.Timeout:
        print(f"✗ ImageKit timeout after 30s", flush=True)
        return None
    except Exception as e:
        print(f"✗ ImageKit error: {type(e).__name__}: {e}", flush=True)
        return None

def process_images(input_folder):
    """Process all images in folder with enhanced adjustments"""
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

            print(f"  - Starting adjustments...", flush=True)
            img = apply_canva_adjustments(img)
            print(f"  - Adjustments applied: {img.size}, mode: {img.mode}", flush=True)
            gc.collect()

            if not img or img.size[0] == 0:
                print(f"  ✗ Image corrupted after adjustments", flush=True)
                failed.append(filename)
                continue

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
            print(f"  ✗ ERROR processing {filename}: {e}", flush=True)
        finally:
            if img:
                img.close()
            del img
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

    # Clear old files
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
    """Background thread for processing images"""
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
        print(f"Background process error: {e}", flush=True)
    finally:
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
    try:
        return jsonify(processing_status), 200
    except:
        return jsonify({'status': 'idle', 'processed': 0, 'total': 0}), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'}), 200

@app.route('/gallery')
def gallery():
    print(f"\n=== GALLERY ROUTE CALLED ===")
    print(f"image_gallery has {len(image_gallery)} images")
    print(f"Gallery contents: {image_gallery}")
    return render_template('gallery.html', images=image_gallery)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)
