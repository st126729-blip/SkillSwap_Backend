from django.contrib.auth.models import User
from django.db import models


class Message(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name="received_messages")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)  # null = unread

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["sender", "recipient", "created_at"]),
            models.Index(fields=["recipient", "read_at"]),
        ]

    def __str__(self):
        return f"{self.sender.username} -> {self.recipient.username}"