import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.utils.response import APIResponse
from .serializers import UserProfileSerializer

logger = logging.getLogger("apps.authentication")


class ProfileView(APIView):
    """
    Returns the authenticated user's profile.
    Data is always fresh - synced from central ERP on every request
    via CentralTokenAuthentication before this view is even reached.
    Read-only. Central ERP owns all user data.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserProfileSerializer(request.user)
        return APIResponse.success(data=serializer.data)


class LogoutView(APIView):
    """
    We don't issue or store session tokens - central ERP does.
    Flutter discards the central token locally on logout.
    This endpoint exists as a clean hook for any logout-time
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        logger.info("User logged out | user_id=%s email=%s", request.user.pk, request.user.email)
        return APIResponse.success(message="Logged out successfully.")
