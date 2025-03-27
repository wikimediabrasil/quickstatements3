from django.contrib import admin

from core.models import Batch, BatchCommand, Wikibase


@admin.register(Wikibase)
class WikibaseAdmin(admin.ModelAdmin):
    list_display = ("url", "description")


@admin.register(BatchCommand)
class BatchCommandAdmin(admin.ModelAdmin):
    list_select_related = ["batch"]
    list_display = [
        "batch",
        "index",
        "operation",
        "status",
        "error",
        "created",
        "modified",
    ]
    list_filter = ["operation", "status", "error", "created", "modified"]
    search_field = ["batch__name", "batch__user"]
    raw_id_fields = ["batch"]


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "user",
        "status",
        "created",
        "modified",
        "wikibase",
    ]
    search_field = ["name", "user"]
    list_filter = ["status", "created", "modified", "wikibase"]
