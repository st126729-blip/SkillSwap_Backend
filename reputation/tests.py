from django.core.exceptions import ValidationError
from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from .models import Vouch


class VouchModelTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user(username='vouch_a', password='test1234')
        self.b = User.objects.create_user(username='vouch_b', password='test1234')

    def test_create_vouch(self):
        vouch = Vouch.objects.create(
            voucher=self.a, vouchee=self.b, skill_area='React',
            technical_quality=5, reliability=4, comment='Great work',
        )
        self.assertIn('vouched for', str(vouch))

    def test_self_vouch_invalid_via_clean(self):
        vouch = Vouch(voucher=self.a, vouchee=self.a, technical_quality=5, reliability=5)
        with self.assertRaises(ValidationError):
            vouch.clean()

    def test_rating_out_of_range_invalid(self):
        vouch = Vouch(voucher=self.a, vouchee=self.b, technical_quality=6, reliability=5)
        with self.assertRaises(ValidationError):
            vouch.full_clean()


class VouchAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username='alice4', password='test1234')
        self.bob = User.objects.create_user(username='bob4', password='test1234')

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def test_unauthenticated_cannot_vouch(self):
        response = self.client.post('/api/vouches/', {
            'vouchee': self.bob.pk, 'technical_quality': 5, 'reliability': 5,
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_vouch(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/vouches/', {
            'vouchee': self.bob.pk, 'skill_area': 'Django', 'technical_quality': 4, 'reliability': 5,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['voucher_username'], 'alice4')

    def test_cannot_vouch_self(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/vouches/', {
            'vouchee': self.alice.pk, 'technical_quality': 5, 'reliability': 5,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_reputation_summary_no_vouches(self):
        response = self.client.get(f'/api/reputation/{self.bob.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['vouch_count'], 0)
        self.assertIsNone(response.data['avg_technical_quality'])

    def test_reputation_summary_averages(self):
        self.auth_as(self.alice)
        self.client.post('/api/vouches/', {
            'vouchee': self.bob.pk, 'technical_quality': 4, 'reliability': 4,
        })
        third = User.objects.create_user(username='carol4', password='test1234')
        self.auth_as(third)
        self.client.post('/api/vouches/', {
            'vouchee': self.bob.pk, 'technical_quality': 2, 'reliability': 4,
        })
        response = self.client.get(f'/api/reputation/{self.bob.pk}/')
        self.assertEqual(response.data['vouch_count'], 2)
        self.assertEqual(response.data['avg_technical_quality'], 3.0)
        self.assertEqual(response.data['avg_reliability'], 4.0)

    def test_reputation_summary_user_not_found(self):
        response = self.client.get('/api/reputation/999999/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


from django.test import TestCase

# Create your tests here.
