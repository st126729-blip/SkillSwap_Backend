from rest_framework import viewsets, permissions, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from projects.models import Project
from .models import BuildLogEntry
from .serializers import BuildLogEntrySerializer
from .permissions import IsProjectMemberOrReadOnly


class BuildLogEntryViewSet(viewsets.ModelViewSet):
    queryset = BuildLogEntry.objects.all()
    serializer_class = BuildLogEntrySerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsProjectMemberOrReadOnly]

    def perform_create(self, serializer):
        project = serializer.validated_data['project']
        user = self.request.user
        if not (user.is_staff or project.owner == user or project.collaborator == user):
            raise PermissionDenied("Only project owner or collaborator can post build logs.")
        serializer.save(author=user)