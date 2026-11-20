from rest_framework import serializers
from .models import BuildLogEntry


class BuildLogEntrySerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    project_title = serializers.CharField(source='project.title', read_only=True)

    class Meta:
        model = BuildLogEntry
        fields = [
            'id', 'project', 'project_title', 'author', 'author_username',
            'title', 'content', 'image', 'created_at',
        ]
        read_only_fields = ['author', 'created_at']