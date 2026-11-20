from django.contrib.auth import get_user_model
from rest_framework import serializers
from .models import Trade

User = get_user_model()


class TradeSerializer(serializers.ModelSerializer):
    initiator_username = serializers.CharField(source='initiator.username', read_only=True)
    recipient_username = serializers.CharField(source='recipient.username', read_only=True)
    # Ghi-only: gõ username người nhận
    recipient_name = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = Trade
        fields = [
            'id', 'initiator', 'initiator_username', 'recipient', 'recipient_username',
            'recipient_name',
            'offer_description', 'request_description', 'credit_amount', 'status',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['initiator', 'status', 'created_at', 'updated_at']
        extra_kwargs = {'recipient': {'required': False}}

    def validate_recipient_name(self, value):
        try:
            return User.objects.get(username=value.strip())
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Không tìm thấy user '{value}'.")

    def validate(self, attrs):
        user = attrs.pop('recipient_name', None)
        if user:
            attrs['recipient'] = user

        # Chỉ kiểm tra khi tạo mới (self.instance là None)
        if self.instance is None:
            recipient = attrs.get('recipient')
            if not recipient:
                raise serializers.ValidationError(
                    {"recipient_name": "Cần nhập username người nhận."}
                )
            request = self.context.get('request')
            if request and recipient == request.user:
                raise serializers.ValidationError(
                    {"recipient_name": "Không thể tự trade với chính mình."}
                )
        return attrs