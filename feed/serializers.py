from rest_framework import serializers
from .models import Post, Reaction, Comment


class CommentSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    # True khi người bình luận chính là tác giả bài viết → frontend hiện nhãn "Tác giả" cạnh tên
    is_post_author = serializers.SerializerMethodField()
    # True khi comment này là câu trả lời được chấp nhận của câu hỏi
    is_accepted = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            'id', 'post', 'parent', 'author', 'author_username', 'is_post_author',
            'is_accepted', 'content', 'image', 'created_at',
        ]
        read_only_fields = ['post', 'parent', 'author', 'created_at']

    def get_is_post_author(self, obj):
        return obj.author_id == obj.post.author_id

    def get_is_accepted(self, obj):
        return obj.post.accepted_comment_id == obj.id

    def validate(self, data):
        content = data.get('content', '').strip() if data.get('content') else ''
        image = data.get('image')
        if not content and not image:
            raise serializers.ValidationError("Comment must have either text or an image.")
        return data

    def validate_image(self, value):
        if value:
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if value.content_type not in allowed_types:
                raise serializers.ValidationError("Only image files (jpg, png, gif, webp) are allowed.")
            max_size_mb = 5
            if value.size > max_size_mb * 1024 * 1024:
                raise serializers.ValidationError(f"Image must be smaller than {max_size_mb}MB.")
        return value


class PostSerializer(serializers.ModelSerializer):
    author_username = serializers.CharField(source='author.username', read_only=True)
    reaction_counts = serializers.SerializerMethodField()
    my_reaction = serializers.SerializerMethodField()
    comment_count = serializers.SerializerMethodField()
    # Danh sách phẳng (gồm cả câu trả lời); mỗi comment có 'parent' để frontend dựng cây
    comments = CommentSerializer(many=True, read_only=True)

    class Meta:
        model = Post
        fields = [
            'id', 'author', 'author_username', 'title', 'content',
            'post_type', 'accepted_comment',
            'related_project', 'reaction_counts', 'my_reaction', 'comment_count',
            'comments', 'created_at', 'updated_at',
        ]
        # accepted_comment chỉ được đổi qua action accept-comment, không qua PATCH
        read_only_fields = ['author', 'accepted_comment', 'created_at', 'updated_at']

    def get_reaction_counts(self, obj):
        """Trả về dạng {'LIKE': 3, 'LOVE': 1, 'HAHA': 0, ...} — đếm từng loại."""
        counts = {choice[0]: 0 for choice in Reaction.ReactionType.choices}
        for r in obj.reactions.values_list('reaction_type', flat=True):
            counts[r] += 1
        return counts

    def get_my_reaction(self, obj):
        """Trả về loại reaction của chính user đang gọi API, hoặc null nếu chưa react."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        reaction = obj.reactions.filter(user=request.user).first()
        return reaction.reaction_type if reaction else None

    def get_comment_count(self, obj):
        return obj.comments.count()