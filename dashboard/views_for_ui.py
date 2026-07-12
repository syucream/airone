from typing import TYPE_CHECKING

from airone.lib.http import http_get, render

if TYPE_CHECKING:
    from django.http import HttpRequest, HttpResponse


@http_get
def index(request: HttpRequest) -> HttpResponse:
    return render(request, "frontend/index.html")
