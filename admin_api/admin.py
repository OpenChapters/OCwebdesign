from django.contrib import admin
from django.utils.html import format_html

from .models import SiteConfig


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ("Splash screen", {
            "fields": (
                "splash_enabled",
                "splash_duration_ms",
                "splash_image",
                "splash_caption",
                "preview_link",
            ),
        }),
    )
    readonly_fields = ("preview_link", "updated_at")

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def preview_link(self, obj):
        if not obj or not obj.pk:
            return "Save once to enable preview."
        return format_html(
            '<a href="/chapters?splash=preview" target="_blank" rel="noopener" '
            'class="button">Open preview in new tab &rarr;</a><br>'
            '<span style="color:#666">Bypasses the session / don\'t-show-again '
            "gates without affecting other users.</span>"
        )
    preview_link.short_description = "Preview"
