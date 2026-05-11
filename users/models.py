from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        email = self.normalize_email(email)
        extra_fields.setdefault("username", email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Custom user model using email as the login identifier.
    Email is required and unique; it is used for PDF delivery notifications.
    Username is retained for the admin but is not the login field.
    """

    username = models.CharField(max_length=150, blank=True)
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=300, blank=True)

    # Opt-in: when True, this user's completed books appear in the public
    # Community library. Off by default — book/part titles are user-defined
    # and may carry personal info, so visibility is the user's choice.
    share_builds = models.BooleanField(default=False)

    # Scheduled-deletion grace period. Setting this to a future datetime
    # marks the account for purge by a Celery beat task once it elapses.
    # Cleared (set back to NULL) by the user's "Cancel deletion" action
    # to call off a pending removal.
    deletion_scheduled_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email
