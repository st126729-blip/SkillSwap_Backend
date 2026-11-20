from rest_framework import serializers
from django.db.models import Avg
from .models import Vouch


class VouchSerializer(serializers.ModelSerializer):
    voucher_username = serializers.CharField(source='voucher.username', read_only=True)
    vouchee_username = serializers.CharField(source='vouchee.username', read_only=True)

    class Meta:
        model = Vouch
        fields = [
            'id', 'voucher', 'voucher_username', 'vouchee', 'vouchee_username',
            'skill_area', 'technical_quality', 'reliability', 'comment',
            'reference_id', 'created_at',
        ]
        read_only_fields = ['voucher', 'created_at']

    def validate(self, data):
        request = self.context['request']
        vouchee = data.get('vouchee')
        if vouchee == request.user:
            raise serializers.ValidationError("You cannot vouch for yourself.")
        return data


class ReputationSummarySerializer(serializers.Serializer):
    """Tổng hợp điểm reputation của 1 user — không map trực tiếp 1 model, tự build trong view."""
    user_id = serializers.IntegerField()
    username = serializers.CharField()
    vouch_count = serializers.IntegerField()
    avg_technical_quality = serializers.FloatField(allow_null=True)
    avg_reliability = serializers.FloatField(allow_null=True)