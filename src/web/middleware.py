from django.conf import settings
from django.utils import translation

from web.models import Preferences


def language_cookie_middleware(get_response):
    def middleware(request):
        if request.user.is_authenticated:
            language = Preferences.objects.get_language(
                request.user,
                settings.LANGUAGE_CODE,
            )
        elif "language_code" in request.session:
            language = request.session["language_code"]
        else:
            language = settings.LANGUAGE_CODE

        if language in settings.TRANSLATED_LANGUAGES:
            translation.activate(language)

        request.LANGUAGE_CODE = translation.get_language()
        return get_response(request)

    return middleware
