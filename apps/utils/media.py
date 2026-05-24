import io
import logging

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image

logger = logging.getLogger("apps.contents")


def validate_file_size(file, media_type):
    """
    Validate uploaded file against per-type size limits from settings.
    Raises ValueError with a user-friendly message if limit exceeded.
    Called in serializer validate_* methods.
    """
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
    """Compress an image file using Pillow."""
    try:
        img = Image.open(uploaded_file)

        # Resize if needed — maintain aspect ratio
        if img.width > max_dimension or img.height > max_dimension:
            img.thumbnail((max_dimension, max_dimension), Image.LANCZOS)

        # Convert to RGB — required for JPEG (handles RGBA, P/palette modes)
        if img.mode in ("RGBA", "P", "LA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "RGBA":
                background.paste(img, mask=img.split()[3])
            else:
                background.paste(img)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        output.seek(0)

        original_size_kb = uploaded_file.size / 1024
        compressed_size_kb = output.getbuffer().nbytes / 1024
        logger.debug(
            "Image compressed | file=%s original=%.1fKB compressed=%.1fKB saved=%.0f%%",
            uploaded_file.name,
            original_size_kb,
            compressed_size_kb,
            (
                (1 - compressed_size_kb / original_size_kb) * 100
                if original_size_kb
                else 0
            ),
        )

        # Build a new file name with .jpg extension
        base_name = uploaded_file.name.rsplit(".", 1)[0]
        new_name = f"{base_name}.jpg"

        return InMemoryUploadedFile(
            file=output,
            field_name=uploaded_file.field_name,
            name=new_name,
            content_type="image/jpeg",
            size=output.getbuffer().nbytes,
            charset=None,
        )

    except Exception as e:
        logger.error(
            "Image compression failed | file=%s error=%s", uploaded_file.name, e
        )
        # Return original file unchanged — never fail the upload because of compression
        return uploaded_file
