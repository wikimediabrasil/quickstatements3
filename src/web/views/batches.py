from typing import Optional

from django.core.paginator import Paginator
from django.shortcuts import render
from django.views.decorators.http import require_http_methods
from django.urls import reverse

from core.models import Batch

PAGE_SIZE = 25
MAX_PAGE_SIZE = 500


@require_http_methods(["GET", "HEAD"])
def home(request):
    """
    Main page for this tool
    """
    return render(request, "index.html")


def _last_batches(request, user: Optional[str]):
    try:
        page = int(request.GET.get("page", 1))
        page_size = min(int(request.GET.get("page_size", PAGE_SIZE)), MAX_PAGE_SIZE)
    except (TypeError, ValueError):
        page = 1
        page_size = PAGE_SIZE

    batches = Batch.objects.all()

    if user:
        batches = batches.filter(user=user)
        base_url = reverse("last_batches_by_user", args=[user])
    else:
        base_url = reverse("last_batches")

    batches = (
        batches.exclude(status=Batch.STATUS_PREVIEW)
        .with_command_status_counts()
        .select_related("wikibase")
        .order_by("-modified")
    )
    paginator = Paginator(batches, page_size)

    return render(
        request,
        "batches.html",
        {
            # we need to use `username` since `user` is always supplied by django templates
            "username": user,
            "page": paginator.page(page),
            "base_url": base_url,
            "page_size": page_size,
        },
    )


@require_http_methods(["GET"])
def last_batches(request):
    """
    List last PAGE_SIZE batches modified
    """
    return _last_batches(request, None)


@require_http_methods(["GET"])
def last_batches_by_user(request, user):
    """
    List last PAGE_SIZE batches modified created by user
    """
    return _last_batches(request, user)
