from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from core.models import Batch

PAGE_SIZE = 25


@require_http_methods(["GET", "HEAD"])
def home(request):
    """
    Main page for this tool
    """
    return render(request, "index.html")


@require_http_methods(["GET"])
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

    qs = (
        Batch.objects.exclude(status=Batch.STATUS_PREVIEW)
        .with_command_status_counts()
        .order_by("-modified")
    )

    paginator = Paginator(qs, page_size)
    base_url = reverse("last_batches")
    return render(
        request,
        "batches.html",
        {"page": paginator.page(page), "base_url": base_url, "page_size": page_size},
    )


@require_http_methods(["GET"])
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

    batches = (
        Batch.objects.filter(user=user)
        .exclude(status=Batch.STATUS_PREVIEW)
        .with_command_status_counts()
    )
    paginator = Paginator(batches.order_by("-modified"), page_size)
    base_url = reverse("last_batches_by_user", args=[user])
    # we need to use `username` since `user` is always supplied by django templates
    return render(
        request,
        "batches.html",
        {
            "username": user,
            "page": paginator.page(page),
            "base_url": base_url,
            "page_size": page_size,
        },
    )
