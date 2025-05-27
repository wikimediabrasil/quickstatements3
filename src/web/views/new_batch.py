from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import pgettext_lazy
from django.views.decorators.http import require_http_methods

from core.exceptions import ServerError, UnauthorizedToken
from core.models import (
    Batch,
    BatchCommand,
    BatchEditingSession,
    Client,
    Token,
    Wikibase,
    get_default_wikibase,
)
from core.parsers.base import ParserException
from core.parsers.csv import CSVCommandParser
from core.parsers.v1 import V1CommandParser

from .auth import logout_per_token_expired

PAGE_SIZE = 25


@require_http_methods(["GET"])
def preview_batch(request):
    """
    Base call for a batch. Returns the main page, that will load 2 fragments: commands and summary
    Used for ajax calls
    """

    batch = (
        Batch.objects.filter(
            editing_session__session_key=request.session.session_key,
            status=Batch.STATUS_PREVIEW,
        )
        .order_by("-created")
        .first()
    )
    if batch:
        total_count = 0
        initial_count = 0
        error_count = 0
        for bc in batch.batchcommand_set.all():
            total_count += 1
            if bc.status == BatchCommand.STATUS_ERROR:
                error_count += 1
            else:
                initial_count += 1

        is_autoconfirmed = None

        try:
            token = Token.objects.get(user=request.user)
            client = Client(token=token, wikibase=batch.wikibase)
            is_autoconfirmed = client.get_is_autoconfirmed()
            is_blocked = client.get_is_blocked()
        except UnauthorizedToken:
            return logout_per_token_expired(request)
        except (Token.DoesNotExist, ServerError):
            is_autoconfirmed = False
            is_blocked = False

        return render(
            request,
            "preview_batch.html",
            {
                "batch": batch,
                "current_owner": True,
                "is_autoconfirmed": is_autoconfirmed,
                "is_blocked": is_blocked,
                "total_count": total_count,
                "initial_count": initial_count,
                "error_count": error_count,
            },
        )
    else:
        return redirect(reverse("new_batch"))


@require_http_methods(["GET"])
def preview_batch_commands(request):
    """
    RETURNS fragment page with PAGINATED COMMANDs FOR A GIVEN BATCH ID
    Used for ajax calls
    """

    batch = (
        Batch.objects.filter(
            editing_session__session_key=request.session.session_key,
            status=Batch.STATUS_PREVIEW,
        )
        .order_by("-created")
        .first()
    )
    if batch:
        batch_commands = batch.batchcommand_set.all()
        try:
            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", PAGE_SIZE))
        except (TypeError, ValueError):
            page = 1
            page_size = PAGE_SIZE

        only_errors = int(request.GET.get("show_errors", 0)) == 1
        if only_errors:
            batch_commands = [
                bc for bc in batch_commands if bc.status == BatchCommand.STATUS_ERROR
            ]

        paginator = Paginator(batch_commands, page_size)
        page = paginator.page(page)

    base_url = reverse("preview_batch_commands")
    return render(
        request,
        "batch_commands.html",
        {
            "page": page,
            "only_errors": only_errors,
            "base_url": base_url,
            "page_size": page_size,
        },
    )


@login_required()
def new_batch(request):
    """
    Creates a new batch
    """

    if request.method == "POST":
        try:
            BatchEditingSession.objects.filter(session_key=request.session.session_key).delete()
            Batch.objects.filter(status=Batch.STATUS_PREVIEW, user=request.user.username).delete()
            batch_type = request.POST.get("type", "v1")
            batch_commands = request.POST.get("commands")

            uploaded_file = request.FILES.get("file")
            if uploaded_file:
                batch_commands = uploaded_file.read().decode("utf-8")

            batch_name = request.POST.get(
                "name",
                f"Batch user:{request.user.username} {datetime.now().isoformat()}",
            ).strip()

            batch_commands = batch_commands.strip()
            if not batch_commands:
                raise ParserException(pgettext_lazy(
                    "batch-py-empty-command-input",
                    "Command input cannot be empty. Please provide valid commands."
                ))

            if batch_type == "v1":
                parser = V1CommandParser()
            else:
                if "\n" not in batch_commands:
                    raise ParserException(pgettext_lazy(
                        "batch-py-csv-only-header",
                        "CSV input must include more than just the header row"
                    ))
                parser = CSVCommandParser()

            wikibase_url = request.POST.get("wikibase")
            wikibase = wikibase_url and Wikibase.objects.filter(url=wikibase_url).first()

            batch = Batch.objects.create(
                name=batch_name,
                user=request.user.username,
                wikibase=wikibase or get_default_wikibase(),
                status=Batch.STATUS_PREVIEW,
                block_on_errors="block_on_errors" in request.POST,
                combine_commands="do_not_combine_commands" not in request.POST,
            )

            for batch_command in parser.parse(batch_commands):
                batch_command.batch = batch
                batch_command.save()

            if not batch.batchcommand_set.exists():
                raise ParserException(pgettext_lazy(
                    "batch-py-valid-command-not-found",
                    "No valid commands found in the provided input."
                ))

            request.session["preferred_batch_type"] = batch_type
            # Set up editing session for the newly created batch.
            BatchEditingSession.objects.create(
                batch=batch, session_key=request.session.session_key
            )

            return redirect(reverse("preview_batch"))
        except ParserException as p:
            error = p.message
        except Exception as p:
            error = str(p)
        return render(
            request,
            "new_batch.html",
            {
                "error": error,
                "name": batch_name,
                "batch_type": batch_type,
                "commands": batch_commands,
                "wikibases": Wikibase.objects.all(),
            },
        )

    else:
        batch = Batch.objects.filter(
            editing_session__session_key=request.session.session_key,
            status=Batch.STATUS_PREVIEW,
        ).first()
        try:
            token = Token.objects.get(user=request.user)
            wikibase = batch and batch.wikibase or get_default_wikibase()
            client = Client(token=token, wikibase=wikibase)
            is_autoconfirmed = client.get_is_autoconfirmed()
            is_blocked = client.get_is_blocked()
        except (Token.DoesNotExist, ServerError):
            is_autoconfirmed = False
            is_blocked = False
        except UnauthorizedToken:
            return logout_per_token_expired(request)

        return render(
            request,
            "new_batch.html",
            {
                "batch_type": request.session.get("preferred_batch_type", "v1"),
                "is_autoconfirmed": is_autoconfirmed,
                "is_blocked": is_blocked,
                "wikibases": Wikibase.objects.all(),
                "commands": request.GET.get("v1"),
            },
        )


@require_http_methods(["POST"])
@login_required()
def batch_allow_start(request):
    batch = Batch.objects.filter(
        editing_session__session_key=request.session.session_key,
        status=Batch.STATUS_PREVIEW,
    ).first()
    if not batch:
        return render(request, "batch_not_found.html", status=404)

    try:
        token = Token.objects.get(user=request.user)
        client = Client(token=token, wikibase=batch.wikibase)
        is_autoconfirmed = client.get_is_autoconfirmed()
        is_blocked = client.get_is_blocked()
    except UnauthorizedToken:
        return logout_per_token_expired(request)
    except (Token.DoesNotExist, ServerError):
        is_autoconfirmed = False
        is_blocked = False

    can_start = is_autoconfirmed and not is_blocked
    if not can_start:
        not_confirmed = pgettext_lazy(
            "batch-py-user-not-autoconfirmed",
            "User is not autoconfirmed. Only autoconfirmed users can run batches."
        )
        blocked = pgettext_lazy(
            "batch-py-user-blocked", "User is blocked and can not run batches."
        )

        error_message = not_confirmed if not is_autoconfirmed else blocked

        return render(
            request,
            "new_batch.html",
            {
                "is_autoconfirmed": is_autoconfirmed,
                "is_blocked": is_blocked,
                "error": error_message,
                "wikibases": Wikibase.objects.all(),
            },
        )

    batch.status = Batch.STATUS_INITIAL
    batch.save()
    return redirect(reverse("batch", args=[batch.pk]))
