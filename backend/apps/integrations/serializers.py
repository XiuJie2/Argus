from django.utils import timezone
from rest_framework import serializers

from apps.integrations.models import GSCConnection, GSCSearchMetric
from apps.scans.serializers import VerifiedDomainSerializer


class ProjectInputSerializer(serializers.Serializer):
    project_id = serializers.UUIDField()


class GSCPropertySerializer(ProjectInputSerializer):
    site_url = serializers.CharField(max_length=2048)


class GSCSyncSerializer(ProjectInputSerializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["start_date"] > attrs["end_date"]:
            raise serializers.ValidationError("開始日期不得晚於結束日期。")
        if attrs["end_date"] > timezone.localdate():
            raise serializers.ValidationError("結束日期不得晚於今天。")
        if (attrs["end_date"] - attrs["start_date"]).days > 90:
            raise serializers.ValidationError("單次最多同步 91 天資料。")
        return attrs


class GSCConnectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSCConnection
        fields = [
            "project_id",
            "properties",
            "selected_property",
            "selected_permission_level",
            "connected_at",
            "updated_at",
            "last_synced_at",
            "last_error",
        ]
        read_only_fields = fields


class GSCStatusSerializer(GSCConnectionSerializer):
    connected = serializers.BooleanField()
    domain_verification = VerifiedDomainSerializer(allow_null=True)

    class Meta(GSCConnectionSerializer.Meta):
        fields = ["connected", *GSCConnectionSerializer.Meta.fields, "domain_verification"]
        extra_kwargs = {
            field: {"required": False}
            for field in GSCConnectionSerializer.Meta.fields
        }


class GSCSearchMetricSerializer(serializers.ModelSerializer):
    class Meta:
        model = GSCSearchMetric
        fields = ["date", "clicks", "impressions", "ctr", "position", "synced_at"]
        read_only_fields = fields
