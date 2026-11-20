from django.db import models
from django.contrib.auth.models import User
from projects.models import Project
from django.core.exceptions import ValidationError


class Post(models.Model):
    class PostType(models.TextChoices):
        POST = 'POST', 'Post'
        QUESTION = 'QUESTION', 'Question'

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
    title = models.CharField(max_length=200)
    content = models.TextField()
    post_type = models.CharField(
        max_length=10, choices=PostType.choices, default=PostType.POST,
    )
    accepted_comment = models.ForeignKey(
        'Comment', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='+',
    )
    related_project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='posts',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} by {self.author.username}"

    def clean(self):
        if self.accepted_comment_id:
            if self.post_type != self.PostType.QUESTION:
                raise ValidationError("Only questions can have an accepted answer.")
            if self.accepted_comment.post_id != self.pk:
                raise ValidationError("The accepted answer must belong to this question.")

    def accept_comment(self, comment, by_user):
        """Mark one comment as the accepted answer. Only the author may do this."""
        if by_user != self.author:
            raise PermissionError("Only the author can accept an answer.")
        if self.post_type != self.PostType.QUESTION:
            raise ValidationError("Only questions can have an accepted answer.")
        if comment.post_id != self.pk:
            raise ValidationError("The comment does not belong to this question.")
        self.accepted_comment = comment
        self.save(update_fields=['accepted_comment', 'updated_at'])


class Reaction(models.Model):
    class ReactionType(models.TextChoices):
        LIKE = 'LIKE', '👍 Like'
        LOVE = 'LOVE', '❤️ Love'
        HAHA = 'HAHA', '😂 Haha'
        WOW = 'WOW', '😮 Wow'
        SAD = 'SAD', '😢 Sad'
        ANGRY = 'ANGRY', '😡 Angry'

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_reactions')
    reaction_type = models.CharField(max_length=10, choices=ReactionType.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('post', 'user')

    def __str__(self):
        return f"{self.user.username} reacted {self.reaction_type} to '{self.post.title}'"


ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif', 'webp']

def validate_image_extension(value):
    ext = value.name.split('.')[-1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Only image files are allowed ({', '.join(ALLOWED_IMAGE_EXTENSIONS)}).")


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    content = models.TextField(blank=True)
    parent = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.CASCADE,
        related_name='replies',
    )
    image = models.ImageField(
        upload_to='comment_images/', null=True, blank=True,
        validators=[validate_image_extension],
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.author.username} on '{self.post.title}'"

    def clean(self):
        if not self.content and not self.image:
            raise ValidationError("Comment must have either text or an image.")