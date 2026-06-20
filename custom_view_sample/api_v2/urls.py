from django.urls import include, path

urlpatterns = [
    path("network/", include("custom_view.api_v2.network.urls")),
    path("floor/", include("custom_view.api_v2.floor.urls")),
    path("ipaddr/", include("custom_view.api_v2.ipaddr.urls")),
    path("port/", include("custom_view.api_v2.port.urls")),
    path("rack/", include("custom_view.api_v2.rack.urls")),
    path("id/", include("custom_view.api_v2.id.urls")),
    path("tulta/", include("custom_view.api_v2.tulta.urls")),
    path("google/", include("custom_view.api_v2.third_party.google.urls")),
    path("mole/", include("custom_view.api_v2.mole.urls")),
    path("wasabi/", include("custom_view.api_v2.wasabi.urls")),
]
