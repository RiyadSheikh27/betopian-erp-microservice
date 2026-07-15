import uuid
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)
from django.db import models

""" Custom user model for central ERP users. Read-only mirror of central auth data. """

class UserManager(BaseUserManager):
    def create_superuser(self, email, password=None, **extra_fields):
        """
        Creates a local admin user for Django admin panel access only.
        Not related to central auth - admin panel use only.
        """
        username = email.split("@")[0]
        user = self.model(
            email=email,
            username=username,
            employee_id=f"ADMIN_{username}",
            name=username,
            is_active=True,
            is_staff=True,
            is_superuser=True,
            **extra_fields,
        )
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """
    Read-only mirror of the central ERP user.
    Central auth users always have password=None.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    central_id = models.BigIntegerField(unique=True, blank=True, null=True)
    employee_id = models.CharField(max_length=100, unique=True, db_index=True)
    email = models.EmailField(unique=True)
    username = models.CharField(
        max_length=100, unique=True
    )  # derived from email before @
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=150, blank=True)
    position = models.CharField(max_length=150, blank=True)
    location = models.CharField(max_length=150, blank=True)
    company = models.CharField(max_length=150, blank=True)
    avatar_url = models.URLField(max_length=10000, blank=True, null=True)
    
    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(blank=True, null=True)

    # Only set for Django admin superusers, never for central auth users
    password = models.CharField(max_length=128, blank=True, null=True)

    # Stored for use by other ERP services within the same app
    central_access_token = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.username} ({self.employee_id})"
