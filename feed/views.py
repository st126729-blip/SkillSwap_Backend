from django.core.exceptions import ValidationError as DjangoValidationError
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Post, Reaction, Comment
from .serializers import PostSerializer, CommentSerializer
from .permissions import IsAuthorOrReadOnly


class PostViewSet(viewsets.ModelViewSet):
    queryset = Post.objects.all()
    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        # Giảm số query cho is_post_author / is_accepted trong CommentSerializer
        return (
            Post.objects
            .select_related('author', 'accepted_comment')
            .prefetch_related('comments__author', 'reactions')
        )

    def get_serializer_context(self):
        return {'request': self.request}

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def react(self, request, pk=None):
        """Body: {"reaction_type": "LOVE"} — tạo mới hoặc đổi loại reaction đã có."""
        post = self.get_object()
        reaction_type = request.data.get('reaction_type', '').upper()

        valid_types = [choice[0] for choice in Reaction.ReactionType.choices]
        if reaction_type not in valid_types:
            return Response(
                {'detail': f'Invalid reaction_type. Must be one of: {valid_types}'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        Reaction.objects.update_or_create(
            post=post, user=request.user,
            defaults={'reaction_type': reaction_type},
        )
        return Response(PostSerializer(post, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def unreact(self, request, pk=None):
        """Bỏ hẳn reaction (không còn cảm xúc nào)."""
        post = self.get_object()
        deleted, _ = Reaction.objects.filter(post=post, user=request.user).delete()
        if not deleted:
            return Response({'detail': 'You have not reacted to this post.'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PostSerializer(post, context={'request': request}).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated],
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def comment(self, request, pk=None):
        """Body: content và/hoặc image; thêm "parent": <id comment> để trả lời một bình luận."""
        post = self.get_object()

        parent = None
        parent_id = request.data.get('parent')
        if parent_id not in (None, '', 'null'):
            try:
                parent = Comment.objects.get(pk=parent_id, post=post)
            except (Comment.DoesNotExist, ValueError, TypeError):
                return Response(
                    {'detail': 'Parent comment not found on this post.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = CommentSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(post=post, author=request.user, parent=parent)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], url_path='accept-comment',
            permission_classes=[permissions.IsAuthenticated])
    def accept_comment(self, request, pk=None):
        """Body: {"comment_id": <id>} — chỉ tác giả câu hỏi được chọn câu trả lời."""
        post = self.get_object()
        try:
            comment_id = int(request.data.get('comment_id'))
        except (TypeError, ValueError):
            return Response({'detail': 'comment_id is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

        comment = get_object_or_404(post.comments, pk=comment_id)  # comment bài khác -> 404
        try:
            post.accept_comment(comment, request.user)
        except PermissionError as e:
            return Response({'detail': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except DjangoValidationError as e:
            return Response({'detail': e.messages}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PostSerializer(post, context={'request': request}).data)


class CommentViewSet(viewsets.ModelViewSet):
    queryset = Comment.objects.all()
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsAuthorOrReadOnly]
    http_method_names = ['get', 'patch', 'delete']