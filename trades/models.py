from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from wallet.models import Wallet, add_credit


class Trade(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'
        CANCELLED = 'CANCELLED', 'Cancelled'
        COMPLETED = 'COMPLETED', 'Completed'

    initiator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades_sent')
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades_received')

    offer_description = models.TextField()   # e.g. "I'll design a logo"
    request_description = models.TextField() # e.g. "In exchange for landing page code"
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)  # optional credit top-up

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.initiator.username} -> {self.recipient.username} ({self.status})"

    def accept(self):
        """Recipient accepts the trade — credit_amount moves from initiator to recipient."""
        if self.status != self.Status.PENDING:
            raise ValidationError("Trade is not pending.")

        if self.credit_amount > 0:
            initiator_wallet = Wallet.objects.get(user=self.initiator)
            recipient_wallet = Wallet.objects.get(user=self.recipient)

            add_credit(initiator_wallet, -self.credit_amount, 'SWAP_SENT', reference_id=str(self.pk))
            add_credit(recipient_wallet, self.credit_amount, 'SWAP_RECEIVED', reference_id=str(self.pk))

        self.status = self.Status.ACCEPTED
        self.save()

    def reject(self):
        if self.status != self.Status.PENDING:
            raise ValidationError("Trade is not pending.")
        self.status = self.Status.REJECTED
        self.save()

    def cancel(self):
        if self.status != self.Status.PENDING:
            raise ValidationError("Trade is not pending.")
        self.status = self.Status.CANCELLED
        self.save()