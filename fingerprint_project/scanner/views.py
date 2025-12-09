import psycopg2
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
    template_base64 = None

    if capture:
        tmp, img_bytes = capture  # <-- TEMPLATE + IMAGE BYTES
        
        # TEMPLATE (TMP) TO BASE64 (IMPORTANT) 
        template_base64 = base64.b64encode(bytes(tmp)).decode("utf-8")

        # ---- IMAGE PROCESSING ----
        width, height = zkfp2.width, zkfp2.height
        img_pil = Image.frombytes('L', (width, height), img_bytes)

        img_array = np.array(img_pil, dtype=np.float32)
        low, high = np.percentile(img_array, 5), np.percentile(img_array, 95)
        if high - low > 0:
            img_array = np.clip((img_array - low) / (high - low) * 255, 0, 255)
        else:
            img_array = np.zeros_like(img_array)

        img_pil = Image.fromarray(img_array.astype(np.uint8))
        img_pil = ImageEnhance.Contrast(img_pil).enhance(1.3)
        img_pil = ImageEnhance.Sharpness(img_pil).enhance(1.5)

        img_pil = img_pil.resize((width * 2, height * 2), Image.NEAREST)

        buffer = io.BytesIO()
        img_pil.save(buffer, format='PNG')
        fingerprint_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    zkfp2.CloseDevice()
    zkfp2.Terminate()

    return JsonResponse({
        "captured": capture is not None,
        "fingerprint": fingerprint_base64,
        "template": template_base64,
    })


def capture_and_verify(request):
    try:
        # --- Initialize scanner ---
        zkfp2 = ZKFP2()
        zkfp2.Init()

        device_count = zkfp2.GetDeviceCount()
        if device_count == 0:
            zkfp2.Terminate()
            return JsonResponse({"captured": False, "error": "No fingerprint devices found"})

        zkfp2.OpenDevice(0)

        # --- Capture fingerprint ---
        start_time = time.time()
        capture = None

        while True:
            if time.time() - start_time > 15:  # 15 seconds timeout
                break
            result = zkfp2.AcquireFingerprint()
            if result:
                capture = result
                break

        if not capture:
            zkfp2.CloseDevice()
            zkfp2.Terminate()
            return JsonResponse({"captured": False, "error": "No fingerprint captured"})

        captured_tmp, img_bytes = capture

        # Optional: convert image to Base64 for frontend preview
        width, height = zkfp2.width, zkfp2.height
        img_pil = Image.frombytes('L', (width, height), img_bytes)
        img_array = np.array(img_pil, dtype=np.float32)
        low, high = np.percentile(img_array, 5), np.percentile(img_array, 95)
        if high - low > 0:
            img_array = np.clip((img_array - low) / (high - low) * 255, 0, 255)
        else:
            img_array = np.zeros_like(img_array)
        img_pil = Image.fromarray(img_array.astype(np.uint8))
        img_pil = ImageEnhance.Contrast(img_pil).enhance(1.3)
        img_pil = ImageEnhance.Sharpness(img_pil).enhance(1.5)
        img_pil = img_pil.resize((width * 2, height * 2), Image.NEAREST)
        buffer = io.BytesIO()
        img_pil.save(buffer, format='PNG')
        fingerprint_base64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

        # --- Connect to PostgreSQL and fetch templates ---
        conn = psycopg2.connect(
            host="127.0.0.1",
            database="profiling",
            user="postgres",
            password="edward14",
            port=5432
        )
        cursor = conn.cursor()
        cursor.execute("SELECT id, fingerprint_tmp FROM parents")
        rows = cursor.fetchall()
        print(rows)

        # --- Compare captured template with DB templates ---
        matched_parent_id = None
        match_score = 0

        for parent_id, db_template_b64 in rows:
            db_template_bytes = base64.b64decode(db_template_b64)
            score = zkfp2.DBMatch(captured_tmp, db_template_bytes)


            if score > 0:
                matched_parent_id = parent_id
                print(matched_parent_id)
                match_score = score
                break

        zkfp2.CloseDevice()
        zkfp2.Terminate()
        cursor.close()
        conn.close()


        return JsonResponse({
            "captured": True,
            "fingerprint_image": fingerprint_base64,
            "match": matched_parent_id is not None,
            "parent_id": matched_parent_id,
            "score": match_score
        })

    except Exception as e:
        return JsonResponse({"captured": False, "error": str(e)}, status=500)
