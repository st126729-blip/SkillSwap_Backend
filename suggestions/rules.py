from django.db.models import Q

from projects.models import Milestone
from trades.models import Trade
from groups.models import GroupMembership
from messaging.models import Message


def _item(key, title, link, priority, count):
    return {"key": key, "title": title, "link": link,
            "priority": priority, "count": count}


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _milestone_link(qs, n, status=None):
    """1 việc -> mở thẳng dialog milestone đó; nhiều việc -> lọc theo status."""
    if n == 1:
        return f"/milestones?id={qs.first().id}"
    if status:
        return f"/milestones?status={status}"
    return "/milestones"


def milestones_to_fund(user):
    """Owner: milestone PENDING, project đã có collaborator -> cần fund."""
    qs = Milestone.objects.filter(
        project__owner=user,
        project__collaborator__isnull=False,
        status=Milestone.Status.PENDING,
    )
    n = qs.count()
    if not n:
        return None
    return _item("fund_milestone",
                 f"Fund {_plural(n, 'milestone', 'milestones')}",
                 _milestone_link(qs, n, Milestone.Status.PENDING), "high", n)


def milestones_to_submit(user):
    """Collaborator: milestone đã FUNDED nhưng chưa nộp việc."""
    qs = Milestone.objects.filter(
        project__collaborator=user,
        status=Milestone.Status.FUNDED,
        submitted_at__isnull=True,
    )
    n = qs.count()
    if not n:
        return None
    return _item("submit_work",
                 f"Submit work for {_plural(n, 'milestone', 'milestones')}",
                 _milestone_link(qs, n,  Milestone.Status.FUNDED), "high", n)


def milestones_to_approve(user):
    """Milestone FUNDED, đã có bài nộp, và bạn chưa approve."""
    qs = Milestone.objects.filter(
        Q(project__owner=user, owner_approved=False)
        | Q(project__collaborator=user, collaborator_approved=False),
        status=Milestone.Status.FUNDED,
        submitted_at__isnull=False,
    )
    n = qs.count()
    if not n:
        return None
    return _item("approve_milestone",
                 f"Review and approve {_plural(n, 'submitted milestone', 'submitted milestones')}",
                 _milestone_link(qs, n, Milestone.Status.FUNDED), "high", n)


def pending_join_requests(user):
    """Join request PENDING vào các nhóm do bạn tạo."""
    n = GroupMembership.objects.filter(
        group__created_by=user,
        status=GroupMembership.Status.PENDING,
    ).count()
    if not n:
        return None
    return _item("join_requests",
                 f"Review {_plural(n, 'join request', 'join requests')} in your groups",
                 "/team", "medium", n)


def trades_awaiting_accept(user):
    """Trade đang chờ bạn (recipient) accept hoặc reject."""
    n = Trade.objects.filter(
        recipient=user, status=Trade.Status.PENDING).count()
    if not n:
        return None
    return _item("accept_trade",
                 f"Respond to {_plural(n, 'trade proposal', 'trade proposals')}",
                 "/trades", "medium", n)


def unread_messages(user):
    n = Message.objects.filter(recipient=user, read_at__isnull=True).count()
    if not n:
        return None
    return _item("unread_messages",
                 f"Read {_plural(n, 'unread message', 'unread messages')}",
                 "/inbox", "low", n)


# Thứ tự = ưu tiên khi cùng mức priority
RULES = [
    milestones_to_submit,
    milestones_to_approve,
    milestones_to_fund,
    trades_awaiting_accept,
    pending_join_requests,
    unread_messages,
]

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def build_suggestions(user):
    items = [r for rule in RULES if (r := rule(user))]
    items.sort(key=lambda s: PRIORITY_ORDER[s["priority"]])  # sort ổn định
    return items or [_item("all_clear", "You're all caught up", "/", "low", 0)]