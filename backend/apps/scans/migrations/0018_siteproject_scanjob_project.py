import uuid
from urllib.parse import urlparse

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def backfill_site_projects(apps, schema_editor):
    SiteProject = apps.get_model("scans", "SiteProject")
    ScanJob = apps.get_model("scans", "ScanJob")
    projects = {}
    for scan in ScanJob.objects.order_by("user_id", "created_at", "id").iterator():
        hostname = (
            (urlparse(scan.normalized_url or scan.original_url or "").hostname or "")
            .lower()
            .rstrip(".")
        )
        if not hostname:
            raise RuntimeError(f"ScanJob {scan.pk} 無法解析 hostname，停止網站專案回填。")
        key = (scan.user_id, hostname)
        project = projects.get(key)
        if project is None:
            canonical_url = f"https://{hostname}/"
            project, _ = SiteProject.objects.get_or_create(
                owner_id=scan.user_id,
                hostname=hostname,
                archived_at=None,
                defaults={"name": hostname, "canonical_url": canonical_url},
            )
            projects[key] = project
        scan.project_id = project.id
        scan.save(update_fields=["project"])


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("scans", "0017_scanjob_categories"),
    ]

    operations = [
        migrations.CreateModel(
            name="SiteProject",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4, editable=False, primary_key=True, serialize=False
                    ),
                ),
                ("name", models.CharField(max_length=120)),
                ("canonical_url", models.URLField(max_length=2048)),
                ("hostname", models.CharField(db_index=True, max_length=255)),
                ("archived_at", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "owner",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="site_projects",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ["name", "hostname"]},
        ),
        migrations.AddField(
            model_name="scanjob",
            name="project",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="scan_jobs",
                to="scans.siteproject",
            ),
        ),
        migrations.RunPython(backfill_site_projects, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="siteproject",
            constraint=models.UniqueConstraint(
                condition=Q(archived_at__isnull=True),
                fields=("owner", "hostname"),
                name="unique_active_site_project_hostname_per_owner",
            ),
        ),
    ]
