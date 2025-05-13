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


def plots_data(request, username):
    all_batches = Batch.objects.exclude(status=Batch.STATUS_PREVIEW)
    all_commands = BatchCommand.objects.exclude(batch__status=Batch.STATUS_PREVIEW)
    if username:
        all_batches = all_batches.filter(user=username)
        all_commands = all_commands.filter(batch__user=username)
    # ----
    today = now().date()
    first_batch = all_batches.order_by("created").first()
    basedate = first_batch.created.date() - timedelta(days=1) if first_batch else today
    delta = (today - basedate).days
    # ---
    created_batches_per_day = {
        q["date"].date(): q["count"]
        for q in all_batches.annotate(date=TruncDay("created"))
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
        for q in all_commands.annotate(date=TruncDay("created"))
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
        "username": username,
        "batches_per_day": batches_per_day,
        "commands_per_day": commands_per_day,
    }
    return data


def all_time_counters_data(request, username):
    all_batches = Batch.objects.exclude(status=Batch.STATUS_PREVIEW)
    all_commands = BatchCommand.objects.exclude(batch__status=Batch.STATUS_PREVIEW)
    if username:
        all_batches = all_batches.filter(user=username)
        all_commands = all_commands.filter(batch__user=username)
    # ----
    batches_count = all_batches.count()
    editors = all_batches.values("user").distinct().count()
    commands_count = all_commands.count()
    average_commands_per_batch = (
        round(commands_count / batches_count) if batches_count > 0 else 0
    )
    # TODO: we can refactor a lot of this into a BatchCommand model manager
    items_created = all_commands.filter(
        operation=BatchCommand.Operation.CREATE_ITEM,
        status=BatchCommand.STATUS_DONE,
    ).count()
    edits = (
        all_commands.filter(status=BatchCommand.STATUS_DONE)
        .exclude(response_id__isnull=True)
        .exclude(response_id="")
        .count()
    )
    data = {
        "username": username,
        "batches_count": batches_count,
        "commands_count": commands_count,
        "average_commands_per_batch": average_commands_per_batch,
        "items_created": items_created,
        "editors": editors,
        "edits": edits,
    }
    return data


def statistics(request):
    return render(request, "statistics.html", {})


def statistics_user(request, username):
    return render(request, "statistics.html", {"username": username})


@cache_page(60)
def plots(request):
    data = plots_data(request, None)
    return render(request, "statistics_plots.html", data)


@cache_page(60)
def plots_user(request):
    data = plots_data(request, None)
    return render(request, "statistics_plots.html", data)


@cache_page(60)
def all_time_counters(request):
    data = all_time_counters_data(request, None)
    return render(request, "statistics_all_time_counters.html", data)


@cache_page(60)
def all_time_counters_user(request, username):
    data = all_time_counters_data(request, username)
    return render(request, "statistics_all_time_counters.html", data)
