from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from wallet.models import Wallet, add_credit

# Time the worker has to dispute after the receiver asks to cancel.
# Use timedelta(minutes=1) when demoing the "Finalize refund" step.
CANCEL_WINDOW = timedelta(hours=48)


class Project(models.Model):
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_projects')
    collaborator = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='collaborating_projects',
        null=True, blank=True,
    )  # null until someone applies and gets accepted

    title = models.CharField(max_length=200)
    description = models.TextField()
    roles_needed = models.TextField(blank=True)  # simple text list for now

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.status})"


class Milestone(models.Model):
    """
    Each milestone has two roles:
      - worker   (assignee): does the work and earns the credit
      - receiver (the other party): receives the work, funds the escrow
    Old milestones without an assignee behave as before:
    collaborator = worker, owner = receiver.
    """

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        FUNDED = 'FUNDED', 'Funded'
        RELEASED = 'RELEASED', 'Released'
        REFUNDED = 'REFUNDED', 'Refunded'
        DISPUTED = 'DISPUTED', 'Disputed'
        REJECTED = 'REJECTED', 'Rejected'

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='milestones')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(null=True, blank=True)  # deadline for the worker to deliver

    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='created_milestones',
    )
    assignee = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_milestones',
    )

    owner_approved = models.BooleanField(default=False)
    collaborator_approved = models.BooleanField(default=False)

    submission_note = models.TextField(blank=True)
    submission_url = models.URLField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    # Receiver asked to cancel; credit stays in escrow until the window ends
    cancel_requested_at = models.DateTimeField(null=True, blank=True)

    reject_reason = models.TextField(blank=True)

    dispute_reason = models.TextField(blank=True)
    dispute_response = models.TextField(blank=True)  # reason from the other party
    disputed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='disputed_milestones',
    )

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.project.title} - {self.title} ({self.status})"

    # ---- Roles ----

    @property
    def creator(self):
        return self.created_by or self.project.owner

    @property
    def worker(self):
        return self.assignee or self.project.collaborator

    @property
    def receiver(self):
        worker = self.worker
        if worker == self.project.owner:
            return self.project.collaborator
        return self.project.owner

    @property
    def cancel_available_at(self):
        if not self.cancel_requested_at:
            return None
        return self.cancel_requested_at + CANCEL_WINDOW

    # ---- Escrow actions ----

    def fund(self, by_user: User, expected_amount=None):
        if self.status != self.Status.PENDING:
            raise ValidationError("Milestone is not in PENDING state.")
        if not self.project.collaborator:
            raise ValidationError("Project has no assigned collaborator yet.")
        if by_user != self.receiver:
            raise ValidationError("Only the person who receives this work can fund it.")

        # Protects against the price being changed right before funding
        if expected_amount is not None:
            try:
                expected = Decimal(str(expected_amount))
            except InvalidOperation:
                raise ValidationError("Invalid credit amount.")
            if expected != self.credit_amount:
                raise ValidationError("The credit amount has changed. Reload and review it before funding.")

        with transaction.atomic():
            receiver_wallet = Wallet.objects.get(user=self.receiver)
            add_credit(
                receiver_wallet, -self.credit_amount, 'ESCROW_HOLD',
                reference_id=f"milestone-{self.pk}",
                note=f"Escrow hold for milestone '{self.title}'",
            )
            self.status = self.Status.FUNDED
            self.save()

    def reject(self, by_user: User, reason: str = ''):
        if self.status != self.Status.PENDING:
            raise ValidationError("Only a PENDING milestone can be rejected.")
        if by_user not in (self.project.owner, self.project.collaborator):
            raise ValidationError("Only the owner or the collaborator can reject a milestone.")
        if by_user == self.creator:
            raise ValidationError("You created this milestone. Delete it instead of rejecting it.")
        if not reason or not reason.strip():
            raise ValidationError("Please tell the other person why (for example the credit is too high).")

        self.status = self.Status.REJECTED
        self.reject_reason = reason.strip()
        self.save()

    def submit_work(self, by_user: User, note='', url=''):
        if self.status != self.Status.FUNDED:
            raise ValidationError("Work can only be submitted while the milestone is FUNDED.")
        if by_user != self.worker:
            raise ValidationError("Only the person assigned to this milestone can submit work.")
        if self.cancel_requested_at:
            raise ValidationError(
                "Cancellation has been requested. Raise a dispute if you disagree, or wait for it to finish."
            )
        if not note and not url:
            raise ValidationError("Submission must include a note or a URL.")

        self.submission_note = note
        self.submission_url = url
        self.submitted_at = timezone.now()
        self.save()

    def approve(self, by_user: User):
        if self.status != self.Status.FUNDED:
            raise ValidationError("Milestone must be FUNDED before approval.")

        if by_user == self.project.owner:
            self.owner_approved = True
        elif by_user == self.project.collaborator:
            self.collaborator_approved = True
        else:
            raise ValidationError("Only the project owner or collaborator can approve.")

        self.save()

        if self.owner_approved and self.collaborator_approved:
            self._release()

    def _release(self):
        with transaction.atomic():
            worker_wallet = Wallet.objects.get(user=self.worker)
            add_credit(
                worker_wallet, self.credit_amount, 'ESCROW_RELEASE',
                reference_id=f"milestone-{self.pk}",
                note=f"Escrow release for milestone '{self.title}'",
            )
            self.status = self.Status.RELEASED
            self.save()

    def _refund_internal(self):
        with transaction.atomic():
            receiver_wallet = Wallet.objects.get(user=self.receiver)
            add_credit(
                receiver_wallet, self.credit_amount, 'ESCROW_REFUND',
                reference_id=f"milestone-{self.pk}",
                note=f"Escrow refund for milestone '{self.title}'",
            )
            self.status = self.Status.REFUNDED
            self.save()

    # ---- Cancellation (receiver can always ask; worker can object via dispute) ----

    def request_cancel(self, by_user: User):
        if self.status != self.Status.FUNDED:
            raise ValidationError("Only a FUNDED milestone can be cancelled.")
        if by_user != self.receiver:
            raise ValidationError("Only the person who funded this milestone can cancel it.")
        if self.cancel_requested_at:
            raise ValidationError("Cancellation has already been requested.")

        # Credit stays in escrow: the worker gets a window to dispute first
        self.cancel_requested_at = timezone.now()
        self.save()

    def finalize_cancel(self, by_user: User):
        if self.status != self.Status.FUNDED:
            raise ValidationError("This milestone is not FUNDED any more (it may be disputed).")
        if by_user != self.receiver:
            raise ValidationError("Only the person who funded this milestone can finalize the cancellation.")
        if not self.cancel_requested_at:
            raise ValidationError("Request cancellation first.")
        if timezone.now() < self.cancel_available_at:
            raise ValidationError(
                f"The other person can still dispute until {self.cancel_available_at:%Y-%m-%d %H:%M} UTC."
            )
        self._refund_internal()

    # ---- Dispute actions ----

    def dispute(self, by_user: User, reason: str):
        if self.status != self.Status.FUNDED:
            raise ValidationError("Only a FUNDED milestone can be disputed.")
        if by_user not in (self.project.owner, self.project.collaborator):
            raise ValidationError("Only the project owner or collaborator can raise a dispute.")
        # The one who asked to cancel cannot skip the objection window by disputing
        if self.cancel_requested_at and by_user == self.receiver:
            raise ValidationError("You requested the cancellation. Wait for the window to end, then finalize it.")
        if not reason or not reason.strip():
            raise ValidationError("Please provide a reason for the dispute.")

        self.status = self.Status.DISPUTED
        self.dispute_reason = reason.strip()
        self.disputed_by = by_user
        self.save()

    def respond_dispute(self, by_user: User, response: str):
        if self.status != self.Status.DISPUTED:
            raise ValidationError("Milestone is not under dispute.")
        if by_user not in (self.project.owner, self.project.collaborator):
            raise ValidationError("Only the project owner or collaborator can respond.")
        if by_user == self.disputed_by:
            raise ValidationError("You opened this dispute. Only the other party can respond.")
        if self.dispute_response:
            raise ValidationError("A response has already been submitted.")
        if not response or not response.strip():
            raise ValidationError("Please provide a response.")

        self.dispute_response = response.strip()
        self.save()

    def resolve_dispute_release(self):
        if self.status != self.Status.DISPUTED:
            raise ValidationError("Milestone is not under dispute.")
        self._release()

    def resolve_dispute_refund(self):
        if self.status != self.Status.DISPUTED:
            raise ValidationError("Milestone is not under dispute.")
        self._refund_internal()