from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from wallet.models import Wallet, add_credit
from .models import Trade


class TradeTests(TestCase):
    def setUp(self):
        self.initiator = User.objects.create_user(username='initiator', password='test1234')
        self.recipient = User.objects.create_user(username='recipient', password='test1234')

        self.initiator_wallet = Wallet.objects.create(user=self.initiator)
        self.recipient_wallet = Wallet.objects.create(user=self.recipient)
        add_credit(self.initiator_wallet, 100, 'DEPOSIT')

    def make_trade(self, credit_amount=Decimal('0')):
        return Trade.objects.create(
            initiator=self.initiator,
            recipient=self.recipient,
            offer_description='I will design a logo',
            request_description='In exchange for landing page code',
            credit_amount=credit_amount,
        )

    # ---- Basic creation ----

    def test_trade_starts_pending(self):
        trade = self.make_trade()
        self.assertEqual(trade.status, Trade.Status.PENDING)

    # ---- Accept (with credit) ----

    def test_accept_moves_credit_from_initiator_to_recipient(self):
        trade = self.make_trade(credit_amount=Decimal('20'))
        trade.accept()

        self.initiator_wallet.refresh_from_db()
        self.recipient_wallet.refresh_from_db()
        trade.refresh_from_db()

        self.assertEqual(self.initiator_wallet.balance, Decimal('80'))
        self.assertEqual(self.recipient_wallet.balance, Decimal('20'))
        self.assertEqual(trade.status, Trade.Status.ACCEPTED)

    def test_accept_with_zero_credit_does_not_move_credit(self):
        trade = self.make_trade(credit_amount=Decimal('0'))
        trade.accept()

        self.initiator_wallet.refresh_from_db()
        self.recipient_wallet.refresh_from_db()

        self.assertEqual(self.initiator_wallet.balance, Decimal('100'))  # unchanged
        self.assertEqual(self.recipient_wallet.balance, Decimal('0'))

    def test_cannot_accept_with_insufficient_balance(self):
        trade = self.make_trade(credit_amount=Decimal('9999'))
        with self.assertRaises(ValidationError):
            trade.accept()
        trade.refresh_from_db()
        self.assertEqual(trade.status, Trade.Status.PENDING)  # unchanged on failure

    def test_cannot_accept_twice(self):
        trade = self.make_trade(credit_amount=Decimal('10'))
        trade.accept()
        with self.assertRaises(ValidationError):
            trade.accept()

    # ---- Reject ----

    def test_reject_changes_status_and_moves_no_credit(self):
        trade = self.make_trade(credit_amount=Decimal('20'))
        trade.reject()

        self.initiator_wallet.refresh_from_db()
        trade.refresh_from_db()

        self.assertEqual(trade.status, Trade.Status.REJECTED)
        self.assertEqual(self.initiator_wallet.balance, Decimal('100'))  # unchanged

    def test_cannot_reject_already_accepted_trade(self):
        trade = self.make_trade(credit_amount=Decimal('10'))
        trade.accept()
        with self.assertRaises(ValidationError):
            trade.reject()

    # ---- Cancel ----

    def test_cancel_changes_status_and_moves_no_credit(self):
        trade = self.make_trade(credit_amount=Decimal('20'))
        trade.cancel()

        self.initiator_wallet.refresh_from_db()
        trade.refresh_from_db()

        self.assertEqual(trade.status, Trade.Status.CANCELLED)
        self.assertEqual(self.initiator_wallet.balance, Decimal('100'))

    def test_cannot_cancel_already_rejected_trade(self):
        trade = self.make_trade()
        trade.reject()
        with self.assertRaises(ValidationError):
            trade.cancel()

    # ---- Conservation of credit ----

    def test_total_credit_conserved_after_accept(self):
        self.initiator_wallet.refresh_from_db()
        self.recipient_wallet.refresh_from_db()
        total_before = self.initiator_wallet.balance + self.recipient_wallet.balance

        trade = self.make_trade(credit_amount=Decimal('30'))
        trade.accept()

        self.initiator_wallet.refresh_from_db()
        self.recipient_wallet.refresh_from_db()
        total_after = self.initiator_wallet.balance + self.recipient_wallet.balance

        self.assertEqual(total_before, total_after)