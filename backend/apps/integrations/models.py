import secrets

from django.conf import settings
from django.db import models


class GSCConnection(models.Model):
    """單一網站專案的 Google Search Console 唯讀連線。"""

    project = models.OneToOneField(
        "scans.SiteProject",
        on_delete=models.CASCADE,
        related_name="gsc_connection",
    )
    access_token_encrypted = models.TextField(blank=True)
    refresh_token_encrypted = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    properties = models.JSONField(default=list, blank=True)
    selected_property = models.CharField(max_length=2048, blank=True)
    selected_permission_level = models.CharField(max_length=32, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)
    last_error = models.CharField(max_length=255, blank=True)

    def __str__(self) -> str:
        return f"GSC<{self.project_id}>"


class GSCOAuthState(models.Model):
    """一次性 OAuth state；callback 不依賴前端 JWT 或瀏覽器 session。"""

    token = models.CharField(max_length=64, unique=True, default=secrets.token_urlsafe)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    project = models.ForeignKey("scans.SiteProject", on_delete=models.CASCADE)
    expires_at = models.DateTimeField(db_index=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class GSCSearchMetric(models.Model):
    """Search Analytics 日維度快照；數值定義維持 Google 原始語意。"""

    connection = models.ForeignKey(
        GSCConnection,
        on_delete=models.CASCADE,
        related_name="metrics",
    )
    date = models.DateField(db_index=True)
    clicks = models.FloatField(default=0)
    impressions = models.FloatField(default=0)
    ctr = models.FloatField(default=0)
    position = models.FloatField(default=0)
    synced_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["date"]
        constraints = [
            models.UniqueConstraint(
                fields=["connection", "date"],
                name="unique_gsc_metric_per_connection_date",
            ),
        ]
