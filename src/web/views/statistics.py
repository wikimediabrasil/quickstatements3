from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import logging

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


def plot_number_of_commands(all_commands, basedate, delta):
    query_commands_per_day = {
        q["date"].date(): (q["done_count"], q["error_count"])
        for q in all_commands.annotate(date=TruncDay("created"))
        .values("date")
        .annotate(done_count=Count("pk", filter=Q(status=BatchCommand.STATUS_DONE)))
        .annotate(error_count=Count("pk", filter=Q(status=BatchCommand.STATUS_ERROR)))
        .order_by("date")
    }
    done_per_day = [0]
    error_per_day = [0]
    for date in dates_after_basedate(basedate, delta):
        done, error = query_commands_per_day.get(date, (0, 0))
        done_per_day.append(done)
        error_per_day.append(error)
    return {"done": done_per_day, "error": error_per_day}


def plot_cumulative_editors_and_edits(all_batches, all_commands, basedate, delta):
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
    query_edits_per_day = {
        q["date"].date(): q["count"]
        for q in all_commands.filter(status=BatchCommand.STATUS_DONE)
        .exclude(response_id__isnull=True)
        .exclude(response_id="")
        .annotate(date=TruncDay("created"))
        .values("date")
        .annotate(count=Count("pk"))
        .order_by("date")
    }
    current_edit_count = 0
    current_editors_count = 0
    editors_per_day = [0]
    edits_per_day = [0]
    for date in dates_after_basedate(basedate, delta):
        current_editors_count += dates_and_new_users_count.get(date, 0)
        current_edit_count += query_edits_per_day.get(date, 0)
        editors_per_day.append(current_editors_count)
        edits_per_day.append(current_edit_count)
    return {"editors": editors_per_day, "edits": edits_per_day}


def count_items_created(all_commands):
    # TODO: we can refactor a lot of this into a BatchCommand model manager
    return all_commands.filter(
        operation=BatchCommand.Operation.CREATE_ITEM,
        status=BatchCommand.STATUS_DONE,
    ).count()


def count_edits(all_commands):
    return (
        all_commands.filter(status=BatchCommand.STATUS_DONE)
        .exclude(response_id__isnull=True)
        .exclude(response_id="")
        .count()
    )


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
    with ThreadPoolExecutor() as executor:
        t1 = executor.submit(plot_cumulative_batches, all_batches, basedate, delta)
        t2 = executor.submit(plot_number_of_commands, all_commands, basedate, delta)
        t3 = executor.submit(
            plot_cumulative_editors_and_edits,
            all_batches,
            all_commands,
            basedate,
            delta,
        )
        batches_per_day = t1.result()
        commands_per_day = t2.result()
        editors_and_edits_per_day = t3.result()
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
    commands_count = all_commands.count()
    average_commands_per_batch = round(commands_count / batches_count) if batches_count > 0 else 0
    # only these ones multi-threaded because they are the slowest
    # the above ones are quite fast
    with ThreadPoolExecutor() as executor:
        t1 = executor.submit(count_items_created, all_commands)
        t2 = executor.submit(count_edits, all_commands)
        items_created = t1.result()
        edits = t2.result()
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
def plots_user(request, username):
    data = plots_data(request, username)
    return render(request, "statistics_plots.html", data)


@cache_page(60)
def all_time_counters(request):
    data = all_time_counters_data(request, None)
    return render(request, "statistics_all_time_counters.html", data)


@cache_page(60)
def all_time_counters_user(request, username):
    data = all_time_counters_data(request, username)
    return render(request, "statistics_all_time_counters.html", data)
