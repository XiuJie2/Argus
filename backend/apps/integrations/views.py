from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.integrations.models import GSCConnection, GSCOAuthState
from apps.integrations.serializers import (
    GSCConnectionSerializer,
    GSCPropertySerializer,
    GSCSearchMetricSerializer,
    GSCStatusSerializer,
    GSCSyncSerializer,
    ProjectInputSerializer,
)
from apps.integrations.services import (
    GSCIntegrationError,
    authorization_url,
    exchange_code,
    list_properties,
    matching_properties,
    revoke_connection,
    save_tokens,
    sync_metrics,
    verify_domain_from_property,
)
from apps.scans.models import SiteProject
from apps.scans.serializers import VerifiedDomainSerializer


def _project_for(user, project_id):
    return SiteProject.objects.filter(id=project_id, owner=user, archived_at__isnull=True).first()


def _connection_for(user, project_id):
    return (
        GSCConnection.objects.select_related("project")
        .filter(
            project_id=project_id,
            project__owner=user,
            project__archived_at__isnull=True,
        )
        .first()
    )


def _domain_verification_for(project):
    labels = project.hostname.split(".")
    candidates = [".".join(labels[index:]) for index in range(max(len(labels) - 1, 1))]
    domains = project.owner.verified_domains.filter(domain__in=candidates)
    return next((domain for domain in domains if domain.is_effectively_verified), None)


def _domain_verification_data(project):
    domain = _domain_verification_for(project)
    return VerifiedDomainSerializer(domain).data if domain else None


def _error_response(exc: GSCIntegrationError):
    return Response({"detail": str(exc)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)


class GSCAuthorizeView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=ProjectInputSerializer,
        responses={
            200: inline_serializer(
                name="GSCAuthorizeResponse",
                fields={
                    "authorization_url": serializers.URLField(),
                    "expires_at": serializers.DateTimeField(),
                },
            )
        },
    )
    def post(self, request):
        serializer = ProjectInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        project = _project_for(request.user, serializer.validated_data["project_id"])
        if project is None:
            return Response({"detail": "找不到網站專案。"}, status=status.HTTP_404_NOT_FOUND)
        GSCOAuthState.objects.filter(expires_at__lte=timezone.now()).delete()
        oauth_state = GSCOAuthState.objects.create(
            user=request.user,
            project=project,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        try:
            url = authorization_url(oauth_state.token)
        except GSCIntegrationError as exc:
            oauth_state.delete()
            return _error_response(exc)
        return Response({"authorization_url": url, "expires_at": oauth_state.expires_at})


class GSCCallbackView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(exclude=True)
    def get(self, request):
        state_token = request.query_params.get("state", "")
        code = request.query_params.get("code", "")
        oauth_state = (
            GSCOAuthState.objects.select_related("project", "user")
            .filter(
                token=state_token,
                consumed_at__isnull=True,
                expires_at__gt=timezone.now(),
            )
            .first()
        )
        if oauth_state is None or not code:
            return self._redirect("error", "Google 授權請求已失效，請重新連線。")
        oauth_state.consumed_at = timezone.now()
        oauth_state.save(update_fields=["consumed_at"])
        try:
            payload = exchange_code(code)
            connection, _ = GSCConnection.objects.get_or_create(project=oauth_state.project)
            save_tokens(connection, payload)
            properties = list_properties(connection)
            connection.properties = properties
            matches = matching_properties(properties, oauth_state.project.hostname)
            if matches:
                selected = next(
                    (item for item in matches if item["permission_level"] == "siteOwner"),
                    matches[0],
                )
                connection.selected_property = selected["site_url"]
                connection.selected_permission_level = selected["permission_level"]
            connection.last_error = ""
            connection.save()
            verify_domain_from_property(connection)
        except GSCIntegrationError as exc:
            return self._redirect("error", str(exc), oauth_state.project_id)
        return self._redirect("connected", "", oauth_state.project_id)

    @staticmethod
    def _redirect(result, message="", project_id=None):
        target = settings.GSC_FRONTEND_RETURN_PATH.format(project_id=project_id or "")
        query = urlencode({"gsc": result, **({"message": message} if message else {})})
        return HttpResponseRedirect(f"{target}?{query}")


class GSCStatusView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[ProjectInputSerializer],
        responses={200: GSCStatusSerializer},
    )
    def get(self, request):
        serializer = ProjectInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        project_id = serializer.validated_data["project_id"]
        project = _project_for(request.user, project_id)
        if project is None:
            return Response({"detail": "找不到網站專案。"}, status=status.HTTP_404_NOT_FOUND)
        connection = _connection_for(request.user, project_id)
        if connection is None:
            return Response(
                {
                    "connected": False,
                    "domain_verification": _domain_verification_data(project),
                }
            )
        return Response(
            {
                "connected": True,
                **GSCConnectionSerializer(connection).data,
                "domain_verification": _domain_verification_data(project),
            }
        )


