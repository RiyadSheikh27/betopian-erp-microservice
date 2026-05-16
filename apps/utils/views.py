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
