from rest_framework import serializers
from .models import Group, GroupMembership, GroupPost, GroupPostComment


class GroupPostCommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        model = GroupPostComment
        fields = ['id', 'post', 'author', 'author_username', 'content', 'created_at']
        read_only_fields = ['post', 'author', 'created_at']


class GroupPostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    comments = GroupPostCommentSerializer(many=True, read_only=True)
    comment_count = serializers.SerializerMethodField()

    class Meta:
        model = GroupPost
        fields = [
            'id', 'group', 'author', 'author_username', 'content', 'image',
            'comments', 'comment_count', 'created_at',
        ]
        read_only_fields = ['group', 'author', 'created_at']

    def get_comment_count(self, obj):
        return obj.comments.count()


class MembershipRequestSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = GroupMembership
        fields = ['id', 'user', 'username', 'status', 'joined_at']
        read_only_fields = fields


class GroupSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    member_count = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()
    is_owner = serializers.SerializerMethodField()
    my_status = serializers.SerializerMethodField()      # None | PENDING | APPROVED
    pending_count = serializers.SerializerMethodField()  # chỉ owner thấy số khác 0

    class Meta:
        model = Group
        fields = [
            'id', 'name', 'description', 'category',
            'created_by', 'created_by_username', 'member_count',
            'is_member', 'is_owner', 'my_status', 'pending_count', 'created_at',
        ]
        read_only_fields = ['created_by', 'created_at']

    def _user(self):
        request = self.context.get('request')
        return request.user if request and request.user.is_authenticated else None

    def get_member_count(self, obj):
        return obj.memberships.filter(status=GroupMembership.Status.APPROVED).count()

    def get_is_owner(self, obj):
        u = self._user()
        return bool(u and obj.created_by_id == u.id)

    def get_my_status(self, obj):
        u = self._user()
        if not u:
            return None
        if obj.created_by_id == u.id:
            return GroupMembership.Status.APPROVED
        m = obj.memberships.filter(user=u).first()
        return m.status if m else None

    def get_is_member(self, obj):
        return self.get_my_status(obj) == GroupMembership.Status.APPROVED

    def get_pending_count(self, obj):
        if not self.get_is_owner(obj):
            return 0
        return obj.memberships.filter(status=GroupMembership.Status.PENDING).count()