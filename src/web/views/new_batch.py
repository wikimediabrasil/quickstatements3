from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.core import serializers
from django.core.paginator import Paginator
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.translation import gettext as _
from django.views.decorators.http import require_http_methods

from core.exceptions import ServerError, UnauthorizedToken
from core.models import BatchCommand, Client, Token, Wikibase, get_default_wikibase
from core.parsers.base import ParserException
from core.parsers.csv import CSVCommandParser
from core.parsers.v1 import V1CommandParser
from web.models import Preferences

from .auth import logout_per_token_expired

PAGE_SIZE = 25


@require_http_methods(["GET"])
def preview_batch(request):
    """
    Base call for a batch. Returns the main page, that will load 2 fragments: commands and summary
    Used for ajax calls
    """

    preview_batch = request.session.get("preview_batch")
    if preview_batch:
        total_count = 0
        initial_count = 0
        error_count = 0
        batch = list(serializers.deserialize("json", preview_batch))[0].object
        preview_batch_commands = request.session.get("preview_commands", "[]")
        batch_commands = list(serializers.deserialize("json", preview_batch_commands))
        for bc in batch_commands:
            total_count += 1
            if bc.object.status == BatchCommand.STATUS_ERROR:
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
    preview_batch_commands = request.session.get("preview_commands")
    if preview_batch_commands:
        batch_commands = list(serializers.deserialize("json", preview_batch_commands))

        try:
            batch_json = request.session.get("preview_batch")
            deserialized_batch = list(serializers.deserialize("json", batch_json))[0]

            batch = deserialized_batch.object
            token = Token.objects.get(user=request.user)
        except (IndexError, Token.DoesNotExist):
            token = None

        try:
            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", PAGE_SIZE))
        except (TypeError, ValueError):
            page = 1
            page_size = PAGE_SIZE

        only_errors = int(request.GET.get("show_errors", 0)) == 1
        if only_errors:
            batch_commands = [
                bc
                for bc in batch_commands
                if bc.object.status == BatchCommand.STATUS_ERROR
            ]

        for command in batch_commands:
            command.batch = batch

        paginator = Paginator(batch_commands, page_size)
        page = paginator.page(page)
        page.object_list = [d.object for d in page.object_list]

        if request.user.is_authenticated and token is not None:
            client = Client(token=token, wikibase=batch.wikibase)
            language = Preferences.objects.get_language(request.user, "en")
            BatchCommand.load_labels(client, page.object_list, language)

    base_url = reverse("preview_batch_commands")
    return render(
        request,
        "batch_commands.html",
        {"page": page, "only_errors": only_errors, "base_url": base_url, "page_size": page_size,},
    )


@login_required()
def new_batch(request):
    """
    Creates a new batch
    """

    if request.method == "POST":
        try:
            batch_owner = request.user.username
            batch_commands = request.POST.get("commands")
            batch_name = request.POST.get(
                "name", f"Batch  user:{batch_owner} {datetime.now().isoformat()}"
            )
            batch_type = request.POST.get("type", "v1")
            request.session["preferred_batch_type"] = batch_type

            batch_commands = batch_commands.strip()
            if not batch_commands:
                raise ParserException("Command string cannot be empty")

            batch_name = batch_name.strip()

            if batch_type == "v1":
                parser = V1CommandParser()
            else:
                parser = CSVCommandParser()

            batch = parser.parse(batch_name, batch_owner, batch_commands)

            wikibase_url = request.POST.get("wikibase")
            wikibase = Wikibase.objects.filter(url=wikibase_url).first()
            batch.wikibase = wikibase or get_default_wikibase()

            batch.status = batch.STATUS_PREVIEW
            batch.block_on_errors = "block_on_errors" in request.POST
            batch.combine_commands = "do_not_combine_commands" not in request.POST

            serialized_batch = serializers.serialize("json", [batch])
            serialized_commands = serializers.serialize(
                "json", batch.get_preview_commands()
            )

            request.session["preview_batch"] = serialized_batch
            request.session["preview_commands"] = serialized_commands

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
        preferred_batch_type = request.session.get("preferred_batch_type", "v1")

        try:
            token = Token.objects.get(user=request.user)
            wikibase = get_default_wikibase()
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
                "batch_type": preferred_batch_type,
                "is_autoconfirmed": is_autoconfirmed,
                "is_blocked": is_blocked,
                "wikibases": Wikibase.objects.all(),
            },
        )


@require_http_methods(["POST"])
def batch_allow_start(request):
    """
    Saves and allow a batch that is in the preview state to start running.
    """

    preview_batch = request.session.get("preview_batch")
    if not preview_batch:
        return render(request, "batch_not_found.html", status=404)

    wikibase = get_default_wikibase()
    batch = list(serializers.deserialize("json", preview_batch))[0].object

    try:

        token = Token.objects.get(user=request.user)
        client = Client(token=token, wikibase=wikibase)
        is_autoconfirmed = client.get_is_autoconfirmed()
        is_blocked = client.get_is_blocked()
    except UnauthorizedToken:
        return logout_per_token_expired(request)
    except (Token.DoesNotExist, ServerError):
        is_autoconfirmed = False
        is_blocked = False

    can_start = is_autoconfirmed and not is_blocked
    if not can_start:
        not_confirmed = _(
            "User is not autoconfirmed. Only autoconfirmed users can run batches."
        )
        blocked = _("User is blocked and can not run batches.")

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

    preview_batch_commands = request.session.get("preview_commands", "[]")
    for batch_command in serializers.deserialize("json", preview_batch_commands):
        batch.add_preview_command(batch_command.object)

    batch.wikibase = wikibase
    batch.save_batch_and_preview_commands()

    del request.session["preview_batch"]
    del request.session["preview_commands"]

    return redirect(reverse("batch", args=[batch.pk]))
