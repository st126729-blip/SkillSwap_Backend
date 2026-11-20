from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError as DRFValidationError
from rest_framework.response import Response
from django.db.models import Q
from .models import Project, Milestone
from .serializers import ProjectSerializer, MilestoneSerializer
from .permissions import IsProjectOwnerOrCollaborator, IsProjectOwner, IsProjectCollaborator


class ProjectViewSet(viewsets.ModelViewSet):
    serializer_class = ProjectSerializer

    def get_permissions(self):
        # Edit / delete: owner only. View: owner or collaborator.
        if self.action in ('update', 'partial_update', 'destroy'):
            return [permissions.IsAuthenticated(), IsProjectOwner()]
        return [permissions.IsAuthenticated(), IsProjectOwnerOrCollaborator()]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Project.objects.all()
        return Project.objects.filter(Q(owner=user) | Q(collaborator=user))

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        if serializer.instance.owner != self.request.user:
            raise PermissionDenied("Only the project owner can edit this project.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.owner != self.request.user:
            raise PermissionDenied("Only the project owner can delete this project.")
        # Deleting a project deletes its milestones, which would lose escrowed credit
        locked = instance.milestones.filter(
            status__in=[Milestone.Status.FUNDED, Milestone.Status.DISPUTED]
        ).exists()
        if locked:
            raise DRFValidationError(
                "This project has funded or disputed milestones. "
                "Cancel or resolve them before deleting the project."
            )
        instance.delete()


class MilestoneViewSet(viewsets.ModelViewSet):
    serializer_class = MilestoneSerializer
    permission_classes = [permissions.IsAuthenticated, IsProjectOwnerOrCollaborator]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Milestone.objects.all()
        return Milestone.objects.filter(Q(project__owner=user) | Q(project__collaborator=user))

    # ---- CRUD guards (object permissions do not run on create) ----

    def perform_create(self, serializer):
        project = serializer.validated_data['project']
        user = self.request.user
        if user != project.owner and user != project.collaborator:
            raise PermissionDenied("Only the owner or the collaborator of this project can add milestones.")
        assignee = serializer.validated_data.get('assignee') or project.collaborator
        serializer.save(created_by=user, assignee=assignee)

    def perform_update(self, serializer):
        instance = serializer.instance
        if instance.status != Milestone.Status.PENDING:
            raise DRFValidationError("A milestone can only be edited while it is PENDING.")
        if self.request.user != instance.creator:
            raise PermissionDenied("Only the person who created this milestone can edit it.")
        new_project = serializer.validated_data.get('project')
        if new_project and new_project != instance.project:
            raise DRFValidationError("A milestone cannot be moved to another project.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.status != Milestone.Status.PENDING:
            raise DRFValidationError("Only a PENDING milestone can be deleted.")
        if self.request.user != instance.creator:
            raise PermissionDenied("Only the person who created this milestone can delete it.")
        instance.delete()

    # ---- Escrow actions (the model checks who may do what) ----

    def _run(self, request, method_name, *args):
        milestone = self.get_object()
        try:
            getattr(milestone, method_name)(*args)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(MilestoneSerializer(milestone).data)

    @action(detail=True, methods=['post'],
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def fund(self, request, pk=None):
        return self._run(request, 'fund', request.user, request.data.get('credit_amount'))

    @action(detail=True, methods=['post'],
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def reject(self, request, pk=None):
        return self._run(request, 'reject', request.user, request.data.get('reason', ''))

    @action(detail=True, methods=['post'], url_path='approve-owner',
            permission_classes=[permissions.IsAuthenticated, IsProjectOwner])
    def approve_owner(self, request, pk=None):
        return self._run(request, 'approve', request.user)

    @action(detail=True, methods=['post'], url_path='approve-collaborator',
            permission_classes=[permissions.IsAuthenticated, IsProjectCollaborator])
    def approve_collaborator(self, request, pk=None):
        return self._run(request, 'approve', request.user)

    @action(detail=True, methods=['post'],
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def submit(self, request, pk=None):
        return self._run(
            request, 'submit_work', request.user,
            request.data.get('note', ''), request.data.get('url', ''),
        )

    @action(detail=True, methods=['post'], url_path='cancel',
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def cancel(self, request, pk=None):
        return self._run(request, 'request_cancel', request.user)

    @action(detail=True, methods=['post'], url_path='finalize-cancel',
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def finalize_cancel(self, request, pk=None):
        return self._run(request, 'finalize_cancel', request.user)

    # ---- Dispute actions ----

    @action(detail=True, methods=['post'],
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def dispute(self, request, pk=None):
        return self._run(request, 'dispute', request.user, request.data.get('reason', ''))

    @action(detail=True, methods=['post'], url_path='respond-dispute',
            permission_classes=[permissions.IsAuthenticated, IsProjectOwnerOrCollaborator])
    def respond_dispute(self, request, pk=None):
        return self._run(request, 'respond_dispute', request.user, request.data.get('response', ''))

    @action(detail=True, methods=['post'], url_path='resolve-dispute-release',
            permission_classes=[permissions.IsAuthenticated])
    def resolve_dispute_release(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Only staff can resolve disputes.'}, status=status.HTTP_403_FORBIDDEN)
        return self._run(request, 'resolve_dispute_release')

    @action(detail=True, methods=['post'], url_path='resolve-dispute-refund',
            permission_classes=[permissions.IsAuthenticated])
    def resolve_dispute_refund(self, request, pk=None):
        if not request.user.is_staff:
            return Response({'detail': 'Only staff can resolve disputes.'}, status=status.HTTP_403_FORBIDDEN)
        return self._run(request, 'resolve_dispute_refund')