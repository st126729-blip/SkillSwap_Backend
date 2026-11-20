from rest_framework import permissions


class IsProjectMemberOrReadOnly(permissions.BasePermission):
    """Ai cũng xem được (public discovery). Chỉ owner/collaborator/admin mới đăng."""
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_staff:
            return True
        project = obj.project
        return project.owner == request.user or project.collaborator == request.user