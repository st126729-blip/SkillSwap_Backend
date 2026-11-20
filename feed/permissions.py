from rest_framework import permissions


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Ai cũng xem được, chỉ tác giả (hoặc admin) mới sửa/xóa."""
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        author = obj.author if hasattr(obj, 'author') else obj.user
        return author == request.user