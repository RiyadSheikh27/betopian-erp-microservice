import logging
from .models import ProfileImageStore
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from .serializers import ProfileImageStoreSerializer
from .response import APIResponse

logger = logging.getLogger("apps.utils")

""" Views for Utils Section """


class ProfileImageUploadView(APIView):
    """View for handling profile image uploads."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProfileImageStoreSerializer(data=request.data)

        if serializer.is_valid():
            profile_image = serializer.validated_data["profile_avatar"]

            profile_image, created = ProfileImageStore.objects.update_or_create(
                user=request.user,
                defaults={"profile_avatar": profile_image},
            )
            response_serializer = ProfileImageStoreSerializer(
                profile_image, context={"request": request}
            )

            logger.info(
                f"Profile image uploaded successfully for user: {request.user.id}"
            )

            return APIResponse.success(
                data=response_serializer.data,
                message="Profile image uploaded successfully.",
            )

        logger.error(f"Invalid data provided for user: {request.user.id}")

        return APIResponse.error(
            errors=serializer.errors,
            message="Invalid data.",
            status_code=400,
        )


""" Dynamic Media Handling Seciton """

from django.conf import settings as django_settings
from django.db.utils import OperationalError, ProgrammingError
from .models import MediaHandling


def load_media_handling():
    try:
        config = MediaHandling.objects.first()
    except (OperationalError, ProgrammingError):
        return  # DB not ready yet

    if not config:
        return

    django_settings.IMAGE_UPLOAD_MAX_SIZE_MB = config.image_upload_max_size_mb
    django_settings.VIDEO_UPLOAD_MAX_SIZE_MB = config.video_upload_max_size_mb
    django_settings.IMAGE_COMPRESSION_QUALITY = config.image_compression_quality
    django_settings.IMAGE_MAX_DIMENSION = config.image_max_dimension
    django_settings.AVATAR_MAX_DIMENSION = config.avatar_max_dimension
