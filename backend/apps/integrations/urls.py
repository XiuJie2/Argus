from django.urls import path

from apps.integrations.views import (
    GSCAuthorizeView,
    GSCCallbackView,
    GSCDisconnectView,
    GSCMetricsView,
    GSCPropertyView,
    GSCStatusView,
    GSCSyncView,
)

urlpatterns = [
    path("gsc/authorize/", GSCAuthorizeView.as_view(), name="gsc-authorize"),
    path("gsc/callback", GSCCallbackView.as_view(), name="gsc-callback"),
    path("gsc/status/", GSCStatusView.as_view(), name="gsc-status"),
    path("gsc/property/", GSCPropertyView.as_view(), name="gsc-property"),
    path("gsc/sync/", GSCSyncView.as_view(), name="gsc-sync"),
    path("gsc/metrics/", GSCMetricsView.as_view(), name="gsc-metrics"),
    path("gsc/disconnect/", GSCDisconnectView.as_view(), name="gsc-disconnect"),
]
