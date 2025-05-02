from datetime import timedelta
import logging

from django.shortcuts import render
from django.db.models import Count
from django.db.models import Q
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.db.models.functions import TruncDay


from core.models import Batch
from core.models import BatchCommand

logger = logging.getLogger("qsts3")


@cache_page(60)
def statistics(request):
    # ----
    today = now().date()
    first_batch = Batch.objects.order_by("created").first()
    basedate = first_batch.created.date() - timedelta(days=1) if first_batch else today
    delta = (today - basedate).days
    # ---
    created_batches_per_day = {
        q["date"].date(): q["count"]
        for q in Batch.objects.all()
        .annotate(date=TruncDay("created"))
        .values("date")
        .annotate(count=Count("pk"))
        .order_by("date")
    }
    current_count = 0
    batches_per_day = {basedate: 0}
    for date in [basedate + timedelta(days=x) for x in range(1, delta + 1)]:
        current_count += created_batches_per_day.get(date, 0)
        batches_per_day[date] = current_count
    # ---
    query_commands_per_day = {
        q["date"].date(): (q["done_count"], q["error_count"])
        for q in BatchCommand.objects.all()
        .annotate(date=TruncDay("created"))
        .values("date")
        .annotate(done_count=Count("pk", filter=Q(status=BatchCommand.STATUS_DONE)))
        .annotate(error_count=Count("pk", filter=Q(status=BatchCommand.STATUS_ERROR)))
        .order_by("date")
    }
    commands_per_day = {basedate: (0, 0)}
    for date in [basedate + timedelta(days=x) for x in range(1, delta + 1)]:
        commands_per_day[date] = query_commands_per_day.get(date, (0, 0))
    # ---
    data = {
        "batches_per_day": batches_per_day,
        "commands_per_day": commands_per_day,
    }
    return render(request, "statistics.html", data)


@cache_page(60)
def all_time_counters(request):
    batches_count = Batch.objects.all().count()
    editors = Batch.objects.values("user").distinct().count()
    commands_count = BatchCommand.objects.all().count()
    average_commands_per_batch = (
        round(commands_count / batches_count) if batches_count > 0 else 0
    )
    # TODO: we can refactor a lot of this into a BatchCommand model manager
    items_created = BatchCommand.objects.filter(
        operation=BatchCommand.Operation.CREATE_ITEM,
        status=BatchCommand.STATUS_DONE,
    ).count()
    edits = (
        BatchCommand.objects.filter(status=BatchCommand.STATUS_DONE)
        .exclude(response_id__isnull=True)
        .exclude(response_id="")
        .count()
    )
    data = {
        "batches_count": batches_count,
        "commands_count": commands_count,
        "average_commands_per_batch": average_commands_per_batch,
        "items_created": items_created,
        "editors": editors,
        "edits": edits,
    }
    return render(request, "statistics_all_time_counters.html", data)
