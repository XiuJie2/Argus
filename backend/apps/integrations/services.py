from datetime import timedelta
from urllib.parse import quote, urlencode, urlparse

import httpx
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.integrations.crypto import decrypt_token, encrypt_token
from apps.integrations.models import GSCConnection, GSCSearchMetric
from apps.scans.domain_verification import generate_token
from apps.scans.models import VerifiedDomain

GSC_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GSC_SITES_URL = "https://www.googleapis.com/webmasters/v3/sites"
GOOGLE_REVOKE_URL = "https://oauth2.googleapis.com/revoke"
HTTP_TIMEOUT = 20.0
READABLE_PERMISSION_LEVELS = {"siteOwner", "siteFullUser", "siteRestrictedUser"}


class GSCIntegrationError(RuntimeError):
    pass


def ensure_configured() -> None:
    if not settings.GSC_OAUTH_CLIENT_ID or not settings.GSC_OAUTH_CLIENT_SECRET:
        raise GSCIntegrationError("Google Search Console 尚未完成系統設定。")


def authorization_url(state: str) -> str:
    ensure_configured()
    return f"{GOOGLE_AUTH_URL}?{
        urlencode(
            {
                'client_id': settings.GSC_OAUTH_CLIENT_ID,
                'redirect_uri': settings.GSC_OAUTH_REDIRECT_URI,
                'response_type': 'code',
                'scope': GSC_SCOPE,
                'access_type': 'offline',
                'include_granted_scopes': 'true',
                'prompt': 'consent',
                'state': state,
            }
        )
    }"


