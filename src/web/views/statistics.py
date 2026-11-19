from datetime import timedelta
import logging
from urllib.parse import quote

from django.core.cache import cache
from django.shortcuts import render
from django.db.models import Count
from django.db.models import Min
from django.db.models import Q
from django.utils.timezone import now
from django.views.decorators.cache import cache_page
from django.db.models.functions import TruncDay
from django.template import Context
from django.template import Template


from core.models import Batch
from core.models import BatchCommand

logger = logging.getLogger("qsts3")

# Commands created within the last days are always counted live
RECENT_DAYS = 7
OLD_COUNTS_CACHE_TIMEOUT = 60 * 60 * 24 * 2


def dates_after_basedate(basedate, delta):
    return [basedate + timedelta(days=x) for x in range(1, delta + 1)]


def plot_cumulative_batches(all_batches, basedate, delta):
    created_batches_per_day = {
        q["date"].date(): q["count"]
        for q in all_batches.annotate(date=TruncDay("created"))
        .values("date")
        .annotate(count=Count("pk"))
        .order_by("date")
    }
    current_count = 0
    batches_per_day = [0]
    for date in dates_after_basedate(basedate, delta):
        current_count += created_batches_per_day.get(date, 0)
        batches_per_day.append(current_count)
    return batches_per_day


def command_counts_per_day(all_commands):
    """
    Counts commands per day in a single query.

    Returns a dict mapping each date to a dict of counts.
    """
    done = Q(status=BatchCommand.STATUS_DONE)
    edit = done & Q(response_id__isnull=False) & ~Q(response_id="")
    item_created = done & Q(operation=BatchCommand.Operation.CREATE_ITEM)
    return {
        q["date"].date(): {
            "total": q["total"],
            "done": q["done"],
            "error": q["error"],
            "edits": q["edits"],
            "items_created": q["items_created"],
        }
        for q in all_commands.annotate(date=TruncDay("created"))
        .values("date")
        .annotate(
            total=Count("pk"),
            done=Count("pk", filter=done),
            error=Count("pk", filter=Q(status=BatchCommand.STATUS_ERROR)),
            edits=Count("pk", filter=edit),
            items_created=Count("pk", filter=item_created),
        )
        .order_by()
    }


def cached_command_counts_per_day(all_commands, username):
    """
    Same as `command_counts_per_day`, but the counts for commands created before
    `RECENT_DAYS` days ago are cached until the next day, since they rarely change.
    Only the recent days are queried on every call.
    """
    cutoff = now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=RECENT_DAYS)
    user_key = quote(username or "")
    key = f"statistics-command-counts:{user_key}:{cutoff.date().isoformat()}"
    counts = cache.get(key)
    if counts is None:
        counts = command_counts_per_day(all_commands.filter(created__lt=cutoff))
        cache.set(key, counts, timeout=OLD_COUNTS_CACHE_TIMEOUT)
    recent = command_counts_per_day(all_commands.filter(created__gte=cutoff))
    return {**counts, **recent}


def plot_number_of_commands(counts_per_day, basedate, delta):
    done_per_day = [0]
    error_per_day = [0]
    for date in dates_after_basedate(basedate, delta):
        counts = counts_per_day.get(date, {})
        done_per_day.append(counts.get("done", 0))
        error_per_day.append(counts.get("error", 0))
    return {"done": done_per_day, "error": error_per_day}


def plot_cumulative_editors_and_edits(all_batches, counts_per_day, basedate, delta):
    query_users_and_first_batches = (
        all_batches.annotate(date=TruncDay("created"))
        .values("user")
        .annotate(first_batch=Min("date"))
        .order_by("first_batch")
    )
    dates_and_new_users_count = {}
    for q in query_users_and_first_batches:
        # TODO: can we move this to the query? I couldn't do it
        date = q["first_batch"].date()
        dates_and_new_users_count.setdefault(date, 0)
        dates_and_new_users_count[date] += 1
    current_edit_count = 0
    current_editors_count = 0
    editors_per_day = [0]
    edits_per_day = [0]
    for date in dates_after_basedate(basedate, delta):
        current_editors_count += dates_and_new_users_count.get(date, 0)
        current_edit_count += counts_per_day.get(date, {}).get("edits", 0)
        editors_per_day.append(current_editors_count)
        edits_per_day.append(current_edit_count)
    return {"editors": editors_per_day, "edits": edits_per_day}


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
    date_template = Template("{{ date }}")
    all_dates_str = []
    for date in [basedate, *dates_after_basedate(basedate, delta)]:
        context = Context({"date": date})
        rendered_string = date_template.render(context)
        all_dates_str.append(rendered_string)
    # ---
    counts_per_day = cached_command_counts_per_day(all_commands, username)
    batches_per_day = plot_cumulative_batches(all_batches, basedate, delta)
    commands_per_day = plot_number_of_commands(counts_per_day, basedate, delta)
    editors_and_edits_per_day = plot_cumulative_editors_and_edits(
        all_batches,
        counts_per_day,
        basedate,
        delta,
    )
    # ---
    data = {
        "username": username,
        "all_dates_str": all_dates_str,
        "batches_per_day": batches_per_day,
        "commands_per_day": commands_per_day,
        "editors_and_edits_per_day": editors_and_edits_per_day,
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
    counts_per_day = cached_command_counts_per_day(all_commands, username).values()
    commands_count = sum(counts["total"] for counts in counts_per_day)
    items_created = sum(counts["items_created"] for counts in counts_per_day)
    edits = sum(counts["edits"] for counts in counts_per_day)
    average_commands_per_batch = round(commands_count / batches_count) if batches_count > 0 else 0
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


@cache_page(600)
def plots(request):
    data = plots_data(request, None)
    return render(request, "statistics_plots.html", data)


@cache_page(60)
def plots_user(request, username):
    data = plots_data(request, username)
    return render(request, "statistics_plots.html", data)


@cache_page(600)
def all_time_counters(request):
    data = all_time_counters_data(request, None)
    return render(request, "statistics_all_time_counters.html", data)


@cache_page(60)
def all_time_counters_user(request, username):
    data = all_time_counters_data(request, username)
    return render(request, "statistics_all_time_counters.html", data)
