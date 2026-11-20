from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Group, GroupMembership, GroupPost, GroupPostComment
from .serializers import (
    GroupSerializer, GroupPostSerializer, GroupPostCommentSerializer,
    MembershipRequestSerializer,
)
from .permissions import IsGroupMemberOrReadOnly

APPROVED = GroupMembership.Status.APPROVED
PENDING = GroupMembership.Status.PENDING


def is_approved_member(group, user):
    return GroupMembership.objects.filter(group=group, user=user, status=APPROVED).exists()


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_create(self, serializer):
        group = serializer.save(created_by=self.request.user)
        # The owner is automatically an approved member
        GroupMembership.objects.create(group=group, user=self.request.user, status=APPROVED)

    # Only the owner may edit or delete a group (partial_update goes through update)
    def update(self, request, *args, **kwargs):
        if self.get_object().created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can edit this group.'}, status=status.HTTP_403_FORBIDDEN)
        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        if self.get_object().created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can delete this group.'}, status=status.HTTP_403_FORBIDDEN)
        return super().destroy(request, *args, **kwargs)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def join(self, request, pk=None):
        """Send a join request. The owner must approve it before the user becomes a member."""
        group = self.get_object()
        if group.created_by_id == request.user.id:
            return Response({'detail': 'You own this group.'}, status=status.HTTP_400_BAD_REQUEST)
        membership, created = GroupMembership.objects.get_or_create(
            group=group, user=request.user, defaults={'status': PENDING},
        )
        if not created:
            msg = 'Already a member.' if membership.status == APPROVED else 'Your request is already pending.'
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        return Response(GroupSerializer(group, context={'request': request}).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def leave(self, request, pk=None):
        """Leave the group, or cancel a pending request. The owner cannot leave their own group."""
        group = self.get_object()
        if group.created_by_id == request.user.id:
            return Response({'detail': 'The owner cannot leave the group.'}, status=status.HTTP_400_BAD_REQUEST)
        deleted, _ = GroupMembership.objects.filter(group=group, user=request.user).delete()
        if not deleted:
            return Response({'detail': 'You are not a member.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(GroupSerializer(group, context={'request': request}).data)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def requests(self, request, pk=None):
        """List pending requests. Owner only."""
        group = self.get_object()
        if group.created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can view requests.'}, status=status.HTTP_403_FORBIDDEN)
        pending = group.memberships.filter(status=PENDING).select_related('user').order_by('joined_at')
        return Response(MembershipRequestSerializer(pending, many=True).data)

    @action(detail=True, methods=['post'], url_path=r'requests/(?P<mid>[0-9]+)/approve',
            permission_classes=[permissions.IsAuthenticated])
    def approve(self, request, pk=None, mid=None):
        group = self.get_object()
        if group.created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can approve.'}, status=status.HTTP_403_FORBIDDEN)
        m = get_object_or_404(GroupMembership, pk=mid, group=group, status=PENDING)
        m.status = APPROVED
        m.save(update_fields=['status'])
        return Response({'detail': 'Approved.'})

    @action(detail=True, methods=['post'], url_path=r'requests/(?P<mid>[0-9]+)/reject',
            permission_classes=[permissions.IsAuthenticated])
    def reject(self, request, pk=None, mid=None):
        group = self.get_object()
        if group.created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can reject.'}, status=status.HTTP_403_FORBIDDEN)
        m = get_object_or_404(GroupMembership, pk=mid, group=group, status=PENDING)
        m.delete()
        return Response({'detail': 'Rejected.'})

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def members(self, request, pk=None):
        """List approved members. Owner only."""
        group = self.get_object()
        if group.created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can view members.'}, status=status.HTTP_403_FORBIDDEN)
        approved = group.memberships.filter(status=APPROVED).select_related('user').order_by('joined_at')
        return Response(MembershipRequestSerializer(approved, many=True).data)

    @action(detail=True, methods=['delete'], url_path=r'members/(?P<mid>[0-9]+)',
            permission_classes=[permissions.IsAuthenticated])
    def kick(self, request, pk=None, mid=None):
        """Remove a member from the group. Owner only."""
        group = self.get_object()
        if group.created_by_id != request.user.id:
            return Response({'detail': 'Only the owner can remove members.'}, status=status.HTTP_403_FORBIDDEN)
        m = get_object_or_404(GroupMembership, pk=mid, group=group, status=APPROVED)
        if m.user_id == group.created_by_id:
            return Response({'detail': 'The owner cannot be removed.'}, status=status.HTTP_400_BAD_REQUEST)
        m.delete()
        return Response({'detail': 'Removed.'})

    @action(detail=True, methods=['get', 'post'], permission_classes=[permissions.IsAuthenticatedOrReadOnly])
    def posts(self, request, pk=None):
        group = self.get_object()

        if request.method == 'GET':
            if not request.user.is_authenticated or not is_approved_member(group, request.user):
                return Response(
                    {'detail': 'Only approved members can view posts in this group.'},
                    status=status.HTTP_403_FORBIDDEN,
                )
            posts = group.posts.all()
            return Response(GroupPostSerializer(posts, many=True, context={'request': request}).data)

        # POST: only APPROVED members may post
        if not is_approved_member(group, request.user):
            return Response({'detail': 'You must be an approved member to post.'},
                            status=status.HTTP_403_FORBIDDEN)

        serializer = GroupPostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(group=group, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GroupPostViewSet(viewsets.ModelViewSet):
    """Detail / delete / comment on a specific post inside a group."""
    serializer_class = GroupPostSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return GroupPost.objects.filter(
            group__memberships__user=self.request.user,
            group__memberships__status=APPROVED,
        ).distinct()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def comment(self, request, pk=None):
        post = self.get_object()
        if not is_approved_member(post.group, request.user):
            return Response({'detail': 'You must be an approved member to comment.'},
                            status=status.HTTP_403_FORBIDDEN)
        content = request.data.get('content', '').strip()
        if not content:
            return Response({'detail': 'Comment content is required.'}, status=status.HTTP_400_BAD_REQUEST)
        comment = GroupPostComment.objects.create(post=post, author=request.user, content=content)
        return Response(GroupPostCommentSerializer(comment).data, status=status.HTTP_201_CREATED)