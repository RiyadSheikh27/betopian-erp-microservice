import io
import logging
import os
import subprocess
import tempfile

from django.conf import settings
from django.core.files import File
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


def _probe_duration(path):
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            path,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise ValueError("Could not read video duration.")
    return float(result.stdout.strip())


def _with_temp_path(file, suffix=".mp4"):
    path = getattr(file, "temporary_file_path", None)
    if path:
        yield path
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        for chunk in file.chunks():
            tmp.write(chunk)
        path = tmp.name
    try:
        yield path
    finally:
        os.unlink(path)
        if hasattr(file, "seek"):
            file.seek(0)


def validate_video_duration(file, max_seconds=None):
    max_seconds = max_seconds or getattr(settings, "STORY_VIDEO_MAX_DURATION_SECONDS", 60)
    for path in _with_temp_path(file):
        duration = _probe_duration(path)
    if duration > max_seconds:
        raise ValueError(
            f"Video exceeds the {max_seconds}s limit (duration: {duration:.1f}s)."
        )
    return duration


def extract_video_thumbnail(video_path, output_path, at_seconds=1):
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-ss",
            str(at_seconds),
            "-i",
            video_path,
            "-vframes",
            "1",
            "-q:v",
            "2",
            output_path,
        ],
        capture_output=True,
        check=True,
    )

    max_dim = getattr(settings, "IMAGE_MAX_DIMENSION", 1920)
    quality = getattr(settings, "IMAGE_COMPRESSION_QUALITY", 85)
    img = Image.open(output_path)
    if img.width > max_dim or img.height > max_dim:
        img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    if img.mode != "RGB":
        img = img.convert("RGB")
    img.save(output_path, format="JPEG", quality=quality, optimize=True)
    return output_path


def save_thumbnail_from_video_file(story_file_field, thumbnail_field):
    """Extract a frame from a stored video and save to thumbnail_field."""
    suffix = os.path.splitext(story_file_field.name)[1] or ".mp4"
    video_path = None
    thumb_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as video_tmp:
            with story_file_field.open("rb") as src:
                for chunk in iter(lambda: src.read(8192), b""):
                    video_tmp.write(chunk)
            video_path = video_tmp.name

        thumb_path = video_path + ".jpg"
        extract_video_thumbnail(video_path, thumb_path)
        with open(thumb_path, "rb") as thumb:
            thumbnail_field.save(
                f"thumb_{os.path.basename(story_file_field.name)}.jpg",
                File(thumb),
                save=False,
            )
    finally:
        for path in (video_path, thumb_path):
            if path and os.path.exists(path):
                os.unlink(path)
