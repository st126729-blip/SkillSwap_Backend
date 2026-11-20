from rest_framework import permissions


class IsTradeParticipant(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.initiator == request.user or obj.recipient == request.user


class IsTradeRecipient(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.recipient == request.user