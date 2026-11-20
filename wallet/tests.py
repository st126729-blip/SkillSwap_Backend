from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from .models import Wallet, LedgerEntry, add_credit


class WalletCreditTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='test1234')
        self.wallet = Wallet.objects.create(user=self.user)

    def test_wallet_starts_at_zero(self):
        self.assertEqual(self.wallet.balance, Decimal('0'))

    def test_add_credit_increases_balance(self):
        add_credit(self.wallet, 50, 'DEPOSIT', note='Initial deposit')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('50'))

    def test_add_credit_creates_ledger_entry(self):
        add_credit(self.wallet, 50, 'DEPOSIT', note='Initial deposit')
        entry = LedgerEntry.objects.get(wallet=self.wallet)
        self.assertEqual(entry.amount, Decimal('50'))
        self.assertEqual(entry.balance_after, Decimal('50'))
        self.assertEqual(entry.entry_type, 'DEPOSIT')

    def test_negative_amount_decreases_balance(self):
        add_credit(self.wallet, 100, 'DEPOSIT')
        add_credit(self.wallet, -30, 'ESCROW_HOLD')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('70'))

    def test_cannot_go_negative(self):
        add_credit(self.wallet, 10, 'DEPOSIT')
        with self.assertRaises(ValidationError):
            add_credit(self.wallet, -50, 'ESCROW_HOLD')
        self.wallet.refresh_from_db()
        # balance must remain unchanged after a failed operation
        self.assertEqual(self.wallet.balance, Decimal('10'))

    def test_multiple_entries_keep_correct_running_balance(self):
        add_credit(self.wallet, 100, 'DEPOSIT')
        add_credit(self.wallet, -20, 'ESCROW_HOLD')
        add_credit(self.wallet, 5, 'ESCROW_REFUND')
        self.wallet.refresh_from_db()
        self.assertEqual(self.wallet.balance, Decimal('85'))
        self.assertEqual(LedgerEntry.objects.filter(wallet=self.wallet).count(), 3)
import threading
from decimal import Decimal
from django.db import connections
from django.test import TransactionTestCase
from django.contrib.auth.models import User
from .models import Wallet, LedgerEntry, add_credit


class ConcurrentCreditTests(TransactionTestCase):
    """
    TransactionTestCase (not TestCase) is required here: TestCase wraps
    each test in a single transaction, which would make select_for_update()
    locking invisible since there'd only ever be one real transaction.
    TransactionTestCase commits each operation separately, letting us
    simulate genuinely concurrent database transactions across threads.
    """

    def setUp(self):
        self.user = User.objects.create_user(username='racer', password='test1234')
        self.wallet = Wallet.objects.create(user=self.user)
        add_credit(self.wallet, 100, 'DEPOSIT')

    def test_concurrent_deductions_cannot_double_spend(self):
        """
        Two threads each try to deduct 80 credits from a wallet that only
        has 100. Without row-level locking, both could read balance=100,
        both pass the >=0 check, and the wallet would end at -60.
        With select_for_update(), one thread must wait for the other,
        so only one deduction can succeed.
        """
        results = []

        def attempt_deduction():
            try:
                add_credit(self.wallet, -80, 'ESCROW_HOLD')
                results.append('success')
            except Exception:
                results.append('failed')
            finally:
                connections.close_all()  # each thread needs its own DB connection

        t1 = threading.Thread(target=attempt_deduction)
        t2 = threading.Thread(target=attempt_deduction)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one of the two concurrent deductions must succeed.
        self.assertEqual(results.count('success'), 1)
        self.assertEqual(results.count('failed'), 1)

        self.wallet.refresh_from_db()
        # Balance must never go negative, and must reflect exactly one
        # successful deduction, not zero and not two.
        self.assertEqual(self.wallet.balance, Decimal('20'))
        self.assertEqual(
            LedgerEntry.objects.filter(wallet=self.wallet, entry_type='ESCROW_HOLD').count(),
            1,
        )