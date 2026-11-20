from django.test import TestCase
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from rest_framework.test import APIClient
from rest_framework import status

from .models import Group, GroupMembership, GroupPost, GroupPostComment

APPROVED = GroupMembership.Status.APPROVED
PENDING = GroupMembership.Status.PENDING


class GroupModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='creator1', password='test1234')

    def test_create_group(self):
        group = Group.objects.create(name='Web Devs', description='...', created_by=self.user)
        self.assertEqual(str(group), 'Web Devs')

    def test_unique_membership(self):
        group = Group.objects.create(name='Designers', created_by=self.user)
        GroupMembership.objects.create(group=group, user=self.user, status=APPROVED)
        with self.assertRaises(IntegrityError), transaction.atomic():
            GroupMembership.objects.create(group=group, user=self.user, status=APPROVED)


class GroupAPITestBase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username='alice3', password='test1234')  # owner
        self.bob = User.objects.create_user(username='bob3', password='test1234')
        self.carol = User.objects.create_user(username='carol3', password='test1234')

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    def make_group(self, name='Test Group', owner=None):
        """Create a group whose owner is also an approved member (like the API does)."""
        owner = owner or self.alice
        group = Group.objects.create(name=name, created_by=owner)
        GroupMembership.objects.create(group=group, user=owner, status=APPROVED)
        return group

    def add_member(self, group, user, status=APPROVED):
        return GroupMembership.objects.create(group=group, user=user, status=status)


