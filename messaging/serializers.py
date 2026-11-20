from rest_framework import serializers
from .models import Message


class MessageSerializer(serializers.ModelSerializer):
    sender_username = serializers.CharField(source="sender.username", read_only=True)
    recipient_username = serializers.CharField(source="recipient.username", read_only=True)
    is_mine = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            "id", "sender", "sender_username", "recipient", "recipient_username",
            "content", "created_at", "read_at", "is_mine",
        ]
        read_only_fields = fields

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request) and obj.sender_id == request.user.id