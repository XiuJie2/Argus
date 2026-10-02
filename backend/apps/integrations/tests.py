from datetime import date, timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.integrations.crypto import encrypt_token
from apps.integrations.models import GSCConnection, GSCOAuthState, GSCSearchMetric
from apps.integrations.services import sync_metrics
from apps.scans.models import SiteProject, VerifiedDomain


@override_settings(
    GSC_OAUTH_CLIENT_ID="client-id",
    GSC_OAUTH_CLIENT_SECRET="client-secret",
    GSC_OAUTH_REDIRECT_URI="https://ars.clouda.dpdns.org/api/integrations/gsc/callback",
)
class GSCIntegrationTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="owner@example.com",
            email="owner@example.com",
            password="safe-test-password",
        )
        self.other = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="safe-test-password",
        )
        self.project = SiteProject.objects.create(
            owner=self.user,
            name="網站",
            canonical_url="https://www.example.com/",
            hostname="www.example.com",
        )
        self.client.force_authenticate(self.user)

    def test_authorize_creates_one_time_owner_scoped_state(self):
        self.assertEqual(
            reverse("gsc-callback"),
            "/api/integrations/gsc/callback",
        )
        response = self.client.post(reverse("gsc-authorize"), {"project_id": self.project.id})
        self.assertEqual(response.status_code, 200)
        self.assertIn("accounts.google.com", response.data["authorization_url"])
        self.assertIn("ars.clouda.dpdns.org", response.data["authorization_url"])
        state = GSCOAuthState.objects.get()
        self.assertEqual(state.user, self.user)
        self.assertEqual(state.project, self.project)

        self.client.force_authenticate(self.other)
        response = self.client.post(reverse("gsc-authorize"), {"project_id": self.project.id})
        self.assertEqual(response.status_code, 404)

    @patch("apps.integrations.views.list_properties")
    @patch("apps.integrations.views.exchange_code")
    def test_callback_connects_and_owner_property_verifies_domain(self, exchange, properties):
        state = GSCOAuthState.objects.create(
            user=self.user,
            project=self.project,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        exchange.return_value = {
            "access_token": "access-value",
            "refresh_token": "refresh-value",
            "expires_in": 3600,
            "scope": "https://www.googleapis.com/auth/webmasters.readonly",
        }
        properties.return_value = [
            {"site_url": "sc-domain:example.com", "permission_level": "siteOwner"}
        ]

        response = self.client.get(reverse("gsc-callback"), {"state": state.token, "code": "code"})
        self.assertEqual(response.status_code, 302)
        connection = GSCConnection.objects.get(project=self.project)
        self.assertNotIn("access-value", connection.access_token_encrypted)
        self.assertEqual(connection.selected_property, "sc-domain:example.com")
        verified = VerifiedDomain.objects.get(user=self.user, domain="www.example.com")
        self.assertEqual(verified.method, VerifiedDomain.Method.GOOGLE_SEARCH_CONSOLE)
        self.assertTrue(verified.is_effectively_verified)
        status_response = self.client.get(
            reverse("gsc-status"), {"project_id": self.project.id}
        )
        self.assertEqual(status_response.status_code, 200)
        self.assertTrue(status_response.data["domain_verification"]["is_effectively_verified"])
        self.assertEqual(status_response.data["domain_verification"]["method"], "gsc")
        state.refresh_from_db()
        self.assertIsNotNone(state.consumed_at)

        replay = self.client.get(
            reverse("gsc-callback"), {"state": state.token, "code": "second-code"}
        )
        self.assertEqual(replay.status_code, 302)
        self.assertIn("gsc=error", replay["Location"])
        exchange.assert_called_once_with("code")

    @patch("apps.integrations.views.list_properties")
    @patch("apps.integrations.views.exchange_code")
    def test_full_user_can_connect_but_does_not_verify_domain(self, exchange, properties):
        state = GSCOAuthState.objects.create(
            user=self.user,
            project=self.project,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        exchange.return_value = {
            "access_token": "access-value",
            "refresh_token": "refresh-value",
            "expires_in": 3600,
        }
        properties.return_value = [
            {"site_url": "https://www.example.com/", "permission_level": "siteFullUser"}
        ]
        self.client.get(reverse("gsc-callback"), {"state": state.token, "code": "code"})
        self.assertFalse(VerifiedDomain.objects.filter(user=self.user).exists())

    @patch("apps.integrations.views.list_properties")
    @patch("apps.integrations.views.exchange_code")
    def test_path_prefix_owner_does_not_verify_whole_hostname(self, exchange, properties):
        state = GSCOAuthState.objects.create(
            user=self.user,
            project=self.project,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        exchange.return_value = {
            "access_token": "access-value",
            "refresh_token": "refresh-value",
            "expires_in": 3600,
        }
        properties.return_value = [
            {"site_url": "https://www.example.com/blog/", "permission_level": "siteOwner"}
        ]
        self.client.get(reverse("gsc-callback"), {"state": state.token, "code": "code"})
        self.assertFalse(VerifiedDomain.objects.filter(user=self.user).exists())

    @patch("apps.integrations.services._google_json")
    def test_sync_upserts_daily_metrics(self, google_json):
        connection = GSCConnection.objects.create(
            project=self.project,
            access_token_encrypted=encrypt_token("access-value"),
            token_expires_at=timezone.now() + timedelta(hours=1),
            selected_property="sc-domain:example.com",
            selected_permission_level="siteFullUser",
        )
        google_json.return_value = {
            "rows": [
                {
                    "keys": ["2026-09-30"],
                    "clicks": 12,
                    "impressions": 120,
                    "ctr": 0.1,
                    "position": 4.5,
                }
            ]
        }
        self.assertEqual(sync_metrics(connection, date(2026, 9, 30), date(2026, 9, 30)), 1)
        metric = GSCSearchMetric.objects.get(connection=connection)
        self.assertEqual(metric.clicks, 12)
        self.assertEqual(metric.impressions, 120)

    def test_metrics_endpoint_is_owner_scoped(self):
        connection = GSCConnection.objects.create(project=self.project)
        GSCSearchMetric.objects.create(connection=connection, date=date(2026, 9, 30), clicks=3)
        params = {
            "project_id": self.project.id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
        }
        response = self.client.get(reverse("gsc-metrics"), params)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["source"], "google_search_console")
        self.assertEqual(response.data["results"][0]["clicks"], 3.0)

        self.client.force_authenticate(self.other)
        response = self.client.get(reverse("gsc-metrics"), params)
        self.assertEqual(response.status_code, 404)

    def test_status_exposes_manual_parent_domain_verification_without_connection(self):
        VerifiedDomain.objects.create(
            user=self.user,
            domain="example.com",
            status=VerifiedDomain.Status.VERIFIED,
            method=VerifiedDomain.Method.DNS_TXT,
            token="test-token",
            verified_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=30),
        )

        response = self.client.get(reverse("gsc-status"), {"project_id": self.project.id})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["connected"])
        self.assertEqual(response.data["domain_verification"]["domain"], "example.com")
        self.assertTrue(response.data["domain_verification"]["is_effectively_verified"])

    def test_property_must_cover_project_hostname(self):
        connection = GSCConnection.objects.create(
            project=self.project,
            properties=[
                {"site_url": "sc-domain:other.example", "permission_level": "siteOwner"}
            ],
        )
        response = self.client.post(
            reverse("gsc-property"),
            {"project_id": self.project.id, "site_url": "sc-domain:other.example"},
        )
        self.assertEqual(response.status_code, 400)
        connection.refresh_from_db()
        self.assertEqual(connection.selected_property, "")