class GSCPropertyView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=GSCPropertySerializer, responses={200: GSCConnectionSerializer})
    def post(self, request):
        serializer = GSCPropertySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = _connection_for(request.user, serializer.validated_data["project_id"])
        if connection is None:
            return Response({"detail": "尚未連接 Search Console。"}, status=404)
        requested_site_url = serializer.validated_data["site_url"]
        selected = next(
            (item for item in connection.properties if item["site_url"] == requested_site_url),
            None,
        )
        if selected is None:
            return Response({"detail": "所選資源不在 Google 授權清單中。"}, status=400)
        if selected not in matching_properties([selected], connection.project.hostname):
            return Response({"detail": "所選資源不涵蓋目前網站。"}, status=400)
        connection.selected_property = selected["site_url"]
        connection.selected_permission_level = selected["permission_level"]
        connection.save(
            update_fields=["selected_property", "selected_permission_level", "updated_at"]
        )
        domain_verified = verify_domain_from_property(connection)
        return Response(
            {**GSCConnectionSerializer(connection).data, "domain_verified": domain_verified}
        )


class GSCSyncView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=GSCSyncSerializer,
        responses={
            200: inline_serializer(
                name="GSCSyncResponse",
                fields={
                    "synced_rows": serializers.IntegerField(),
                    "last_synced_at": serializers.DateTimeField(allow_null=True),
                },
            )
        },
    )
    def post(self, request):
        serializer = GSCSyncSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        connection = _connection_for(request.user, serializer.validated_data["project_id"])
        if connection is None:
            return Response({"detail": "尚未連接 Search Console。"}, status=404)
        try:
            rows = sync_metrics(
                connection,
                serializer.validated_data["start_date"],
                serializer.validated_data["end_date"],
            )
        except GSCIntegrationError as exc:
            connection.last_error = str(exc)
            connection.save(update_fields=["last_error", "updated_at"])
            return _error_response(exc)
        return Response({"synced_rows": rows, "last_synced_at": connection.last_synced_at})


class GSCMetricsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[GSCSyncSerializer],
        responses={
            200: inline_serializer(
                name="GSCMetricsResponse",
                fields={
                    "source": serializers.CharField(),
                    "property": serializers.CharField(),
                    "last_synced_at": serializers.DateTimeField(allow_null=True),
                    "results": GSCSearchMetricSerializer(many=True),
                },
            )
        },
    )
    def get(self, request):
        serializer = GSCSyncSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        connection = _connection_for(request.user, serializer.validated_data["project_id"])
        if connection is None:
            return Response({"detail": "尚未連接 Search Console。"}, status=404)
        rows = connection.metrics.filter(
            date__gte=serializer.validated_data["start_date"],
            date__lte=serializer.validated_data["end_date"],
        )
        return Response(
            {
                "source": "google_search_console",
                "property": connection.selected_property,
                "last_synced_at": connection.last_synced_at,
                "results": GSCSearchMetricSerializer(rows, many=True).data,
            }
        )


class GSCDisconnectView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        parameters=[ProjectInputSerializer],
        responses={204: OpenApiResponse(description="已移除 Search Console 連線。")},
    )
    def delete(self, request):
        serializer = ProjectInputSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        connection = _connection_for(request.user, serializer.validated_data["project_id"])
        if connection is not None:
            revoke_connection(connection)
            connection.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
