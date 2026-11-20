from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.balance} credits"


class LedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        DEPOSIT = 'DEPOSIT', 'Deposit'
        SIGNUP_BONUS = 'SIGNUP_BONUS', 'Signup Bonus'
        SWAP_SENT = 'SWAP_SENT', 'Swap Sent'
        SWAP_RECEIVED = 'SWAP_RECEIVED', 'Swap Received'
        ESCROW_HOLD = 'ESCROW_HOLD', 'Escrow Hold'
        ESCROW_RELEASE = 'ESCROW_RELEASE', 'Escrow Release'
        ESCROW_REFUND = 'ESCROW_REFUND', 'Escrow Refund'

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name='entries')
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)  # dương = cộng, âm = trừ
    balance_after = models.DecimalField(max_digits=12, decimal_places=2)  # snapshot sau giao dịch
    reference_id = models.CharField(max_length=100, blank=True)  # id Trade/Milestone liên quan
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.wallet.user.username} | {self.entry_type} | {self.amount}"


def add_credit(wallet: Wallet, amount, entry_type, reference_id='', note=''):
    """
    Cộng/trừ credit an toàn.
    amount dương = cộng, amount âm = trừ.
    Dùng select_for_update() để khóa dòng, tránh double-spending khi có
    nhiều request cùng lúc thao tác trên cùng 1 wallet.
    """
    with transaction.atomic():
        locked_wallet = Wallet.objects.select_for_update().get(pk=wallet.pk)
        new_balance = locked_wallet.balance + amount

        if new_balance < 0:
            raise ValidationError("Insufficient credit balance.")

        locked_wallet.balance = new_balance
        locked_wallet.save()

        LedgerEntry.objects.create(
            wallet=locked_wallet,
            entry_type=entry_type,
            amount=amount,
            balance_after=new_balance,
            reference_id=reference_id,
            note=note,
        )
        return locked_wallet