import io
from decimal import Decimal
from PIL import Image
from django.test import TestCase
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from .models import Post, Comment
from projects.models import Project
from .models import Post, Reaction, Comment


def make_test_image(name='test.jpg', content_type='image/jpeg'):
    """Tạo 1 file ảnh thật (1x1 pixel) trong bộ nhớ để test upload."""
    image = Image.new('RGB', (1, 1))
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG')
    buffer.seek(0)
    return SimpleUploadedFile(name, buffer.read(), content_type=content_type)


class PostModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='alice', password='test1234')

    def test_create_post(self):
        post = Post.objects.create(author=self.user, title='Need a dev', content='Looking for help')
        self.assertEqual(post.author, self.user)
        self.assertEqual(str(post), 'Need a dev by alice')

    def test_post_ordered_newest_first(self):
        p1 = Post.objects.create(author=self.user, title='First', content='...')
        p2 = Post.objects.create(author=self.user, title='Second', content='...')
        posts = list(Post.objects.all())
        self.assertEqual(posts[0], p2)  # newest first
        self.assertEqual(posts[1], p1)

    def test_post_can_link_to_project(self):
        owner = User.objects.create_user(username='owner1', password='test1234')
        project = Project.objects.create(owner=owner, title='Test Project', description='...')
        post = Post.objects.create(author=self.user, title='Check my project', content='...', related_project=project)
        self.assertEqual(post.related_project, project)


class ReactionModelTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='author1', password='test1234')
        self.reactor = User.objects.create_user(username='reactor1', password='test1234')
        self.post = Post.objects.create(author=self.author, title='Post', content='...')

    def test_create_reaction(self):
        reaction = Reaction.objects.create(post=self.post, user=self.reactor, reaction_type='LOVE')
        self.assertEqual(reaction.reaction_type, 'LOVE')

    def test_one_reaction_per_user_per_post(self):
        Reaction.objects.create(post=self.post, user=self.reactor, reaction_type='LIKE')
        with self.assertRaises(Exception):
            Reaction.objects.create(post=self.post, user=self.reactor, reaction_type='LOVE')


class CommentModelTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username='author2', password='test1234')
        self.post = Post.objects.create(author=self.author, title='Post', content='...')

    def test_comment_with_text_only_is_valid(self):
        comment = Comment(post=self.post, author=self.author, content='Nice work!')
        comment.full_clean()  # should not raise

    def test_comment_with_neither_text_nor_image_is_invalid(self):
        comment = Comment(post=self.post, author=self.author, content='')
        with self.assertRaises(Exception):
            comment.full_clean()


class FeedAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.alice = User.objects.create_user(username='alice2', password='test1234')
        self.bob = User.objects.create_user(username='bob2', password='test1234')

    def auth_as(self, user):
        self.client.force_authenticate(user=user)

    # ---- Post creation ----

    def test_authenticated_user_can_create_post(self):
        self.auth_as(self.alice)
        response = self.client.post('/api/posts/', {
            'title': 'Looking for a designer',
            'content': 'Need help with UI',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['author_username'], 'alice2')

    def test_unauthenticated_user_cannot_create_post(self):
        response = self.client.post('/api/posts/', {
            'title': 'Should fail',
            'content': 'No auth',
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_anyone_can_read_posts(self):
        Post.objects.create(author=self.alice, title='Public post', content='...')
        response = self.client.get('/api/posts/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---- Reactions ----

    def test_react_to_post(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        response = self.client.post(f'/api/posts/{post.pk}/react/', {'reaction_type': 'LOVE'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['my_reaction'], 'LOVE')
        self.assertEqual(response.data['reaction_counts']['LOVE'], 1)

    def test_changing_reaction_updates_not_duplicates(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        self.client.post(f'/api/posts/{post.pk}/react/', {'reaction_type': 'LIKE'})
        response = self.client.post(f'/api/posts/{post.pk}/react/', {'reaction_type': 'HAHA'})

        self.assertEqual(response.data['my_reaction'], 'HAHA')
        self.assertEqual(response.data['reaction_counts']['LIKE'], 0)
        self.assertEqual(response.data['reaction_counts']['HAHA'], 1)
        self.assertEqual(Reaction.objects.filter(post=post, user=self.bob).count(), 1)  # still just 1 row

    def test_invalid_reaction_type_rejected(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        response = self.client.post(f'/api/posts/{post.pk}/react/', {'reaction_type': 'NOT_REAL'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unreact_removes_reaction(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        self.client.post(f'/api/posts/{post.pk}/react/', {'reaction_type': 'LIKE'})
        response = self.client.post(f'/api/posts/{post.pk}/unreact/')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['my_reaction'])
        self.assertFalse(Reaction.objects.filter(post=post, user=self.bob).exists())

    def test_unreact_without_existing_reaction_fails(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        response = self.client.post(f'/api/posts/{post.pk}/unreact/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # ---- Comments ----

    def test_comment_with_text_only(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        response = self.client.post(f'/api/posts/{post.pk}/comment/', {'content': 'Interested!'})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content'], 'Interested!')
        self.assertIsNone(response.data['image'])

    def test_comment_with_image_only(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        image = make_test_image()
        response = self.client.post(
            f'/api/posts/{post.pk}/comment/',
            {'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIsNotNone(response.data['image'])

    def test_comment_with_text_and_image_together(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        image = make_test_image()
        response = self.client.post(
            f'/api/posts/{post.pk}/comment/',
            {'content': 'Check this out', 'image': image},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['content'], 'Check this out')
        self.assertIsNotNone(response.data['image'])

    def test_comment_with_neither_text_nor_image_fails(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        response = self.client.post(f'/api/posts/{post.pk}/comment/', {})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_rejects_non_image_file(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        fake_pdf = SimpleUploadedFile('doc.pdf', b'%PDF-1.4 fake content', content_type='application/pdf')
        response = self.client.post(
            f'/api/posts/{post.pk}/comment/',
            {'content': 'here is a file', 'image': fake_pdf},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_comment_count_reflected_on_post(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        self.client.post(f'/api/posts/{post.pk}/comment/', {'content': 'First'})
        self.client.post(f'/api/posts/{post.pk}/comment/', {'content': 'Second'})

        response = self.client.get(f'/api/posts/{post.pk}/')
        self.assertEqual(response.data['comment_count'], 2)

    # ---- Permissions ----

    def test_non_author_cannot_delete_post(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.bob)

        response = self.client.delete(f'/api/posts/{post.pk}/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_author_can_delete_own_post(self):
        post = Post.objects.create(author=self.alice, title='Post', content='...')
        self.auth_as(self.alice)

        response = self.client.delete(f'/api/posts/{post.pk}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


class QuestionAcceptedAnswerTests(APITestCase):
        def setUp(self):
            self.asker = User.objects.create_user('asker', password='pw12345!')
            self.helper = User.objects.create_user('helper', password='pw12345!')
            self.question = Post.objects.create(
                author=self.asker, title='How to X?', content='...',
                post_type=Post.PostType.QUESTION,
            )
            self.answer = Comment.objects.create(
                post=self.question, author=self.helper, content='Do Y.',
            )
            self.url = f'/api/posts/{self.question.id}/accept-comment/'  # TODO: match your URL

        def test_author_can_accept_answer(self):
            self.client.force_authenticate(self.asker)
            r = self.client.post(self.url, {'comment_id': self.answer.id})
            self.assertEqual(r.status_code, 200)
            self.question.refresh_from_db()
            self.assertEqual(self.question.accepted_comment_id, self.answer.id)

        def test_other_user_cannot_accept(self):
            self.client.force_authenticate(self.helper)
            r = self.client.post(self.url, {'comment_id': self.answer.id})
            self.assertEqual(r.status_code, 403)
            self.question.refresh_from_db()
            self.assertIsNone(self.question.accepted_comment)

        def test_comment_from_other_post_returns_404(self):
            other = Post.objects.create(
                author=self.asker, title='Other', content='...',
                post_type=Post.PostType.QUESTION,
            )
            foreign = Comment.objects.create(post=other, author=self.helper, content='x')
            self.client.force_authenticate(self.asker)
            r = self.client.post(self.url, {'comment_id': foreign.id})
            self.assertEqual(r.status_code, 404)

        def test_normal_post_cannot_have_accepted_answer(self):
            normal = Post.objects.create(author=self.asker, title='Hi', content='...')
            c = Comment.objects.create(post=normal, author=self.helper, content='x')
            self.client.force_authenticate(self.asker)
            r = self.client.post(
                f'/api/posts/{normal.id}/accept-comment/', {'comment_id': c.id},
            )
            self.assertEqual(r.status_code, 400)

        def test_deleting_accepted_comment_clears_pointer(self):
            self.question.accept_comment(self.answer, self.asker)
            self.answer.delete()
            self.question.refresh_from_db()
            self.assertIsNone(self.question.accepted_comment)
