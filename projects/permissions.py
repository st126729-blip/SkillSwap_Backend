from rest_framework import permissions

class IsProjectOwnerOrCollaborator(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        project = obj if hasattr(obj, 'owner') else obj.project
        return project.owner == request.user or project.collaborator == request.user

class IsProjectOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        project = obj if hasattr(obj, 'owner') else obj.project
        return project.owner == request.user

class IsProjectCollaborator(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        project = obj if hasattr(obj, 'owner') else obj.project
        return project.collaborator == request.user