from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.contrib.auth.models import User
from django.core import mail
from django.core.cache import cache
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from .models import Profile, EmailVerification, PasswordResetCode
from wallet.models import Wallet, LedgerEntry


class ProfileTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='dev1', password='test1234')

    def test_create_profile(self):
        profile = Profile.objects.create(
            user=self.user,
            bio='Full-stack developer',
            github_url='https://github.com/dev1',
        )
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.bio, 'Full-stack developer')
        self.assertFalse(profile.is_verified)  # default should be False

    def test_profile_str_returns_username(self):
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(str(profile), 'dev1')

    def test_optional_fields_can_be_blank(self):
        profile = Profile.objects.create(user=self.user)
        self.assertEqual(profile.bio, '')
        self.assertEqual(profile.github_url, '')
        self.assertEqual(profile.figma_url, '')
        self.assertEqual(profile.behance_url, '')

    def test_one_to_one_constraint(self):
        Profile.objects.create(user=self.user)
        # a second Profile for the same user must fail (OneToOneField)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Profile.objects.create(user=self.user)

    def test_verified_flag_can_be_set(self):
        profile = Profile.objects.create(user=self.user, is_verified=True)
        self.assertTrue(profile.is_verified)

    def test_deleting_user_deletes_profile(self):
        profile = Profile.objects.create(user=self.user)
        profile_id = profile.id
        self.user.delete()
        self.assertFalse(Profile.objects.filter(id=profile_id).exists())


