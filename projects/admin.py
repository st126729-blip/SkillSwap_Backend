from django.contrib import admin
from django.contrib import messages
from .models import Project, Milestone


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ('title', 'owner', 'collaborator', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'owner__username', 'collaborator__username')


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'project', 'title', 'credit_amount',
        'owner_approved', 'collaborator_approved', 'status',
    )
    list_filter = ('status', 'owner_approved', 'collaborator_approved')
    search_fields = ('project__title', 'title')
    readonly_fields = (
        'owner_approved', 'collaborator_approved', 'status',
        'dispute_reason', 'disputed_by',
        'created_at', 'updated_at',
    )

    actions = [
        'fund_milestones',
        'approve_as_owner',
        'approve_as_collaborator',
        'refund_milestones',
        'dispute_as_owner',
        'dispute_as_collaborator',
        'resolve_dispute_release',
        'resolve_dispute_refund',
    ]

    @admin.action(description='Fund selected milestones (hold credit in escrow)')
    def fund_milestones(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.fund()
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Done funding selected milestones.")

    @admin.action(description="Approve as OWNER")
    def approve_as_owner(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.approve(milestone.project.owner)
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Owner approval processed.")

    @admin.action(description="Approve as COLLABORATOR")
    def approve_as_collaborator(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.approve(milestone.project.collaborator)
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Collaborator approval processed.")

    @admin.action(description='Refund selected milestones')
    def refund_milestones(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.refund()
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Refund processed.")

    @admin.action(description="Raise dispute as OWNER")
    def dispute_as_owner(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.dispute(milestone.project.owner, reason='Test dispute raised by owner via admin')
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Dispute raised by owner.")

    @admin.action(description="Raise dispute as COLLABORATOR")
    def dispute_as_collaborator(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.dispute(milestone.project.collaborator, reason='Test dispute raised by collaborator via admin')
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Dispute raised by collaborator.")

    @admin.action(description="Resolve dispute -> RELEASE to collaborator")
    def resolve_dispute_release(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.resolve_dispute_release()
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Dispute resolved: credit released.")

    @admin.action(description="Resolve dispute -> REFUND to owner")
    def resolve_dispute_refund(self, request, queryset):
        for milestone in queryset:
            try:
                milestone.resolve_dispute_refund()
            except Exception as e:
                self.message_user(request, f"Milestone #{milestone.pk} failed: {e}", level=messages.ERROR)
        self.message_user(request, "Dispute resolved: credit refunded.")