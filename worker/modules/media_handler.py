"""
Image/media handler.

Ollama vision models require images as Base64 strings, not URLs.
This module downloads any image URL and converts it to Base64
so the executor can attach it to the Ollama payload.
"""
import base64
import logging
import os
import tempfile

import requests

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT = 30   # seconds per image download
MAX_IMAGE_SIZE   = 20 * 1024 * 1024   # 20 MB hard limit


def download_and_encode(image_url: str) -> str | None:
    """
    Download an image from a URL and return it as a Base64 string.
    Returns None on any error (caller skips the image and logs a warning).
    """
    logger.debug("Downloading image: %s", image_url)
    try:
        resp = requests.get(image_url, timeout=DOWNLOAD_TIMEOUT, stream=True)
        resp.raise_for_status()

        # Sanity-check content type
        content_type = resp.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            logger.warning("URL does not look like an image (%s): %s", content_type, image_url)

        # Write to a temp file (avoids loading entire file into RAM)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".img") as tmp:
            downloaded = 0
            for chunk in resp.iter_content(chunk_size=8192):
                downloaded += len(chunk)
                if downloaded > MAX_IMAGE_SIZE:
                    logger.error("Image too large (>20 MB), skipping: %s", image_url)
                    os.unlink(tmp.name)
                    return None
                tmp.write(chunk)
            tmp_path = tmp.name

        # Encode to Base64
        with open(tmp_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")

        os.unlink(tmp_path)
        logger.debug("Image encoded (%d chars) from: %s", len(encoded), image_url)
        return encoded

    except requests.exceptions.RequestException as exc:
        logger.error("Failed to download image '%s': %s", image_url, exc)
        return None
    except Exception as exc:
        logger.error("Unexpected error processing image '%s': %s", image_url, exc)
        return None


def process_images(image_urls: list) -> list:
    """
    Process a list of image URLs → list of Base64 strings.
    URLs that fail are skipped with a warning (job still processes without them).
    """
    if not image_urls:
        return []
    result = []
    for url in image_urls:
        encoded = download_and_encode(url)
        if encoded:
            result.append(encoded)
        else:
            logger.warning("Skipping failed image: %s", url)
    return result
