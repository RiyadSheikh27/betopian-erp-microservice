import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from apps.utils.response import APIResponse
from .serializers import RegisterSerializer, LoginSerializer, UserProfileSerializer

from drf_spectacular.utils import extend_schema, OpenApiResponse

logger = logging.getLogger("apps.authentication")


def _get_tokens(user):
    refresh = RefreshToken.for_user(user)
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


class RegisterView(APIView):
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: UserProfileSerializer},
        summary="Register a new user",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "Registration failed | errors=%s", serializer.errors
            )
            return APIResponse.error(errors=serializer.errors, message="Registration failed.")

        user = serializer.save()
        logger.info("New user registered | user_id=%s email=%s", user.pk, user.email)
        return APIResponse.success(
            data={
                "user": UserProfileSerializer(user, context={"request": request}).data,
                "tokens": _get_tokens(user),
            },
            message="Registration successful.",
            status_code=201,
        )


class LoginView(APIView):

    @extend_schema(
        request=LoginSerializer,
        responses={200: UserProfileSerializer},
        summary="Login and receive JWT tokens",
        tags=["Authentication"],
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            logger.warning(
                "Login failed | email=%s errors=%s",
                request.data.get("email"), serializer.errors,
            )
            return APIResponse.error(errors=serializer.errors, message="Login failed.")

        user = serializer.validated_data["user"]
        logger.info("User logged in | user_id=%s email=%s", user.pk, user.email)
        return APIResponse.success(
            data={
                "user": UserProfileSerializer(user, context={"request": request}).data,
                "tokens": _get_tokens(user),
            },
            message="Login successful.",
        )


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(summary="Logout and blacklist refresh token", tags=["Authentication"])
    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return APIResponse.error(errors={"refresh": "Refresh token is required."})
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError as e:
            logger.warning(
                "Logout token error | user_id=%s error=%s", request.user.pk, str(e)
            )
            return APIResponse.error(errors={"refresh": str(e)})

        logger.info("User logged out | user_id=%s", request.user.pk)
        return APIResponse.success(message="Logged out successfully.")


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(responses={200: UserProfileSerializer}, summary="Get own profile", tags=["Authentication"])
    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={"request": request})
        return APIResponse.success(data=serializer.data)

    @extend_schema(request=UserProfileSerializer, responses={200: UserProfileSerializer}, summary="Update profile", tags=["Authentication"])
    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user, data=request.data, partial=True, context={"request": request}
        )
        if not serializer.is_valid():
            logger.warning(
                "Profile update failed | user_id=%s errors=%s",
                request.user.pk, serializer.errors,
            )
            return APIResponse.error(errors=serializer.errors)

        serializer.save()
        logger.info("Profile updated | user_id=%s", request.user.pk)
        return APIResponse.success(data=serializer.data, message="Profile updated.")
