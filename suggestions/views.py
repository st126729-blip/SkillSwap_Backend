from django.db.models import Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from groups.models import GroupMembership
from messaging.models import Message
from projects.models import Milestone, Project
from trades.models import Trade

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _plural(n, one, many):
    return one if n == 1 else many


def _item(key, title, link, priority, count=1):
    return {"key": key, "title": title, "link": link, "priority": priority, "count": count}


def build_suggestions(user):
    items = []
    MS = Milestone.Status

    # 1. Join requests waiting in groups I own
    n = GroupMembership.objects.filter(
        group__created_by=user, status=GroupMembership.Status.PENDING
    ).count()
    if n:
        items.append(_item(
            "join-requests",
            f"Review {n} pending join {_plural(n, 'request', 'requests')}",
            "/team", "high", n,
        ))

    # 2. Trade offers waiting for my answer
    n = Trade.objects.filter(recipient=user, status=Trade.Status.PENDING).count()
    if n:
        items.append(_item(
            "trades",
            f"Respond to {n} trade {_plural(n, 'offer', 'offers')}",
            "/trades", "high", n,
        ))

    # 3. Milestones I own that can be funded (needs an assigned collaborator)
    n = Milestone.objects.filter(
        project__owner=user,
        project__collaborator__isnull=False,
        status=MS.PENDING,
    ).count()
    if n:
        items.append(_item(
            "fund-milestones",
            f"Fund {n} {_plural(n, 'milestone', 'milestones')}",
            "/milestones", "high", n,
        ))

    # 4. Work submitted by my collaborator that I have not approved yet
    n = Milestone.objects.filter(
        project__owner=user,
        status=MS.FUNDED,
        submitted_at__isnull=False,
        owner_approved=False,
    ).count()
    if n:
        items.append(_item(
            "review-milestones",
            f"Review submitted work on {n} {_plural(n, 'milestone', 'milestones')}",
            "/milestones", "high", n,
        ))

    # 5. Funded milestones where I am the collaborator and have not submitted yet
    n = Milestone.objects.filter(
        project__collaborator=user,
        status=MS.FUNDED,
        submitted_at__isnull=True,
    ).count()
    if n:
        items.append(_item(
            "deliver-milestones",
            f"Submit work for {n} funded {_plural(n, 'milestone', 'milestones')}",
            "/milestones", "medium", n,
        ))

    # 6. I submitted work and still need to confirm so the credits get released
    n = Milestone.objects.filter(
        project__collaborator=user,
        status=MS.FUNDED,
        submitted_at__isnull=False,
        collaborator_approved=False,
    ).count()
    if n:
        items.append(_item(
            "confirm-milestones",
            f"Approve {n} {_plural(n, 'milestone', 'milestones')} to release credits",
            "/milestones", "medium", n,
        ))

    # 7. Disputes I am involved in
    n = Milestone.objects.filter(
        Q(project__owner=user) | Q(project__collaborator=user),
        status=MS.DISPUTED,
    ).count()
    if n:
        items.append(_item(
            "disputes",
            f"{n} {_plural(n, 'milestone is', 'milestones are')} under dispute",
            "/milestones", "medium", n,
        ))

    # 8. My open projects that still have no collaborator
    n = Project.objects.filter(
        owner=user, status=Project.Status.OPEN, collaborator__isnull=True
    ).count()
    if n:
        items.append(_item(
            "find-collaborator",
            f"{n} open {_plural(n, 'project needs', 'projects need')} a collaborator",
            "/projects", "low", n,
        ))

    # 9. Unread messages
    n = Message.objects.filter(recipient=user, read_at__isnull=True).count()
    if n:
        items.append(_item(
            "unread",
            f"Read {n} unread {_plural(n, 'message', 'messages')}",
            "/inbox", "medium", n,
        ))

    # 10. Nothing to do
    if not items:
        items.append(_item(
            "explore", "You're all caught up. Browse the feed or groups.", "/feed", "low", 0,
        ))

    items.sort(key=lambda i: PRIORITY_ORDER[i["priority"]])
    return items


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def suggestions(request):
    return Response(build_suggestions(request.user))