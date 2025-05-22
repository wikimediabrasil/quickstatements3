from django.shortcuts import render
from django.utils import translation
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from rest_framework.authtoken.models import Token as AuthToken

from core.exceptions import ServerError, UnauthorizedToken
from core.models import Client, Token, get_default_wikibase
from web.languages import LANGUAGE_CHOICES
from web.languages import LANGUAGE_CODE_LIST
from web.models import Preferences

from .auth import logout_per_token_expired


def profile(request):
    data = {}
    if request.user.is_authenticated:
        user = request.user

        # Wikimedia API
        is_autoconfirmed = False
        token_failed = False
        try:
            wikibase = get_default_wikibase()
            token = Token.objects.get(user=request.user)
            client = Client(token=token, wikibase=wikibase)
            is_autoconfirmed = client.get_is_autoconfirmed()
        except UnauthorizedToken:
            return logout_per_token_expired(request)
        except (Token.DoesNotExist, ServerError):
            token_failed = True

        data["is_autoconfirmed"] = is_autoconfirmed
        data["token_failed"] = token_failed

        # TOKEN
        auth_token, created = AuthToken.objects.get_or_create(user=user)

        # POSTing
        if request.method == "POST":
            action = request.POST["action"]
            if action == "update_language":
                prefs, _ = Preferences.objects.get_or_create(user=user)
                prefs.language = request.POST["language"]
                prefs.save()

                translation.activate(prefs.language)
                request.LANGUAGE_CODE = translation.get_language()
            elif action == "update_token":
                if auth_token:
                    auth_token.delete()
                auth_token = AuthToken.objects.create(user=user)

        data["token"] = auth_token.key

        data["language"] = Preferences.objects.get_language(user, "en")
        data["language_choices"] = LANGUAGE_CHOICES

    return render(request, "profile.html", data)

@require_POST
def language_change(request, code):
    translation.activate(code)
    request.LANGUAGE_CODE = translation.get_language()
    res = HttpResponse(status=200)
    res.headers["HX-Refresh"] = "true"
    if request.user.is_authenticated and code in LANGUAGE_CODE_LIST:
        prefs, _ = Preferences.objects.get_or_create(user=request.user)
        prefs.language = code
        prefs.save()
    else:
        request.session["language_code"] = code
    return res
