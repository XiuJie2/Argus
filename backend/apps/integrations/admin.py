from django.contrib import admin

from apps.integrations.models import GSCConnection, GSCOAuthState, GSCSearchMetric


@admin.register(GSCConnection)
class GSCConnectionAdmin(admin.ModelAdmin):
    list_display = ("project", "selected_property", "last_synced_at")
    readonly_fields = ("access_token_encrypted", "refresh_token_encrypted")


admin.site.register(GSCOAuthState)
admin.site.register(GSCSearchMetric)
