from django.contrib import admin

from .models import Preferences


@admin.register(Preferences)
class PreferencesAdmin(admin.ModelAdmin):
    list_display = ["user", "language"]
    list_filter = ["language"]
    search_field = ["user"]
    raw_id_fields = ["user"]
