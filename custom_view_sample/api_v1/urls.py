from django.urls import include, re_path

from .entry.urls import urlpatterns as entry_urlpatterns

urlpatterns = [
    re_path(r"^entry/", include(entry_urlpatterns)),
]
