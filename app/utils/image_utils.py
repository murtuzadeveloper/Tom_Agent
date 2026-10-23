"""
Image manipulation, base64 encoding, and format conversion utilities.
"""

import io
import base64
from typing import Optional, Tuple
from PIL import Image

def scale_image_for_model(
    image: Image.Image,
    max_dimension: int = 1280,
    jpeg_quality: int = 80
) -> Tuple[Image.Image, str]:
    """
    Downscales image if larger than max_dimension to conserve memory,
    converts to RGB, and returns (scaled_image, base64_jpeg_data_url).
    """
    img = image.convert("RGB")
    width, height = img.size

    # Only scale down if width or height exceeds max_dimension
    if width > max_dimension or height > max_dimension:
        if width >= height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))
        img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Encode to base64 JPEG
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=jpeg_quality, optimize=True)
    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    data_url = f"data:image/jpeg;base64,{b64_data}"
    return img, data_url

def pil_to_qimage(pil_image: Image.Image):
    """Converts a PIL Image to PySide6 QImage without writing to disk."""
    from PySide6.QtGui import QImage
    img_rgb = pil_image.convert("RGBA")
    data = img_rgb.tobytes("raw", "RGBA")
    qimg = QImage(data, img_rgb.width, img_rgb.height, QImage.Format.Format_RGBA8888)
    # Important: keep reference to data to avoid GC segfault
    return qimg.copy()

def pil_to_qpixmap(pil_image: Image.Image):
    """Converts a PIL Image to PySide6 QPixmap."""
    from PySide6.QtGui import QPixmap
    qimage = pil_to_qimage(pil_image)
    return QPixmap.fromImage(qimage)

def get_image_thumbnail_bytes(image: Image.Image, size: Tuple[int, int] = (64, 64)) -> bytes:
    """Creates a small grayscale thumbnail bytearray for perceptual change detection."""
    thumb = image.convert("L").resize(size, Image.Resampling.BILINEAR)
    return thumb.tobytes()
