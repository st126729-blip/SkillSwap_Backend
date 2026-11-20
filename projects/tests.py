from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status as http_status

from wallet.models import Wallet, add_credit, LedgerEntry
from .models import Project, Milestone


class MilestoneEscrowTests(TestCase):
    """Model-level tests. Default roles (no assignee):
    worker = collaborator (earns credit), receiver = owner (funds escrow)."""

    def setUp(self):
        self.owner = User.objects.create_user(username='owner', password='test1234')
        self.collaborator = User.objects.create_user(username='collab', password='test1234')

        self.owner_wallet = Wallet.objects.create(user=self.owner)
        self.collaborator_wallet = Wallet.objects.create(user=self.collaborator)
        add_credit(self.owner_wallet, 100, 'DEPOSIT')

        self.project = Project.objects.create(
            owner=self.owner,
            collaborator=self.collaborator,
            title='Test Project',
            description='Test',
        )
        self.milestone = Milestone.objects.create(
            project=self.project,
            title='Test Milestone',
            credit_amount=Decimal('20'),
        )

    # ---- helpers ----

    def balance(self, wallet):
        wallet.refresh_from_db()
        return wallet.balance

    def backdate_cancel(self, hours=49):
        """Pretend the cancel request was made `hours` ago (window is 48h)."""
        self.milestone.cancel_requested_at = timezone.now() - timedelta(hours=hours)
        self.milestone.save()

    # ---- Funding ----

    def test_fund_moves_credit_into_escrow(self):
        self.milestone.fund(self.owner)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('80'))
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)

    def test_cannot_fund_twice(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.fund(self.owner)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('80'))  # charged once only

    def test_cannot_fund_without_collaborator(self):
        self.project.collaborator = None
        self.project.save()
        with self.assertRaises(ValidationError):
            self.milestone.fund(self.owner)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('100'))

    def test_cannot_fund_with_insufficient_balance(self):
        expensive_milestone = Milestone.objects.create(
            project=self.project, title='Expensive', credit_amount=Decimal('9999'),
        )
        with self.assertRaises(ValidationError):
            expensive_milestone.fund(self.owner)
        expensive_milestone.refresh_from_db()
        self.assertEqual(expensive_milestone.status, Milestone.Status.PENDING)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('100'))

    def test_worker_cannot_fund_own_milestone(self):
        # Only the receiver (owner here) may fund; the collaborator is the worker.
        with self.assertRaises(ValidationError):
            self.milestone.fund(self.collaborator)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.PENDING)

    def test_stranger_cannot_fund(self):
        stranger = User.objects.create_user(username='stranger_f', password='test1234')
        with self.assertRaises(ValidationError):
            self.milestone.fund(stranger)

    def test_fund_with_matching_expected_amount_succeeds(self):
        self.milestone.fund(self.owner, expected_amount='20.00')
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)

    def test_fund_with_changed_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.milestone.fund(self.owner, expected_amount='25')
        self.assertEqual(self.balance(self.owner_wallet), Decimal('100'))

    def test_fund_with_invalid_expected_amount_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.milestone.fund(self.owner, expected_amount='abc')

    # ---- Approval / release (the core "atomic" requirement) ----

    def test_single_approval_does_not_release_credit(self):
        self.milestone.fund(self.owner)
        self.milestone.approve(self.owner)

        self.milestone.refresh_from_db()

        self.assertTrue(self.milestone.owner_approved)
        self.assertFalse(self.milestone.collaborator_approved)
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)  # not released yet
        self.assertEqual(self.balance(self.collaborator_wallet), Decimal('0'))  # no credit moved

    def test_both_approvals_release_credit(self):
        self.milestone.fund(self.owner)
        self.milestone.approve(self.owner)
        self.milestone.approve(self.collaborator)

        self.milestone.refresh_from_db()

        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)
        self.assertEqual(self.balance(self.collaborator_wallet), Decimal('20'))

    def test_approval_order_does_not_matter(self):
        self.milestone.fund(self.owner)
        self.milestone.approve(self.collaborator)
        self.milestone.approve(self.owner)

        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)

    def test_cannot_approve_before_funding(self):
        with self.assertRaises(ValidationError):
            self.milestone.approve(self.owner)

    def test_stranger_cannot_approve(self):
        stranger = User.objects.create_user(username='stranger', password='test1234')
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.approve(stranger)

    # ---- Reject (only while PENDING, only by the non-creator) ----

    def test_other_party_can_reject_pending_milestone(self):
        # created_by is None, so the creator defaults to the project owner;
        # the collaborator is therefore the one who may reject.
        self.milestone.reject(self.collaborator, reason='Credit is too high')
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.REJECTED)
        self.assertEqual(self.milestone.reject_reason, 'Credit is too high')

    def test_creator_cannot_reject_own_milestone(self):
        with self.assertRaises(ValidationError):
            self.milestone.reject(self.owner, reason='Changed my mind')

    def test_reject_requires_reason(self):
        with self.assertRaises(ValidationError):
            self.milestone.reject(self.collaborator, reason='   ')

    def test_stranger_cannot_reject(self):
        stranger = User.objects.create_user(username='stranger_r', password='test1234')
        with self.assertRaises(ValidationError):
            self.milestone.reject(stranger, reason='Nope')

    def test_cannot_reject_funded_milestone(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.reject(self.collaborator, reason='Too late')

    # ---- Cancel + refund (receiver asks, worker gets a 48h window to object) ----

    def test_cancel_then_finalize_after_window_refunds_credit(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('80'))  # still in escrow

        self.backdate_cancel()
        self.milestone.finalize_cancel(self.owner)

        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.REFUNDED)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('100'))  # back to original

    def test_cannot_finalize_cancel_inside_window(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.finalize_cancel(self.owner)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('80'))

    def test_cannot_finalize_without_requesting_cancel(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.finalize_cancel(self.owner)

    def test_cannot_request_cancel_twice(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.request_cancel(self.owner)

    def test_worker_cannot_request_cancel(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.request_cancel(self.collaborator)

    def test_only_receiver_can_finalize_cancel(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        self.backdate_cancel()
        with self.assertRaises(ValidationError):
            self.milestone.finalize_cancel(self.collaborator)

    def test_cannot_cancel_unfunded_milestone(self):
        with self.assertRaises(ValidationError):
            self.milestone.request_cancel(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.finalize_cancel(self.owner)

    def test_cannot_cancel_already_released_milestone(self):
        self.milestone.fund(self.owner)
        self.milestone.approve(self.owner)
        self.milestone.approve(self.collaborator)
        with self.assertRaises(ValidationError):
            self.milestone.request_cancel(self.owner)

    def test_worker_can_dispute_during_cancel_window(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        self.milestone.dispute(self.collaborator, reason='I already did the work')

        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.DISPUTED)

        # the dispute freezes the milestone: cancellation can no longer be finalized
        self.backdate_cancel()
        with self.assertRaises(ValidationError):
            self.milestone.finalize_cancel(self.owner)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('80'))

    def test_receiver_cannot_dispute_to_skip_cancel_window(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.dispute(self.owner, reason='Skip the wait')

    # ---- Dispute ----

    def test_dispute_freezes_milestone(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.owner, reason='Work not delivered')

        self.milestone.refresh_from_db()

        self.assertEqual(self.milestone.status, Milestone.Status.DISPUTED)
        self.assertEqual(self.milestone.disputed_by, self.owner)
        self.assertEqual(self.balance(self.collaborator_wallet), Decimal('0'))  # frozen, not moved

    def test_cannot_dispute_unfunded_milestone(self):
        with self.assertRaises(ValidationError):
            self.milestone.dispute(self.owner, reason='Too early')

    def test_stranger_cannot_dispute(self):
        stranger = User.objects.create_user(username='stranger2', password='test1234')
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.dispute(stranger, reason='Not involved')

    def test_dispute_requires_reason(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.dispute(self.owner, reason='  ')

    def test_other_party_can_respond_to_dispute(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.owner, reason='Work not delivered')
        self.milestone.respond_dispute(self.collaborator, 'I delivered on Monday')
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.dispute_response, 'I delivered on Monday')

    def test_dispute_opener_cannot_respond_to_own_dispute(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.owner, reason='Work not delivered')
        with self.assertRaises(ValidationError):
            self.milestone.respond_dispute(self.owner, 'Talking to myself')

    def test_cannot_respond_twice(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.owner, reason='Work not delivered')
        self.milestone.respond_dispute(self.collaborator, 'First answer')
        with self.assertRaises(ValidationError):
            self.milestone.respond_dispute(self.collaborator, 'Second answer')

    def test_cannot_respond_when_not_disputed(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.respond_dispute(self.collaborator, 'Nothing to answer')

    def test_resolve_dispute_release(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.owner, reason='Disagreement')
        self.milestone.resolve_dispute_release()

        self.milestone.refresh_from_db()

        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)
        self.assertEqual(self.balance(self.collaborator_wallet), Decimal('20'))

    def test_resolve_dispute_refund(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.collaborator, reason='Cannot deliver')
        self.milestone.resolve_dispute_refund()

        self.milestone.refresh_from_db()

        self.assertEqual(self.milestone.status, Milestone.Status.REFUNDED)
        self.assertEqual(self.balance(self.owner_wallet), Decimal('100'))

    def test_cannot_resolve_dispute_on_non_disputed_milestone(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.resolve_dispute_release()
        with self.assertRaises(ValidationError):
            self.milestone.resolve_dispute_refund()

    def test_cannot_resolve_dispute_twice(self):
        self.milestone.fund(self.owner)
        self.milestone.dispute(self.owner, reason='Disagreement')
        self.milestone.resolve_dispute_release()
        with self.assertRaises(ValidationError):
            self.milestone.resolve_dispute_refund()
        self.assertEqual(self.balance(self.collaborator_wallet), Decimal('20'))
        self.assertEqual(self.balance(self.owner_wallet), Decimal('80'))  # no double payout

    # ---- Conservation of credit (key invariant) ----

    def test_total_credit_is_conserved_through_release(self):
        total_before = self.balance(self.owner_wallet) + self.balance(self.collaborator_wallet)

        self.milestone.fund(self.owner)
        self.milestone.approve(self.owner)
        self.milestone.approve(self.collaborator)

        total_after = self.balance(self.owner_wallet) + self.balance(self.collaborator_wallet)
        self.assertEqual(total_before, total_after)

    def test_total_credit_is_conserved_through_refund(self):
        total_before = self.balance(self.owner_wallet) + self.balance(self.collaborator_wallet)

        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        self.backdate_cancel()
        self.milestone.finalize_cancel(self.owner)

        total_after = self.balance(self.owner_wallet) + self.balance(self.collaborator_wallet)
        self.assertEqual(total_before, total_after)

    def test_cannot_release_twice_even_if_release_called_directly(self):
        """approve() already guards against re-release once status != FUNDED;
        this test documents and locks in that protection."""
        self.milestone.fund(self.owner)
        self.milestone.approve(self.owner)
        self.milestone.approve(self.collaborator)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)

        balance_after_first_release = self.balance(self.collaborator_wallet)

        # A retried/duplicate approval request must be rejected outright,
        # not silently no-op: this is the correct, safer behavior.
        with self.assertRaises(ValidationError):
            self.milestone.approve(self.owner)

        self.assertEqual(self.balance(self.collaborator_wallet), balance_after_first_release)
        self.assertEqual(
            LedgerEntry.objects.filter(
                wallet=self.collaborator_wallet, entry_type='ESCROW_RELEASE'
            ).count(),
            1,  # exactly one release entry, never two
        )

    # ---- Submitting work ----

    def test_collaborator_can_submit_work(self):
        self.milestone.fund(self.owner)
        self.milestone.submit_work(self.collaborator, note='Done', url='https://github.com/x/pr/1')
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.submission_note, 'Done')
        self.assertEqual(self.milestone.submission_url, 'https://github.com/x/pr/1')
        self.assertIsNotNone(self.milestone.submitted_at)
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)

    def test_owner_cannot_submit_work(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.submit_work(self.owner, note='Sneaky')

    def test_cannot_submit_work_before_funding(self):
        with self.assertRaises(ValidationError):
            self.milestone.submit_work(self.collaborator, note='Too early')

    def test_cannot_submit_empty_work(self):
        self.milestone.fund(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.submit_work(self.collaborator)

    def test_cannot_submit_work_after_cancel_requested(self):
        self.milestone.fund(self.owner)
        self.milestone.request_cancel(self.owner)
        with self.assertRaises(ValidationError):
            self.milestone.submit_work(self.collaborator, note='Last minute')


class MilestoneAssigneeRolesTests(TestCase):
    """When the OWNER is assigned as the worker, the roles flip:
    the collaborator becomes the receiver who funds the escrow."""

    def setUp(self):
        self.owner = User.objects.create_user(username='r_owner', password='test1234')
        self.collaborator = User.objects.create_user(username='r_collab', password='test1234')
        self.owner_wallet = Wallet.objects.create(user=self.owner)
        self.collaborator_wallet = Wallet.objects.create(user=self.collaborator)
        add_credit(self.collaborator_wallet, 50, 'DEPOSIT')  # the receiver pays

        self.project = Project.objects.create(
            owner=self.owner, collaborator=self.collaborator,
            title='Reverse Roles', description='...',
        )
        self.milestone = Milestone.objects.create(
            project=self.project, title='Owner does the work',
            credit_amount=Decimal('20'), assignee=self.owner,
        )

    def test_roles_are_flipped(self):
        self.assertEqual(self.milestone.worker, self.owner)
        self.assertEqual(self.milestone.receiver, self.collaborator)

    def test_only_collaborator_can_fund(self):
        with self.assertRaises(ValidationError):
            self.milestone.fund(self.owner)
        self.milestone.fund(self.collaborator)
        self.collaborator_wallet.refresh_from_db()
        self.assertEqual(self.collaborator_wallet.balance, Decimal('30'))

    def test_release_pays_the_assigned_worker(self):
        self.milestone.fund(self.collaborator)
        self.milestone.approve(self.owner)
        self.milestone.approve(self.collaborator)

        self.owner_wallet.refresh_from_db()
        self.collaborator_wallet.refresh_from_db()
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)
        self.assertEqual(self.owner_wallet.balance, Decimal('20'))
        self.assertEqual(self.collaborator_wallet.balance, Decimal('30'))

    def test_owner_submits_work_and_collaborator_cannot(self):
        self.milestone.fund(self.collaborator)
        self.milestone.submit_work(self.owner, note='Done')
        with self.assertRaises(ValidationError):
            self.milestone.submit_work(self.collaborator, note='Not my job')


class MilestoneAPIPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='api_owner', password='test1234')
        self.collaborator = User.objects.create_user(username='api_collab', password='test1234')
        self.stranger = User.objects.create_user(username='api_stranger', password='test1234')

        self.owner_wallet = Wallet.objects.create(user=self.owner)
        add_credit(self.owner_wallet, 100, 'DEPOSIT')
        self.collaborator_wallet = Wallet.objects.create(user=self.collaborator)

        self.project = Project.objects.create(
            owner=self.owner, collaborator=self.collaborator,
            title='API Test Project', description='...',
        )
        self.milestone = Milestone.objects.create(
            project=self.project, title='API Test Milestone', credit_amount=Decimal('20'),
        )

    def url(self, action):
        return f'/api/milestones/{self.milestone.pk}/{action}/'

    def fund_as_owner(self):
        self.client.force_authenticate(self.owner)
        return self.client.post(self.url('fund'))

    # ---- who may fund ----

    def test_owner_can_fund_milestone(self):
        response = self.fund_as_owner()
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.milestone.refresh_from_db()
        self.owner_wallet.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)
        self.assertEqual(self.owner_wallet.balance, Decimal('80'))

    def test_fund_with_wrong_credit_amount_is_rejected(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.url('fund'), {'credit_amount': '25'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.PENDING)

    def test_fund_with_matching_credit_amount_succeeds(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.url('fund'), {'credit_amount': '20'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)

    def test_non_owner_cannot_fund_milestone(self):
        """A total stranger has no relation to the project, so the
        milestone is filtered out of their queryset entirely by
        MilestoneViewSet.get_queryset() before any permission check
        runs. DRF correctly returns 404, not 403, avoiding leaking the
        milestone's existence to unrelated users."""
        self.client.force_authenticate(self.stranger)
        response = self.client.post(self.url('fund'))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_collaborator_cannot_fund_milestone(self):
        """The collaborator IS in the queryset (project__collaborator=user),
        so get_object() succeeds and the request reaches the model. The
        model rejects it (only the receiver may fund) and MilestoneViewSet._run
        turns that ValidationError into a 400."""
        self.client.force_authenticate(self.collaborator)
        response = self.client.post(self.url('fund'))
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.milestone.refresh_from_db()
        self.owner_wallet.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.PENDING)
        self.assertEqual(self.owner_wallet.balance, Decimal('100'))

    def test_unrelated_member_sees_404_not_403(self):
        """A legitimate platform member who simply has no relation to
        THIS specific project should also get 404, confirming the
        queryset-level filtering applies uniformly to any non-member,
        not just to a never-registered stranger."""
        other_collaborator = User.objects.create_user(username='unrelated_collab', password='test1234')
        self.client.force_authenticate(other_collaborator)
        response = self.client.post(self.url('fund'))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_fund(self):
        response = self.client.post(self.url('fund'))
        self.assertIn(response.status_code, (http_status.HTTP_401_UNAUTHORIZED, http_status.HTTP_403_FORBIDDEN))
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.PENDING)

    # ---- approval ----

    def test_stranger_cannot_approve(self):
        self.fund_as_owner()
        self.client.force_authenticate(self.stranger)
        response = self.client.post(self.url('approve-owner'))
        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_both_approvals_via_api_release_credit(self):
        self.fund_as_owner()

        self.client.force_authenticate(self.owner)
        r1 = self.client.post(self.url('approve-owner'))
        self.assertEqual(r1.status_code, http_status.HTTP_200_OK)

        self.client.force_authenticate(self.collaborator)
        r2 = self.client.post(self.url('approve-collaborator'))
        self.assertEqual(r2.status_code, http_status.HTTP_200_OK)

        self.milestone.refresh_from_db()
        self.collaborator_wallet.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)
        self.assertEqual(self.collaborator_wallet.balance, Decimal('20'))

    def test_collaborator_cannot_use_owner_approval_endpoint(self):
        self.fund_as_owner()
        self.client.force_authenticate(self.collaborator)
        response = self.client.post(self.url('approve-owner'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.milestone.refresh_from_db()
        self.assertFalse(self.milestone.owner_approved)

    def test_owner_cannot_use_collaborator_approval_endpoint(self):
        self.fund_as_owner()
        self.client.force_authenticate(self.owner)
        response = self.client.post(self.url('approve-collaborator'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.milestone.refresh_from_db()
        self.assertFalse(self.milestone.collaborator_approved)

    # ---- disputes ----

    def test_non_staff_cannot_resolve_dispute(self):
        self.fund_as_owner()
        self.client.post(self.url('dispute'), {'reason': 'test'})

        self.client.force_authenticate(self.collaborator)  # involved, but not staff
        response = self.client.post(self.url('resolve-dispute-release'))
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.DISPUTED)

    def test_staff_can_resolve_dispute_release(self):
        staff = User.objects.create_user(username='api_staff', password='test1234', is_staff=True)
        self.fund_as_owner()
        self.client.post(self.url('dispute'), {'reason': 'test'})

        self.client.force_authenticate(staff)
        response = self.client.post(self.url('resolve-dispute-release'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.milestone.refresh_from_db()
        self.collaborator_wallet.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.RELEASED)
        self.assertEqual(self.collaborator_wallet.balance, Decimal('20'))

    def test_staff_can_resolve_dispute_refund(self):
        staff = User.objects.create_user(username='api_staff2', password='test1234', is_staff=True)
        self.fund_as_owner()
        self.client.post(self.url('dispute'), {'reason': 'test'})

        self.client.force_authenticate(staff)
        response = self.client.post(self.url('resolve-dispute-refund'))
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.milestone.refresh_from_db()
        self.owner_wallet.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.REFUNDED)
        self.assertEqual(self.owner_wallet.balance, Decimal('100'))

    def test_dispute_without_reason_is_rejected(self):
        self.fund_as_owner()
        response = self.client.post(self.url('dispute'), {'reason': ''})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.status, Milestone.Status.FUNDED)

    # ---- submit / cancel ----

    def test_collaborator_can_submit_work_via_api(self):
        self.fund_as_owner()
        self.client.force_authenticate(self.collaborator)
        response = self.client.post(self.url('submit'), {'note': 'All done', 'url': 'https://example.com/pr/1'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.submission_note, 'All done')

    def test_owner_cannot_submit_work_via_api(self):
        self.fund_as_owner()
        response = self.client.post(self.url('submit'), {'note': 'Sneaky'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_owner_can_request_cancel_but_not_finalize_inside_window(self):
        self.fund_as_owner()
        r1 = self.client.post(self.url('cancel'))
        self.assertEqual(r1.status_code, http_status.HTTP_200_OK)
        r2 = self.client.post(self.url('finalize-cancel'))
        self.assertEqual(r2.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.owner_wallet.refresh_from_db()
        self.assertEqual(self.owner_wallet.balance, Decimal('80'))  # still in escrow


class MilestoneCrudAPITests(TestCase):
    """create / edit / delete rules enforced in MilestoneViewSet."""

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='crud_owner', password='test1234')
        self.collaborator = User.objects.create_user(username='crud_collab', password='test1234')
        self.stranger = User.objects.create_user(username='crud_stranger', password='test1234')
        self.owner_wallet = Wallet.objects.create(user=self.owner)
        add_credit(self.owner_wallet, 100, 'DEPOSIT')
        Wallet.objects.create(user=self.collaborator)

        self.project = Project.objects.create(
            owner=self.owner, collaborator=self.collaborator,
            title='CRUD Project', description='...',
        )
        # created_by is None -> the project owner counts as the creator
        self.milestone = Milestone.objects.create(
            project=self.project, title='Editable', description='desc', credit_amount=Decimal('20'),
        )

    def payload(self, **overrides):
        data = {
            'project': self.project.pk, 'title': 'New milestone',
            'description': 'Something to do', 'credit_amount': '15',
        }
        data.update(overrides)
        return data

    def test_owner_can_create_milestone(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/milestones/', self.payload())
        self.assertEqual(response.status_code, http_status.HTTP_201_CREATED)
        created = Milestone.objects.get(pk=response.data['id'])
        self.assertEqual(created.created_by, self.owner)
        self.assertEqual(created.status, Milestone.Status.PENDING)

    def test_stranger_cannot_create_milestone_on_project(self):
        self.client.force_authenticate(self.stranger)
        response = self.client.post('/api/milestones/', self.payload())
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertEqual(Milestone.objects.filter(project=self.project).count(), 1)

    def test_credit_must_be_positive(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post('/api/milestones/', self.payload(credit_amount='0'))
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_creator_can_edit_pending_milestone(self):
        self.client.force_authenticate(self.owner)
        response = self.client.patch(f'/api/milestones/{self.milestone.pk}/', {'title': 'Renamed'})
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.title, 'Renamed')

    def test_non_creator_cannot_edit_milestone(self):
        self.client.force_authenticate(self.collaborator)
        response = self.client.patch(f'/api/milestones/{self.milestone.pk}/', {'title': 'Hijacked'})
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.milestone.refresh_from_db()
        self.assertEqual(self.milestone.title, 'Editable')

    def test_cannot_edit_funded_milestone(self):
        self.milestone.fund(self.owner)
        self.client.force_authenticate(self.owner)
        response = self.client.patch(f'/api/milestones/{self.milestone.pk}/', {'title': 'Too late'})
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)

    def test_creator_can_delete_pending_milestone(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f'/api/milestones/{self.milestone.pk}/')
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assertFalse(Milestone.objects.filter(pk=self.milestone.pk).exists())

    def test_non_creator_cannot_delete_milestone(self):
        self.client.force_authenticate(self.collaborator)
        response = self.client.delete(f'/api/milestones/{self.milestone.pk}/')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertTrue(Milestone.objects.filter(pk=self.milestone.pk).exists())

    def test_cannot_delete_funded_milestone(self):
        self.milestone.fund(self.owner)
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f'/api/milestones/{self.milestone.pk}/')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Milestone.objects.filter(pk=self.milestone.pk).exists())


class ProjectDeleteGuardTests(TestCase):
    """Deleting a project must never destroy credit that is held in escrow."""

    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='pd_owner', password='test1234')
        self.collaborator = User.objects.create_user(username='pd_collab', password='test1234')
        owner_wallet = Wallet.objects.create(user=self.owner)
        add_credit(owner_wallet, 100, 'DEPOSIT')
        Wallet.objects.create(user=self.collaborator)

        self.project = Project.objects.create(
            owner=self.owner, collaborator=self.collaborator,
            title='Guarded Project', description='...',
        )
        self.milestone = Milestone.objects.create(
            project=self.project, title='M1', credit_amount=Decimal('20'),
        )

    def test_cannot_delete_project_with_funded_milestone(self):
        self.milestone.fund(self.owner)
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f'/api/projects/{self.project.pk}/')
        self.assertEqual(response.status_code, http_status.HTTP_400_BAD_REQUEST)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())

    def test_can_delete_project_with_only_pending_milestones(self):
        self.client.force_authenticate(self.owner)
        response = self.client.delete(f'/api/projects/{self.project.pk}/')
        self.assertEqual(response.status_code, http_status.HTTP_204_NO_CONTENT)
        self.assertFalse(Project.objects.filter(pk=self.project.pk).exists())

    def test_collaborator_cannot_delete_project(self):
        self.client.force_authenticate(self.collaborator)
        response = self.client.delete(f'/api/projects/{self.project.pk}/')
        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)
        self.assertTrue(Project.objects.filter(pk=self.project.pk).exists())