from django.http import JsonResponse
import time
import base64
from pyzkfp import ZKFP2
from PIL import Image, ImageEnhance
import io
import numpy as np

def capture_fingerprint(request):
    zkfp2 = ZKFP2()
    zkfp2.Init()

    device_count = zkfp2.GetDeviceCount()
    if device_count == 0:
        zkfp2.Terminate()
        return JsonResponse({"captured": False, "error": "No fingerprint devices found"})

    try:
        zkfp2.OpenDevice(0)
    except Exception as e:
        zkfp2.Terminate()
        return JsonResponse({"captured": False, "error": f"Cannot open device: {e}"})

    start_time = time.time()
    capture = None

    try:
        while True:
            if time.time() - start_time >= 15:
                break
            result = zkfp2.AcquireFingerprint()
            if result:
                capture = result
                break
    except Exception as e:
        zkfp2.CloseDevice()
        zkfp2.Terminate()
        return JsonResponse({"captured": False, "error": f"Capture failed: {e}"})

    fingerprint_base64 = None
    if capture:
        tmp, img_bytes = capture

        width, height = zkfp2.width, zkfp2.height

        # Convert raw bytes to grayscale image
        img_pil = Image.frombytes('L', (width, height), img_bytes)

        # Convert to numpy for percentile normalization (brightens image)
        img_array = np.array(img_pil, dtype=np.float32)
        low, high = np.percentile(img_array, 5), np.percentile(img_array, 95)
        if high - low > 0:
            img_array = np.clip((img_array - low) / (high - low) * 255, 0, 255)
        else:
            img_array = np.zeros_like(img_array)

        img_pil = Image.fromarray(img_array.astype(np.uint8))

        # Slight contrast and sharpness enhancement like SDK
        img_pil = ImageEnhance.Contrast(img_pil).enhance(1.3)
        img_pil = ImageEnhance.Sharpness(img_pil).enhance(1.5)

        # Optional: scale up for better preview
        scale = 2
        img_pil = img_pil.resize((width * scale, height * scale), Image.NEAREST)

        # Convert to PNG and Base64 encode
        buffer = io.BytesIO()
        img_pil.save(buffer, format='PNG')
        fingerprint_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

    zkfp2.CloseDevice()
    zkfp2.Terminate()

    return JsonResponse({
        "captured": capture is not None,
        "fingerprint": fingerprint_base64
    })
