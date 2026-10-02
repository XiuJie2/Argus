from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.scans.models import Finding, ScanJob, SiteProject


class SiteProjectApiTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="owner", email="owner@example.com", password="test-pass"
        )
        self.other = User.objects.create_user(
            username="other", email="other@example.com", password="test-pass"
        )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    @patch("apps.scans.serializers.assert_public_http_url", return_value="https://example.com/")
    def test_create_project_does_not_create_scan(self, _assert_public):
        response = self.client.post(
            "/api/projects/",
            {"name": "品牌官網", "canonical_url": "https://example.com/"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["hostname"], "example.com")
        self.assertEqual(ScanJob.objects.count(), 0)

    def test_projects_are_owner_scoped(self):
        own = SiteProject.objects.create(
            owner=self.user,
            name="自己的網站",
            canonical_url="https://example.com/",
            hostname="example.com",
        )
        foreign = SiteProject.objects.create(
            owner=self.other,
            name="別人的網站",
            canonical_url="https://other.example/",
            hostname="other.example",
        )
        response = self.client.get("/api/projects/")
        self.assertEqual(response.status_code, 200)
        ids = {item["id"] for item in response.data}
        self.assertIn(str(own.id), ids)
        self.assertNotIn(str(foreign.id), ids)
        self.assertEqual(self.client.get(f"/api/projects/{foreign.id}/").status_code, 404)

    def test_project_filters_dashboard_and_findings(self):
        first = SiteProject.objects.create(
            owner=self.user, name="A", canonical_url="https://a.example/", hostname="a.example"
        )
        second = SiteProject.objects.create(
            owner=self.user, name="B", canonical_url="https://b.example/", hostname="b.example"
        )
        first_scan = ScanJob.objects.create(
            user=self.user,
            project=first,
            original_url="https://a.example/",
            normalized_url="https://a.example/",
            origin="https://a.example",
            status="completed",
            overall_score=80,
        )
        ScanJob.objects.create(
            user=self.user,
            project=second,
            original_url="https://b.example/",
            normalized_url="https://b.example/",
            origin="https://b.example",
            status="completed",
            overall_score=20,
        )
        Finding.objects.create(
            scan_job=first_scan,
            severity="high",
            category="seo",
            title="標題缺失",
            description="說明",
            remediation="修正",
            ai_handoff_prompt="",
        )
        dashboard = self.client.get(f"/api/dashboard/?project_id={first.id}")
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.data["total_scans"], 1)
        self.assertEqual(dashboard.data["average_score"], 80.0)
        findings = self.client.get(f"/api/findings/?project_id={first.id}")
        self.assertEqual(findings.status_code, 200)
        self.assertEqual(findings.data["count"], 1)

    def test_archive_hides_project_but_preserves_scans(self):
        project = SiteProject.objects.create(
            owner=self.user, name="A", canonical_url="https://a.example/", hostname="a.example"
        )
        scan = ScanJob.objects.create(
            user=self.user,
            project=project,
            original_url="https://a.example/",
            normalized_url="https://a.example/",
            origin="https://a.example",
        )
        response = self.client.post(f"/api/projects/{project.id}/archive/")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/projects/").data, [])
        self.assertTrue(ScanJob.objects.filter(id=scan.id).exists())