class RegistrationTests(TestCase):
    def setUp(self):
        cache.clear()  # reset throttle counters
        self.client = APIClient()

    def test_register_with_valid_gmail_succeeds(self):
        response = self.client.post('/api/register/', {
            'username': 'newuser',
            'email': 'newuser@gmail.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username='newuser')
        self.assertFalse(user.is_active)  # not active until verified

    def test_register_with_valid_ait_email_succeeds(self):
        response = self.client.post('/api/register/', {
            'username': 'newuser2',
            'email': 'newuser2@ait.asia',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_register_with_disallowed_domain_fails(self):
        response = self.client.post('/api/register/', {
            'username': 'baduser',
            'email': 'baduser@yahoo.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username='baduser').exists())

    def test_register_creates_verification_code(self):
        self.client.post('/api/register/', {
            'username': 'newuser3',
            'email': 'newuser3@gmail.com',
            'password': 'testpass123',
        })
        user = User.objects.get(username='newuser3')
        self.assertTrue(EmailVerification.objects.filter(user=user).exists())

    def test_register_sends_email(self):
        self.client.post('/api/register/', {
            'username': 'newuser4',
            'email': 'newuser4@gmail.com',
            'password': 'testpass123',
        })
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('newuser4@gmail.com', mail.outbox[0].to)

    def test_cannot_register_duplicate_username(self):
        User.objects.create_user(username='existing', password='x', email='existing@gmail.com')
        response = self.client.post('/api/register/', {
            'username': 'existing',
            'email': 'another@gmail.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_register_duplicate_email(self):
        User.objects.create_user(username='someone', password='x', email='dup@gmail.com')
        response = self.client.post('/api/register/', {
            'username': 'newuser5',
            'email': 'dup@gmail.com',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class VerifyEmailTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        # simulate a registered-but-unverified user via the real API
        register_response = self.client.post('/api/register/', {
            'username': 'verifyuser',
            'email': 'verifyuser@gmail.com',
            'password': 'testpass123',
        })
        self.user_id = register_response.data['user_id']
        self.user = User.objects.get(id=self.user_id)
        self.verification = EmailVerification.objects.get(user=self.user)

    def test_correct_code_activates_user(self):
        response = self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': self.verification.code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_correct_code_returns_tokens(self):
        response = self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': self.verification.code,
        })
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_correct_code_deletes_verification_record(self):
        self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': self.verification.code,
        })
        self.assertFalse(EmailVerification.objects.filter(user=self.user).exists())

    def test_incorrect_code_does_not_activate(self):
        # pick a code guaranteed to differ from the real one
        wrong = '000000' if self.verification.code != '000000' else '111111'
        response = self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': wrong,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_expired_code_does_not_activate(self):
        self.verification.created_at = timezone.now() - timedelta(minutes=15)
        self.verification.save()

        response = self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': self.verification.code,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_resend_code_generates_new_code(self):
        old_pk = self.verification.pk

        response = self.client.post('/api/resend-code/', {'user_id': self.user_id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # the old row was deleted and replaced, not updated in place,
        # so fetch the current record instead of refresh_from_db().
        new_verification = EmailVerification.objects.get(user=self.user)

        self.assertEqual(len(mail.outbox), 2)  # 1 from register, 1 from resend
        self.assertNotEqual(new_verification.pk, old_pk)  # old row was replaced
        # the resent email must contain the NEW code
        self.assertIn(new_verification.code, mail.outbox[1].body)

    def test_resend_code_for_unknown_user_fails(self):
        response = self.client.post('/api/resend-code/', {'user_id': 999999})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_code_for_active_user_fails(self):
        active = User.objects.create_user(
            username='activeguy', password='x', email='activeguy@gmail.com', is_active=True,
        )
        response = self.client.post('/api/resend-code/', {'user_id': active.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verification_grants_signup_bonus_exactly_once(self):
        response = self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': self.verification.code,
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        wallet = Wallet.objects.get(user=self.user)
        self.assertEqual(wallet.balance, Decimal('20'))
        # exactly one ledger row for the bonus
        # (adjust the filter if your LedgerEntry fields are named differently)
        self.assertEqual(LedgerEntry.objects.filter(wallet=wallet).count(), 1)

        # Simulate a retried/duplicate verification request (double-click,
        # network retry...). Must NOT grant a second bonus, since the
        # verification record was already deleted by the first call.
        response2 = self.client.post('/api/verify-email/', {
            'user_id': self.user_id, 'code': self.verification.code,
        })
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

        wallet.refresh_from_db()
        self.assertEqual(wallet.balance, Decimal('20'))  # unchanged
        self.assertEqual(LedgerEntry.objects.filter(wallet=wallet).count(), 1)


class LoginLogoutTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='loginuser', password='testpass123',
            email='loginuser@gmail.com', is_active=True,
        )

    def test_login_with_correct_credentials_succeeds(self):
        response = self.client.post('/api/login/', {
            'username': 'loginuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_with_wrong_password_fails(self):
        response = self.client.post('/api/login/', {
            'username': 'loginuser',
            'password': 'wrongpass',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data['detail'], 'Invalid username or password.')

    def test_inactive_user_cannot_login(self):
        self.user.is_active = False
        self.user.save()
        response = self.client.post('/api/login/', {
            'username': 'loginuser',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # NOTE: fails until LoginView is fixed. With the default ModelBackend,
        # authenticate() returns None for inactive users, so the view currently
        # returns "Invalid username or password." instead.
        self.assertEqual(response.data['detail'], 'This account is not verified yet.')

    def test_logout_blacklists_refresh_token(self):
        login_response = self.client.post('/api/login/', {
            'username': 'loginuser',
            'password': 'testpass123',
        })
        access = login_response.data['access']
        refresh = login_response.data['refresh']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        response = self.client.post('/api/logout/', {'refresh': refresh})
        self.assertEqual(response.status_code, status.HTTP_205_RESET_CONTENT)

        # the blacklisted refresh token can no longer be used to log out again
        response2 = self.client.post('/api/logout/', {'refresh': refresh})
        self.assertEqual(response2.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_without_refresh_token_fails(self):
        self.client.force_authenticate(self.user)
        response = self.client.post('/api/logout/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_requires_authentication(self):
        response = self.client.post('/api/logout/', {'refresh': 'whatever'})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PasswordResetTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='resetuser', email='reset@gmail.com',
            password='oldpass123', is_active=True,
        )

    def _request_code(self):
        self.client.post('/api/forgot-password/', {'email': 'reset@gmail.com'})
        return PasswordResetCode.objects.get(user=self.user)

    def _wrong_code(self, real_code):
        return '000000' if real_code != '000000' else '111111'

    def test_forgot_password_sends_email_with_code(self):
        reset = self._request_code()
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(reset.code, mail.outbox[0].body)

    def test_unknown_email_returns_same_response_and_sends_nothing(self):
        r1 = self.client.post('/api/forgot-password/', {'email': 'nobody@gmail.com'})
        self.assertEqual(len(mail.outbox), 0)
        r2 = self.client.post('/api/forgot-password/', {'email': 'reset@gmail.com'})
        self.assertEqual(r1.status_code, r2.status_code)
        self.assertEqual(r1.data, r2.data)  # does not leak which emails exist
        self.assertEqual(len(mail.outbox), 1)

    def test_inactive_user_gets_no_reset_code(self):
        self.user.is_active = False
        self.user.save()
        self.client.post('/api/forgot-password/', {'email': 'reset@gmail.com'})
        self.assertFalse(PasswordResetCode.objects.filter(user=self.user).exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_requesting_new_code_replaces_old_one(self):
        first = self._request_code()
        first_pk = first.pk
        second = self._request_code()
        self.assertNotEqual(first_pk, second.pk)
        self.assertEqual(PasswordResetCode.objects.filter(user=self.user).count(), 1)

    def test_verify_correct_code_succeeds_and_keeps_code(self):
        reset = self._request_code()
        r = self.client.post('/api/verify-reset-code/', {
            'email': 'reset@gmail.com', 'code': reset.code,
        })
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        # code must still exist: the reset-password step needs it
        self.assertTrue(PasswordResetCode.objects.filter(user=self.user).exists())

    def test_wrong_code_increments_attempts(self):
        reset = self._request_code()
        r = self.client.post('/api/verify-reset-code/', {
            'email': 'reset@gmail.com', 'code': self._wrong_code(reset.code),
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        reset.refresh_from_db()
        self.assertEqual(reset.attempts, 1)

    def test_too_many_attempts_locks_out_correct_code(self):
        reset = self._request_code()
        correct = reset.code
        wrong = self._wrong_code(correct)
        for _ in range(PasswordResetCode.MAX_ATTEMPTS):
            self.client.post('/api/verify-reset-code/', {
                'email': 'reset@gmail.com', 'code': wrong,
            })
        r = self.client.post('/api/verify-reset-code/', {
            'email': 'reset@gmail.com', 'code': correct,
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(PasswordResetCode.objects.filter(user=self.user).exists())

    def test_expired_code_rejected(self):
        reset = self._request_code()
        reset.created_at = timezone.now() - timedelta(minutes=15)
        reset.save()
        r = self.client.post('/api/verify-reset-code/', {
            'email': 'reset@gmail.com', 'code': reset.code,
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_email_on_verify_is_rejected(self):
        r = self.client.post('/api/verify-reset-code/', {
            'email': 'nobody@gmail.com', 'code': '123456',
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reset_password_success(self):
        reset = self._request_code()
        r = self.client.post('/api/reset-password/', {
            'email': 'reset@gmail.com', 'code': reset.code,
            'new_password': 'Brand-new-pass-91',
        })
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brand-new-pass-91'))
        self.assertFalse(PasswordResetCode.objects.filter(user=self.user).exists())

    def test_reset_code_cannot_be_reused(self):
        reset = self._request_code()
        payload = {
            'email': 'reset@gmail.com', 'code': reset.code,
            'new_password': 'Brand-new-pass-91',
        }
        self.client.post('/api/reset-password/', payload)
        r = self.client.post('/api/reset-password/', {**payload, 'new_password': 'Another-pass-77'})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Brand-new-pass-91'))

    def test_weak_password_rejected_and_code_kept(self):
        reset = self._request_code()
        r = self.client.post('/api/reset-password/', {
            'email': 'reset@gmail.com', 'code': reset.code, 'new_password': '123',
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('new_password', r.data)
        self.assertTrue(PasswordResetCode.objects.filter(user=self.user).exists())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))  # unchanged

    def test_reset_with_wrong_code_does_not_change_password(self):
        reset = self._request_code()
        r = self.client.post('/api/reset-password/', {
            'email': 'reset@gmail.com', 'code': self._wrong_code(reset.code),
            'new_password': 'Brand-new-pass-91',
        })
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('oldpass123'))


class MeViewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='meuser', password='testpass123',
            email='meuser@gmail.com', is_active=True,
        )

    def test_requires_authentication(self):
        r = self.client.get('/api/me/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_returns_own_profile_and_creates_it_if_missing(self):
        self.client.force_authenticate(self.user)
        self.assertFalse(Profile.objects.filter(user=self.user).exists())
        r = self.client.get('/api/me/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertTrue(Profile.objects.filter(user=self.user).exists())

    def test_patch_updates_bio_and_links(self):
        self.client.force_authenticate(self.user)
        r = self.client.patch('/api/me/', {
            'bio': 'Hello there',
            'github_url': 'https://github.com/meuser',
            'figma_url': 'https://figma.com/@meuser',
            'behance_url': 'https://behance.net/meuser',
        }, format='json')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        profile = Profile.objects.get(user=self.user)
        self.assertEqual(profile.bio, 'Hello there')
        self.assertEqual(profile.github_url, 'https://github.com/meuser')
        self.assertEqual(profile.figma_url, 'https://figma.com/@meuser')
        self.assertEqual(profile.behance_url, 'https://behance.net/meuser')

    def test_patch_cannot_escalate_privileges_or_self_verify(self):
        self.client.force_authenticate(self.user)
        self.client.patch('/api/me/', {'is_staff': True, 'is_verified': True}, format='json')
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertFalse(Profile.objects.get(user=self.user).is_verified)

    def test_put_is_not_allowed(self):
        self.client.force_authenticate(self.user)
        r = self.client.put('/api/me/', {'bio': 'x'}, format='json')
        self.assertEqual(r.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class UserProfileViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.viewer = User.objects.create_user(
            username='viewer', password='x', email='viewer@gmail.com', is_active=True,
        )
        self.target = User.objects.create_user(
            username='target', password='x', email='target@gmail.com', is_active=True,
        )

    def test_requires_authentication(self):
        r = self.client.get('/api/users/target/')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_public_profile_does_not_expose_email(self):
        self.client.force_authenticate(self.viewer)
        r = self.client.get('/api/users/target/')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertNotIn('email', r.data)
        self.assertNotIn('target@gmail.com', str(r.data))

    def test_inactive_user_returns_404(self):
        self.target.is_active = False
        self.target.save()
        self.client.force_authenticate(self.viewer)
        r = self.client.get('/api/users/target/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_unknown_user_returns_404(self):
        self.client.force_authenticate(self.viewer)
        r = self.client.get('/api/users/ghost/')
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)


class UserSearchViewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.me = User.objects.create_user(
            username='bobme', password='x', email='bobme@gmail.com', is_active=True,
        )
        for name in ['bob', 'bobby', 'abob', 'alice']:
            User.objects.create_user(
                username=name, password='x', email=f'{name}@gmail.com', is_active=True,
            )
        User.objects.create_user(
            username='bobinactive', password='x', email='bi@gmail.com', is_active=False,
        )
        self.client.force_authenticate(self.me)

    def test_requires_authentication(self):
        r = APIClient().get('/api/users/?q=bob')
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_empty_query_returns_empty_list(self):
        r = self.client.get('/api/users/?q=')
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.data, [])

    def test_excludes_self_and_inactive_users(self):
        r = self.client.get('/api/users/?q=bob')
        names = [u['username'] for u in r.data]
        self.assertNotIn('bobme', names)
        self.assertNotIn('bobinactive', names)
        self.assertNotIn('alice', names)

    def test_prefix_matches_come_first_then_alphabetical(self):
        r = self.client.get('/api/users/?q=bob')
        names = [u['username'] for u in r.data]
        # 'bob' and 'bobby' start with the query; 'abob' only contains it
        self.assertEqual(names, ['bob', 'bobby', 'abob'])

    def test_search_is_case_insensitive(self):
        r = self.client.get('/api/users/?q=BOB')
        names = [u['username'] for u in r.data]
        self.assertIn('bob', names)

    def test_results_are_capped_at_eight(self):
        for i in range(12):
            User.objects.create_user(
                username=f'zed{i:02d}', password='x', email=f'zed{i}@gmail.com', is_active=True,
            )
        r = self.client.get('/api/users/?q=zed')
        self.assertEqual(len(r.data), 8)