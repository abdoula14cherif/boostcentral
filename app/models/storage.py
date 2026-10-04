"""
Upload d'images vers Supabase Storage (bucket "preuves", public).
"""
import logging
import uuid
import requests
from flask import current_app

logger = logging.getLogger(__name__)

BUCKET = "preuves"


def upload_image(file_storage, prefix=""):
    """Upload une image et retourne son URL publique, ou None en cas d'echec."""
    if not file_storage or not file_storage.filename:
        return None
    try:
        ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else "jpg"
        if ext not in ("jpg", "jpeg", "png", "webp"):
            ext = "jpg"
        path = f"{prefix}{uuid.uuid4().hex}.{ext}"

        base_url = current_app.config["SUPABASE_URL"]
        key = current_app.config["SUPABASE_SERVICE_KEY"]
        upload_url = f"{base_url}/storage/v1/object/{BUCKET}/{path}"

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": file_storage.mimetype or "image/jpeg"
        }
        data = file_storage.read()
        r = requests.post(upload_url, headers=headers, data=data, timeout=30)

        if r.status_code not in (200, 201):
            logger.error(f"upload_image echec ({r.status_code}): {r.text}")
            return None

        return f"{base_url}/storage/v1/object/public/{BUCKET}/{path}"
    except Exception as e:
        logger.error(f"upload_image: {e}")
        return None
