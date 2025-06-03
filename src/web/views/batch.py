from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from core.exceptions import ServerError, UnauthorizedToken
from core.models import Batch, BatchCommand, Client, Token
from web.models import Preferences

from .auth import logout_per_token_expired

PAGE_SIZE = 25

import logging

logger = logging.getLogger("qsts3")


@require_http_methods(
    [
        "GET",
    ]
)
def batch(request, pk):
    """
    Base call for a batch. Returns the main page, that will load 2 fragments: commands and summary
    Used for ajax calls
    """
    try:
        batch = Batch.objects.get(pk=pk)
        user_is_authorized = request.user.is_authenticated and (
            request.user.username == batch.user or request.user.is_superuser
        )
        is_autoconfirmed = None
        return render(
            request,
            "batch.html",
            {
                "batch": batch,
                "user_is_authorized": user_is_authorized,
                "is_autoconfirmed": is_autoconfirmed,
            },
        )
    except Batch.DoesNotExist:
        return render(request, "batch_not_found.html", {"pk": pk}, status=404)


@require_http_methods(
    [
        "POST",
    ]
)
def batch_stop(request, pk):
    """
    Base call for a batch. Returns the main page, that will load 2 fragments: commands and summary
    Used for ajax calls
    """
    try:
        batch = Batch.objects.get(pk=pk)
        user_is_authorized = request.user.is_authenticated and (
            request.user.username == batch.user or request.user.is_superuser
        )
        assert user_is_authorized
        batch.stop()
        return redirect(reverse("batch", args=[batch.pk]))
    except Batch.DoesNotExist:
        return render(request, "batch_not_found.html", {"pk": pk}, status=404)
    except AssertionError:
        return HttpResponse("403 Forbidden", status=403)


@require_http_methods(
    [
        "POST",
    ]
)
def batch_restart(request, pk):
    """
    Restart a batch that was previously stopped
    Allows a batch that is in the preview state to start running.
    """
    try:
        batch = Batch.objects.get(pk=pk)
        user_is_authorized = request.user.is_authenticated and (
            request.user.username == batch.user or request.user.is_superuser
        )
        assert user_is_authorized
        batch.restart()
        return redirect(reverse("batch", args=[batch.pk]))
    except Batch.DoesNotExist:
        return render(request, "batch_not_found.html", {"pk": pk}, status=404)
    except AssertionError:
        return HttpResponse("403 Forbidden", status=403)


@require_http_methods(
    [
        "POST",
    ]
)
def batch_rerun(request, pk):
    """
    Rerun a batch that was finished but left command with errors
    """
    try:
        batch = Batch.objects.get(pk=pk)
        user_is_authorized = request.user.is_authenticated and (
            request.user.username == batch.user or request.user.is_superuser
        )
        assert user_is_authorized
        batch.combine_commands = "uncombine_commands" not in request.POST
        batch.rerun()
        return redirect(reverse("batch", args=[batch.pk]))
    except Batch.DoesNotExist:
        return render(request, "batch_not_found.html", {"pk": pk}, status=404)
    except AssertionError:
        return HttpResponse("403 Forbidden", status=403)


@require_GET
def batch_report(request, pk):
    try:
        batch = Batch.objects.get(pk=pk, status=Batch.STATUS_DONE)
        user_is_authorized = request.user.is_authenticated and (
            request.user.username == batch.user or request.user.is_superuser
        )
        assert user_is_authorized
        res = HttpResponse(
            content_type="text/csv",
            headers={
                "Content-Disposition": f'attachment; filename="batch-{pk}-report.csv"'
            },
        )
        batch.write_report(res)
        return res
    except Batch.DoesNotExist:
        return render(request, "batch_not_found.html", {"pk": pk}, status=404)
    except AssertionError:
        return HttpResponse("403 Forbidden", status=403)


@require_http_methods(["GET"])
def batch_commands(request, pk):
    """
    RETURNS fragment page with PAGINATED COMMANDs FOR A GIVEN BATCH ID
    Used for ajax calls
    """
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", PAGE_SIZE))
    except (TypeError, ValueError):
        page = 1
        page_size = PAGE_SIZE

    only_errors = int(request.GET.get("show_errors", 0)) == 1

    batch = get_object_or_404(Batch, pk=pk)

    qs = batch.batchcommand_set.all()
    if only_errors:
        qs = qs.filter(status=BatchCommand.STATUS_ERROR)

    paginator = Paginator(qs.order_by("index"), page_size)
    page = paginator.page(page)
    base_url = reverse("batch_commands", args=[pk])
    return render(
        request,
        "batch_commands.html",
        {
            "page": page,
            "batch_pk": pk,
            "only_errors": only_errors,
            "base_url": base_url,
            "page_size": page_size,
        },
    )


@require_http_methods(
    [
        "GET",
    ]
)
def batch_summary(request, pk):
    """
    Return informations about the current batch. Used as fragment for the main batch page
    CURRENT STATUS
    TOTAL COMMANDS
    ERROR COMMANDS
    DONE COMMANDS
    RUNNING COMMANDS
    INITIAL COMMANDS
    """
    try:
        from django.db.models import Count, Q

        error_commands = Count(
            "batchcommand", filter=Q(batchcommand__status=BatchCommand.STATUS_ERROR)
        )
        initial_commands = Count(
            "batchcommand", filter=Q(batchcommand__status=BatchCommand.STATUS_INITIAL)
        )
        running_commands = Count(
            "batchcommand", filter=Q(batchcommand__status=BatchCommand.STATUS_RUNNING)
        )
        done_commands = Count(
            "batchcommand", filter=Q(batchcommand__status=BatchCommand.STATUS_DONE)
        )
        batch = (
            Batch.objects.annotate(error_commands=error_commands)
            .annotate(initial_commands=initial_commands)
            .annotate(running_commands=running_commands)
            .annotate(done_commands=done_commands)
            .annotate(total_commands=Count("batchcommand"))
            .get(pk=pk)
        )
        show_block_on_errors_notice = (
            batch.is_preview_initial_or_running and batch.block_on_errors
        )
        finished_commands = batch.done_commands + batch.error_commands

        def percentage(val, max):
            return round(float(100 * val / max)) if max else 0

        response = render(
            request,
            "batch_summary.html",
            {
                "pk": batch.pk,
                "batch": batch,
                "status": batch.get_status_display(),
                "error_count": batch.error_commands,
                "initial_count": batch.initial_commands,
                "running_count": batch.running_commands,
                "done_count": batch.done_commands,
                "total_count": batch.total_commands,
                "done_percentage": percentage(
                    batch.done_commands, batch.total_commands
                ),
                "finish_percentage": percentage(
                    finished_commands, batch.total_commands
                ),
                "done_to_finish_percentage": percentage(
                    batch.done_commands, finished_commands
                ),
                "show_block_on_errors_notice": show_block_on_errors_notice,
            },
        )
        if batch.is_done:
            previous_status = request.GET.get("previous_status")
            if previous_status and previous_status != str(batch.STATUS_DONE):
                # Refreshing the page to load the correct buttons
                # and reload the command list if it's the first DONE
                response.headers["HX-Refresh"] = "true"
        return response
    except Batch.DoesNotExist:
        return render(request, "batch_summary.html", {}, status=404)