def _google_post(url: str, data: dict) -> dict:
    try:
        response = httpx.post(url, data=data, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GSCIntegrationError("Google 授權服務暫時無法使用。") from exc


def exchange_code(code: str) -> dict:
    ensure_configured()
    return _google_post(
        GOOGLE_TOKEN_URL,
        {
            "code": code,
            "client_id": settings.GSC_OAUTH_CLIENT_ID,
            "client_secret": settings.GSC_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GSC_OAUTH_REDIRECT_URI,
            "grant_type": "authorization_code",
        },
    )


def _refresh(connection: GSCConnection) -> str:
    refresh_token = decrypt_token(connection.refresh_token_encrypted)
    if not refresh_token:
        raise GSCIntegrationError("Google 授權已失效，請重新連線。")
    payload = _google_post(
        GOOGLE_TOKEN_URL,
        {
            "refresh_token": refresh_token,
            "client_id": settings.GSC_OAUTH_CLIENT_ID,
            "client_secret": settings.GSC_OAUTH_CLIENT_SECRET,
            "grant_type": "refresh_token",
        },
    )
    access_token = payload.get("access_token", "")
    if not access_token:
        raise GSCIntegrationError("Google 未回傳可用的存取權杖。")
    connection.access_token_encrypted = encrypt_token(access_token)
    connection.token_expires_at = timezone.now() + timedelta(
        seconds=max(int(payload.get("expires_in", 3600)) - 60, 60)
    )
    connection.save(update_fields=["access_token_encrypted", "token_expires_at", "updated_at"])
    return access_token


def access_token(connection: GSCConnection) -> str:
    if connection.token_expires_at and connection.token_expires_at > timezone.now():
        token = decrypt_token(connection.access_token_encrypted)
        if token:
            return token
    return _refresh(connection)


def save_tokens(connection: GSCConnection, payload: dict) -> None:
    token = payload.get("access_token", "")
    if not token:
        raise GSCIntegrationError("Google 未回傳可用的存取權杖。")
    connection.access_token_encrypted = encrypt_token(token)
    if payload.get("refresh_token"):
        connection.refresh_token_encrypted = encrypt_token(payload["refresh_token"])
    connection.token_expires_at = timezone.now() + timedelta(
        seconds=max(int(payload.get("expires_in", 3600)) - 60, 60)
    )
    connection.scopes = payload.get("scope", GSC_SCOPE).split()


def _google_json(method: str, url: str, token: str, json: dict | None = None) -> dict:
    try:
        response = httpx.request(
            method,
            url,
            headers={"Authorization": f"Bearer {token}"},
            json=json,
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise GSCIntegrationError("Google Search Console API 暫時無法使用。") from exc


def list_properties(connection: GSCConnection) -> list[dict]:
    payload = _google_json("GET", GSC_SITES_URL, access_token(connection))
    return [
        {"site_url": item.get("siteUrl", ""), "permission_level": item.get("permissionLevel", "")}
        for item in payload.get("siteEntry", [])
        if item.get("siteUrl")
    ]


def property_covers_hostname(site_url: str, hostname: str) -> bool:
    hostname = hostname.lower().rstrip(".")
    if site_url.startswith("sc-domain:"):
        domain = site_url.removeprefix("sc-domain:").lower().rstrip(".")
        return hostname == domain or hostname.endswith(f".{domain}")
    return (urlparse(site_url).hostname or "").lower().rstrip(".") == hostname


def property_proves_hostname_ownership(site_url: str, hostname: str) -> bool:
    """Domain property 可涵蓋子網域；URL-prefix 必須是該 host 根路徑。"""
    if site_url.startswith("sc-domain:"):
        return property_covers_hostname(site_url, hostname)
    parsed = urlparse(site_url)
    return property_covers_hostname(site_url, hostname) and parsed.path in {"", "/"}


def matching_properties(properties: list[dict], hostname: str) -> list[dict]:
    return [
        item
        for item in properties
        if item.get("permission_level") in READABLE_PERMISSION_LEVELS
        and property_covers_hostname(item["site_url"], hostname)
    ]


def revoke_connection(connection: GSCConnection) -> None:
    """盡力撤銷 Google token；即使 Google 無回應仍由呼叫端刪除本地連線。"""
    try:
        token = decrypt_token(connection.refresh_token_encrypted) or decrypt_token(
            connection.access_token_encrypted
        )
    except ValueError:
        return
    if not token:
        return
    try:
        httpx.post(GOOGLE_REVOKE_URL, data={"token": token}, timeout=HTTP_TIMEOUT)
    except httpx.HTTPError:
        return


def verify_domain_from_property(connection: GSCConnection) -> bool:
    proves_ownership = property_proves_hostname_ownership(
        connection.selected_property, connection.project.hostname
    )
    if connection.selected_permission_level != "siteOwner" or not proves_ownership:
        return False
    now = timezone.now()
    domain, _ = VerifiedDomain.objects.get_or_create(
        user=connection.project.owner,
        domain=connection.project.hostname,
        defaults={"token": generate_token()},
    )
    domain.status = VerifiedDomain.Status.VERIFIED
    domain.method = VerifiedDomain.Method.GOOGLE_SEARCH_CONSOLE
    domain.verified_at = now
    domain.last_checked_at = now
    domain.expires_at = now + timedelta(days=settings.ARGUS_DOMAIN_VERIFICATION_TTL_DAYS)
    domain.last_error = ""
    domain.save(
        update_fields=[
            "status",
            "method",
            "verified_at",
            "last_checked_at",
            "expires_at",
            "last_error",
        ]
    )
    return True


def sync_metrics(connection: GSCConnection, start_date, end_date) -> int:
    if not connection.selected_property:
        raise GSCIntegrationError("請先選擇 Search Console 資源。")
    encoded_property = quote(connection.selected_property, safe="")
    url = f"{GSC_SITES_URL}/{encoded_property}/searchAnalytics/query"
    payload = _google_json(
        "POST",
        url,
        access_token(connection),
        {
            "startDate": str(start_date),
            "endDate": str(end_date),
            "dimensions": ["date"],
            "rowLimit": 25000,
        },
    )
    count = 0
    with transaction.atomic():
        GSCSearchMetric.objects.filter(
            connection=connection,
            date__gte=start_date,
            date__lte=end_date,
        ).delete()
        for row in payload.get("rows", []):
            if not row.get("keys"):
                continue
            GSCSearchMetric.objects.update_or_create(
                connection=connection,
                date=row["keys"][0],
                defaults={
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": row.get("ctr", 0),
                    "position": row.get("position", 0),
                },
            )
            count += 1
        connection.last_synced_at = timezone.now()
        connection.last_error = ""
        connection.save(update_fields=["last_synced_at", "last_error", "updated_at"])
    verify_domain_from_property(connection)
    return count
