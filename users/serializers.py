import logging

import httpx
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

logger = logging.getLogger(__name__)

User = get_user_model()

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    turnstile_token = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["email", "full_name", "password", "turnstile_token"]

    def validate_turnstile_token(self, value):
        secret = getattr(settings, "TURNSTILE_SECRET_KEY", "")
        if not secret:
            return value  # skip verification if not configured

        try:
            resp = httpx.post(
                TURNSTILE_VERIFY_URL,
                data={"secret": secret, "response": value},
                timeout=10,
            )
            result = resp.json()
        except httpx.TimeoutException:
            logger.warning("Turnstile verification timed out — allowing registration")
            return value  # graceful degradation: don't block users if Cloudflare is slow
        except httpx.RequestError as exc:
            logger.error("Turnstile service error: %s", exc)
            return value  # graceful degradation: don't block users if Cloudflare is down
        except Exception:
            raise serializers.ValidationError("Could not verify CAPTCHA. Please try again.")

        if not result.get("success"):
            raise serializers.ValidationError("CAPTCHA verification failed. Please try again.")

        return value

    def create(self, validated_data):
        validated_data.pop("turnstile_token", None)
        return User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data.get("full_name", ""),
        )
