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


def page_number_and_size(request):
    try:
        page_number = int(request.GET.get("page", 1))
        page_size = min(int(request.GET.get("page_size", PAGE_SIZE)), MAX_PAGE_SIZE)
    except (TypeError, ValueError):
        page_number = 1
        page_size = PAGE_SIZE
    return {"page_number": page_number, "page_size": page_size}


@require_http_methods(["GET"])
def last_batches_table(request):
    username = request.GET.get("username")
    page_number, page_size = page_number_and_size(request).values()

    batch_ids = (
        Batch.objects.exclude(status=Batch.STATUS_PREVIEW)
        .order_by("-modified", "-id")
        .values_list("id", flat=True)
    )

    if username:
        batch_ids = batch_ids.filter(user=username)
        base_url = reverse("last_batches_by_user", args=[username])
    else:
        base_url = reverse("last_batches")

    paginator = Paginator(batch_ids, page_size)
    page = paginator.page(page_number)

    ids = list(page.object_list)
    # workaround because `with_command_status_counts`
    # was being run for EVERY batch, oh my god...
    # I thought MariaDB was smarter because it doesn't affect the pagination
    # okay then, this is so that it only runs for the current page batches
    batches = (
        Batch.objects.filter(id__in=ids)
        .select_related("wikibase")
        .order_by("-modified", "-id")
        .with_command_status_counts()
    )

    return render(
        request,
        "batches_table.html",
        {
            "username": username,
            "batches": batches,
            "page": page,
            "base_url": base_url,
            "page_number": page_number,
            "page_size": page_size,
        },
    )


@require_http_methods(["GET"])
def last_batches(request):
    """
    List last PAGE_SIZE batches modified
    """
    return last_batches_by_user(request, "")


@require_http_methods(["GET"])
def last_batches_by_user(request, user):
    """
    List last PAGE_SIZE batches modified created by user
    """
    return render(request, "batches.html", {"username": user, **page_number_and_size(request)})
