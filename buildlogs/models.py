from django.db import models
from django.contrib.auth.models import User
from projects.models import Project


class BuildLogEntry(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='build_logs')
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='build_log_entries')
    title = models.CharField(max_length=200)
    content = models.TextField()
    image = models.ImageField(upload_to='build_log_images/', null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.project.title}] {self.title}"