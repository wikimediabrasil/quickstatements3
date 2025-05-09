from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from core.models import Batch, BatchCommand


PAGE_SIZE = 25


@require_http_methods(
    [
        "GET",
        "HEAD",
    ]
)
def home(request):
    """
    Main page for this tool
    """
    return render(request, "index.html")


@require_http_methods(
    [
        "GET",
    ]
)
def last_batches(request):
    """
    List last PAGE_SIZE batches modified
    """
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", PAGE_SIZE))
    except (TypeError, ValueError):
        page = 1
        page_size = PAGE_SIZE

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

    queryset = (Batch.objects.all().order_by("-modified")
                .annotate(initial_commands=initial_commands)
                .annotate(running_commands=running_commands)
                .annotate(done_commands=done_commands)
                .annotate(error_commands=error_commands))

    paginator = Paginator(queryset, page_size)

    base_url = reverse("last_batches")
    return render(
        request, "batches.html", {"page": paginator.page(page), "base_url": base_url, "page_size": page_size}
    )


@require_http_methods(
    [
        "GET",
    ]
)
def last_batches_by_user(request, user):
    """
    List last PAGE_SIZE batches modified created by user
    """
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", PAGE_SIZE))
    except (TypeError, ValueError):
        page = 1
        page_size = PAGE_SIZE

    paginator = Paginator(
        Batch.objects.filter(user=user).order_by("-modified"), page_size
    )
    base_url = reverse("last_batches_by_user", args=[user])
    # we need to use `username` since `user` is always supplied by django templates
    return render(
        request,
        "batches.html",
        {"username": user, "page": paginator.page(page), "base_url": base_url, "page_size": page_size},
    )
