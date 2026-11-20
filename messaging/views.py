from django.contrib.auth.models import User
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from .models import Message
from .serializers import MessageSerializer

MAX_LENGTH = 2000


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def conversations(request):
    """One entry per person I have talked to, newest conversation first."""
    me = request.user
    messages = (
        Message.objects.filter(Q(sender=me) | Q(recipient=me))
        .select_related("sender", "recipient")
        .order_by("-created_at")
    )

    result = {}
    for m in messages:
        other = m.recipient if m.sender_id == me.id else m.sender
        entry = result.get(other.id)
        if entry is None:  # first hit is the latest message (ordered by -created_at)
            entry = {
                "user": {"id": other.id, "username": other.username},
                "last_message": MessageSerializer(m, context={"request": request}).data,
                "unread_count": 0,
            }
            result[other.id] = entry
        if m.recipient_id == me.id and m.read_at is None:
            entry["unread_count"] += 1

    return Response(list(result.values()))


@api_view(["GET", "POST"])
@permission_classes([permissions.IsAuthenticated])
def thread(request, username):
    """GET: messages between me and <username> (marks theirs as read). POST: send a message."""
    me = request.user
    other = get_object_or_404(User, username=username, is_active=True)

    if other.id == me.id:
        return Response({"detail": "You cannot message yourself."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == "GET":
        Message.objects.filter(sender=other, recipient=me, read_at__isnull=True).update(read_at=timezone.now())
        qs = (
            Message.objects.filter(Q(sender=me, recipient=other) | Q(sender=other, recipient=me))
            .select_related("sender", "recipient")
        )
        return Response(MessageSerializer(qs, many=True, context={"request": request}).data)

    content = str(request.data.get("content", "")).strip()
    if not content:
        return Response({"detail": "Message cannot be empty."}, status=status.HTTP_400_BAD_REQUEST)
    if len(content) > MAX_LENGTH:
        return Response({"detail": f"Message is too long (max {MAX_LENGTH} characters)."},
                        status=status.HTTP_400_BAD_REQUEST)

    msg = Message.objects.create(sender=me, recipient=other, content=content)
    return Response(MessageSerializer(msg, context={"request": request}).data,
                    status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([permissions.IsAuthenticated])
def unread_count(request):
    count = Message.objects.filter(recipient=request.user, read_at__isnull=True).count()
    return Response({"count": count})