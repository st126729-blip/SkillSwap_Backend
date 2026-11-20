from rest_framework import permissions


class IsGroupMemberOrReadOnly(permissions.BasePermission):
    """Ai cũng xem group/bài đăng được. Chỉ member mới đăng bài trong group."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated