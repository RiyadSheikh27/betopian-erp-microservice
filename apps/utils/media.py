import io
import logging
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image

logger = logging.getLogger("apps.utils")


def validate_file_size(file, media_type):
    """Validate uploaded file against per-type size limits from settings."""
    if media_type == "image":
        limit = settings.IMAGE_UPLOAD_MAX_SIZE
        limit_mb = settings.IMAGE_UPLOAD_MAX_SIZE_MB
        label = "Image"
    else:
        limit = settings.VIDEO_UPLOAD_MAX_SIZE
        limit_mb = settings.VIDEO_UPLOAD_MAX_SIZE_MB
        label = "Video"

    if file.size > limit:
        raise ValueError(
            f"{label} '{file.name}' exceeds the {limit_mb}MB limit "
            f"(uploaded: {file.size / 1024 / 1024:.1f}MB)."
        )


def compress_image(uploaded_file, max_dimension=None, quality=None):
    """
    Compress and resize an image using Pillow.
    Falls back to settings values when max_dimension/quality not provided.
    Never fails the upload - returns original file on error.
    """
    max_dimension = max_dimension or getattr(settings, "IMAGE_MAX_DIMENSION", 1920)
    quality = quality or getattr(settings, "IMAGE_COMPRESSION_QUALITY", 85)

    try:
        img = Image.open(uploaded_file)

        if img.width > max_dimension or img.height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)

        logger.debug(
            "Image compressed | file=%s original=%.1fKB compressed=%.1fKB",
            uploaded_file.name,
            uploaded_file.size / 1024,
            output.getbuffer().nbytes / 1024,
        )

        return InMemoryUploadedFile(
            file=output,
            field_name=uploaded_file.field_name,
            name=f"{uploaded_file.name.rsplit('.', 1)[0]}.jpg",
            content_type="image/jpeg",
            size=output.getbuffer().nbytes,
            charset=None,
        )

    except Exception as e:
        logger.error(
            "Image compression failed | file=%s error=%s", uploaded_file.name, e
        )
        return uploaded_file