class GroupCrudTests(GroupAPITestBase):
    def test_create_group_auto_joins_creator_as_approved(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/groups/', {'name': 'Indie Designers', 'description': '...'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        group_id = response.data['id']
        self.assertTrue(
            GroupMembership.objects.filter(group_id=group_id, user=self.alice, status=APPROVED).exists()
        )

    def test_anonymous_cannot_create_group(self):
        response = self.client.post('/api/groups/', {'name': 'Nope', 'description': '...'})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertFalse(Group.objects.filter(name='Nope').exists())

    def test_anyone_can_list_groups(self):
        Group.objects.create(name='Public Group', created_by=self.alice)
        response = self.client.get('/api/groups/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_non_owner_cannot_edit_group(self):
        group = self.make_group()
        self.auth_as(self.bob)
        response = self.client.patch(f'/api/groups/{group.pk}/', {'name': 'Hacked'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Test Group')

    def test_owner_can_edit_group(self):
        group = self.make_group()
        self.auth_as(self.alice)
        response = self.client.patch(f'/api/groups/{group.pk}/', {'name': 'Renamed'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        group.refresh_from_db()
        self.assertEqual(group.name, 'Renamed')

    def test_non_owner_cannot_delete_group(self):
        group = self.make_group()
        self.auth_as(self.bob)
        response = self.client.delete(f'/api/groups/{group.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Group.objects.filter(pk=group.pk).exists())

    def test_owner_can_delete_group(self):
        group = self.make_group()
        self.auth_as(self.alice)
        response = self.client.delete(f'/api/groups/{group.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Group.objects.filter(pk=group.pk).exists())


class JoinLeaveTests(GroupAPITestBase):
    def test_join_group_creates_pending_request(self):
        group = self.make_group('Data Nerds')
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{group.pk}/join/')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        membership = GroupMembership.objects.get(group=group, user=self.bob)
        self.assertEqual(membership.status, PENDING)  # not a member until approved

    def test_join_requires_authentication(self):
        group = self.make_group()
        response = self.client.post(f'/api/groups/{group.pk}/join/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_join_twice_fails(self):
        group = self.make_group('Gamers')
        self.auth_as(self.bob)
        self.client.post(f'/api/groups/{group.pk}/join/')
        response = self.client.post(f'/api/groups/{group.pk}/join/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GroupMembership.objects.filter(group=group, user=self.bob).count(), 1)

    def test_approved_member_cannot_join_again(self):
        group = self.make_group()
        self.add_member(group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{group.pk}/join/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_cannot_join_own_group(self):
        group = self.make_group()
        self.auth_as(self.alice)
        response = self.client.post(f'/api/groups/{group.pk}/join/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_leave_group(self):
        group = self.make_group('Writers')
        self.add_member(group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{group.pk}/leave/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.bob).exists())

    def test_leave_cancels_pending_request(self):
        group = self.make_group()
        self.add_member(group, self.bob, PENDING)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{group.pk}/leave/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMembership.objects.filter(group=group, user=self.bob).exists())

    def test_leave_without_membership_fails(self):
        group = self.make_group('Musicians')
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{group.pk}/leave/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_owner_cannot_leave_own_group(self):
        group = self.make_group()
        self.auth_as(self.alice)
        response = self.client.post(f'/api/groups/{group.pk}/leave/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(GroupMembership.objects.filter(group=group, user=self.alice).exists())


class MembershipApprovalTests(GroupAPITestBase):
    def setUp(self):
        super().setUp()
        self.group = self.make_group('Approval Group')
        self.pending = self.add_member(self.group, self.bob, PENDING)

    def test_owner_can_list_pending_requests(self):
        self.auth_as(self.alice)
        response = self.client.get(f'/api/groups/{self.group.pk}/requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_non_owner_cannot_list_requests(self):
        self.auth_as(self.bob)
        response = self.client.get(f'/api/groups/{self.group.pk}/requests/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_approve_request(self):
        self.auth_as(self.alice)
        response = self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, APPROVED)

    def test_non_owner_cannot_approve_request(self):
        self.add_member(self.group, self.carol, APPROVED)
        self.auth_as(self.carol)
        response = self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, PENDING)

    def test_requester_cannot_approve_themselves(self):
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, PENDING)

    def test_approve_nonexistent_or_already_approved_returns_404(self):
        self.auth_as(self.alice)
        r1 = self.client.post(f'/api/groups/{self.group.pk}/requests/999999/approve/')
        self.assertEqual(r1.status_code, status.HTTP_404_NOT_FOUND)
        # approving the same request twice: second time it is no longer pending
        self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/approve/')
        r2 = self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/approve/')
        self.assertEqual(r2.status_code, status.HTTP_404_NOT_FOUND)

    def test_cannot_approve_request_of_another_group(self):
        other = self.make_group('Other Group', owner=self.carol)
        self.auth_as(self.carol)
        # carol owns "other", but the request belongs to self.group
        response = self.client.post(f'/api/groups/{other.pk}/requests/{self.pending.pk}/approve/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, PENDING)

    def test_owner_can_reject_request(self):
        self.auth_as(self.alice)
        response = self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/reject/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMembership.objects.filter(pk=self.pending.pk).exists())

    def test_non_owner_cannot_reject_request(self):
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/reject/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(GroupMembership.objects.filter(pk=self.pending.pk).exists())

    def test_approved_user_can_then_post(self):
        self.auth_as(self.alice)
        self.client.post(f'/api/groups/{self.group.pk}/requests/{self.pending.pk}/approve/')
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{self.group.pk}/posts/', {'content': 'Hi all'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class MembersManagementTests(GroupAPITestBase):
    def setUp(self):
        super().setUp()
        self.group = self.make_group('Members Group')
        self.bob_membership = self.add_member(self.group, self.bob, APPROVED)
        self.owner_membership = GroupMembership.objects.get(group=self.group, user=self.alice)

    def test_owner_can_list_members(self):
        self.auth_as(self.alice)
        response = self.client.get(f'/api/groups/{self.group.pk}/members/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)  # owner + bob

    def test_non_owner_cannot_list_members(self):
        self.auth_as(self.bob)
        response = self.client.get(f'/api/groups/{self.group.pk}/members/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_owner_can_kick_member(self):
        self.auth_as(self.alice)
        response = self.client.delete(f'/api/groups/{self.group.pk}/members/{self.bob_membership.pk}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(GroupMembership.objects.filter(pk=self.bob_membership.pk).exists())

    def test_non_owner_cannot_kick_member(self):
        carol_m = self.add_member(self.group, self.carol, APPROVED)
        self.auth_as(self.bob)
        response = self.client.delete(f'/api/groups/{self.group.pk}/members/{carol_m.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(GroupMembership.objects.filter(pk=carol_m.pk).exists())

    def test_owner_cannot_be_kicked(self):
        self.auth_as(self.alice)
        response = self.client.delete(f'/api/groups/{self.group.pk}/members/{self.owner_membership.pk}/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertTrue(GroupMembership.objects.filter(pk=self.owner_membership.pk).exists())

    def test_cannot_kick_pending_request_via_kick_endpoint(self):
        pending = self.add_member(self.group, self.carol, PENDING)
        self.auth_as(self.alice)
        response = self.client.delete(f'/api/groups/{self.group.pk}/members/{pending.pk}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class GroupPostTests(GroupAPITestBase):
    def setUp(self):
        super().setUp()
        self.group = self.make_group('Post Group')

    def test_non_member_cannot_post_in_group(self):
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{self.group.pk}/posts/', {'content': 'Hello group'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(GroupPost.objects.count(), 0)

    def test_pending_member_cannot_post_in_group(self):
        self.add_member(self.group, self.bob, PENDING)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{self.group.pk}/posts/', {'content': 'Hello group'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_member_can_post_in_group(self):
        self.add_member(self.group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/groups/{self.group.pk}/posts/', {'content': 'Hello group'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post = GroupPost.objects.get(group=self.group)
        self.assertEqual(post.author, self.bob)

    def test_anonymous_cannot_post(self):
        response = self.client.post(f'/api/groups/{self.group.pk}/posts/', {'content': 'Hi'})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_approved_member_can_read_group_posts(self):
        GroupPost.objects.create(group=self.group, author=self.alice, content='Recipe time')
        self.add_member(self.group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.get(f'/api/groups/{self.group.pk}/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_non_member_cannot_read_group_posts(self):
        GroupPost.objects.create(group=self.group, author=self.alice, content='Members only')
        self.auth_as(self.bob)
        response = self.client.get(f'/api/groups/{self.group.pk}/posts/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_pending_member_cannot_read_group_posts(self):
        GroupPost.objects.create(group=self.group, author=self.alice, content='Members only')
        self.add_member(self.group, self.bob, PENDING)
        self.auth_as(self.bob)
        response = self.client.get(f'/api/groups/{self.group.pk}/posts/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_anonymous_cannot_read_group_posts(self):
        GroupPost.objects.create(group=self.group, author=self.alice, content='Members only')
        response = self.client.get(f'/api/groups/{self.group.pk}/posts/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class GroupCommentTests(GroupAPITestBase):
    def setUp(self):
        super().setUp()
        self.group = self.make_group('Runners')
        self.post = GroupPost.objects.create(group=self.group, author=self.alice, content='5k today')

    def test_member_can_comment_on_group_post(self):
        self.add_member(self.group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/group-posts/{self.post.pk}/comment/', {'content': 'Nice pace!'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(GroupPostComment.objects.filter(post=self.post).count(), 1)

    def test_empty_comment_rejected(self):
        self.add_member(self.group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/group-posts/{self.post.pk}/comment/', {'content': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(GroupPostComment.objects.count(), 0)

    def test_whitespace_only_comment_rejected(self):
        self.add_member(self.group, self.bob, APPROVED)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/group-posts/{self.post.pk}/comment/', {'content': '   '})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_member_cannot_comment(self):
        # GroupPostViewSet only exposes posts of groups the user belongs to,
        # so a non-member gets 404 (the post is invisible to them).
        self.auth_as(self.bob)
        response = self.client.post(f'/api/group-posts/{self.post.pk}/comment/', {'content': 'Hi'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(GroupPostComment.objects.count(), 0)

    def test_pending_member_cannot_comment(self):
        self.add_member(self.group, self.bob, PENDING)
        self.auth_as(self.bob)
        response = self.client.post(f'/api/group-posts/{self.post.pk}/comment/', {'content': 'Hi'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(GroupPostComment.objects.count(), 0)

    def test_anonymous_cannot_comment(self):
        response = self.client.post(f'/api/group-posts/{self.post.pk}/comment/', {'content': 'Hi'})
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))