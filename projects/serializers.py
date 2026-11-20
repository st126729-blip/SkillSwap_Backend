from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework import serializers
from .models import Project, Milestone, CANCEL_WINDOW

User = get_user_model()


class MilestoneSerializer(serializers.ModelSerializer):
    cancel_available_at = serializers.DateTimeField(read_only=True)
    cancel_window_minutes = serializers.SerializerMethodField()

    creator = serializers.SerializerMethodField()
    creator_username = serializers.SerializerMethodField()
    worker = serializers.SerializerMethodField()
    worker_username = serializers.SerializerMethodField()
    receiver = serializers.SerializerMethodField()
    receiver_username = serializers.SerializerMethodField()

    class Meta:
        model = Milestone
        fields = [
            'id', 'project', 'title', 'description', 'credit_amount', 'due_date', 'status',
            'created_by', 'creator', 'creator_username',
            'assignee', 'worker', 'worker_username', 'receiver', 'receiver_username',
            'owner_approved', 'collaborator_approved',
            'submission_note', 'submission_url', 'submitted_at',
            'cancel_requested_at', 'cancel_available_at', 'cancel_window_minutes',
            'reject_reason',
            'dispute_reason', 'dispute_response', 'disputed_by',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'status', 'created_by', 'owner_approved', 'collaborator_approved',
            'submission_note', 'submission_url', 'submitted_at',
            'cancel_requested_at', 'reject_reason',
            'dispute_reason', 'dispute_response', 'disputed_by',
            'created_at', 'updated_at',
        ]
        extra_kwargs = {
            'description': {'required': True, 'allow_blank': False},
            'assignee': {'required': False, 'allow_null': True},
        }

    # ---- computed fields ----

    def get_cancel_window_minutes(self, obj):
        return int(CANCEL_WINDOW.total_seconds() // 60)

    def get_creator(self, obj):
        return obj.creator.id if obj.creator else None

    def get_creator_username(self, obj):
        return obj.creator.username if obj.creator else None

    def get_worker(self, obj):
        return obj.worker.id if obj.worker else None

    def get_worker_username(self, obj):
        return obj.worker.username if obj.worker else None

    def get_receiver(self, obj):
        return obj.receiver.id if obj.receiver else None

    def get_receiver_username(self, obj):
        return obj.receiver.username if obj.receiver else None

    # ---- validation ----

    def validate(self, attrs):
        project = attrs.get('project') or getattr(self.instance, 'project', None)
        assignee = attrs.get('assignee')
        if assignee and project and assignee not in (project.owner, project.collaborator):
            raise serializers.ValidationError(
                {'assignee': 'The person doing the work must be the owner or the collaborator of this project.'}
            )
        return attrs

    def validate_due_date(self, value):
        if value and value < timezone.localdate():
            raise serializers.ValidationError("Due date cannot be in the past.")
        return value

    def validate_credit_amount(self, value):
        if value is not None and value <= 0:
            raise serializers.ValidationError("Credit must be greater than 0.")
        return value


class ProjectSerializer(serializers.ModelSerializer):
    owner_username = serializers.CharField(source='owner.username', read_only=True)
    collaborator_username = serializers.CharField(source='collaborator.username', read_only=True)
    # Ghi-only: gõ username để gán collaborator
    assign_collaborator = serializers.CharField(write_only=True, required=False)
    milestones = MilestoneSerializer(many=True, read_only=True)  # matches related_name='milestones'

    class Meta:
        model = Project
        fields = [
            'id', 'title', 'description', 'roles_needed', 'status',
            'owner', 'owner_username', 'collaborator', 'collaborator_username',
            'assign_collaborator',
            'milestones', 'created_at',
        ]
        read_only_fields = ['owner', 'created_at']

    def validate_assign_collaborator(self, value):
        try:
            user = User.objects.get(username=value.strip())
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Không tìm thấy user '{value}'.")
        owner = getattr(self.instance, 'owner', None)
        if owner and user == owner:
            raise serializers.ValidationError("Owner không thể tự làm collaborator.")
        return user

    def create(self, validated_data):
        validated_data.pop('assign_collaborator', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        user = validated_data.pop('assign_collaborator', None)
        if user:
            instance.collaborator = user
        return super().update(instance, validated_data)