from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from rest_framework import status

from projects.models import Project
from .models import BuildLogEntry


class BuildLogEntryModelTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username='owner_bl', password='test1234')
        self.project = Project.objects.create(owner=self.owner, title='Portfolio Site', description='...')

    def test_create_entry(self):
        entry = BuildLogEntry.objects.create(
            project=self.project, author=self.owner,
            title='Day 1', content='Set up repo and CI',
        )
        self.assertEqual(str(entry), f"[{self.project.title}] Day 1")

    def test_ordered_newest_first(self):
        e1 = BuildLogEntry.objects.create(project=self.project, author=self.owner, title='First', content='...')
        e2 = BuildLogEntry.objects.create(project=self.project, author=self.owner, title='Second', content='...')
        entries = list(BuildLogEntry.objects.all())
        self.assertEqual(entries[0], e2)
        self.assertEqual(entries[1], e1)


class BuildLogAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(username='owner1', password='test1234')
        self.collaborator = User.objects.create_user(username='collab1', password='test1234')
        self.outsider = User.objects.create_user(username='outsider1', password='test1234')
        self.project = Project.objects.create(
            owner=self.owner, title='Chat App', description='...', collaborator=self.collaborator,
        )

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def test_anyone_can_read_build_logs(self):
        BuildLogEntry.objects.create(project=self.project, author=self.owner, title='Log', content='...')
        response = self.client.get('/api/build-logs/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_cannot_create(self):
        response = self.client.post('/api/build-logs/', {
            'project': self.project.pk, 'title': 'Log', 'content': 'Progress update',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_owner_can_create(self):
        self.auth_as(self.owner)
        response = self.client.post('/api/build-logs/', {
            'project': self.project.pk, 'title': 'Log', 'content': 'Progress update',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author_username'], 'owner1')

    def test_collaborator_can_create(self):
        self.auth_as(self.collaborator)
        response = self.client.post('/api/build-logs/', {
            'project': self.project.pk, 'title': 'Log', 'content': 'Progress update',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_non_member_cannot_create(self):
        self.auth_as(self.outsider)
        response = self.client.post('/api/build-logs/', {
            'project': self.project.pk, 'title': 'Log', 'content': 'Progress update',
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)