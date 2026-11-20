from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Avg, Q
from django.contrib.auth.models import User
from .models import Vouch
from .serializers import VouchSerializer, ReputationSummarySerializer


class VouchViewSet(viewsets.ModelViewSet):
    queryset = Vouch.objects.all()
    serializer_class = VouchSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]

    def get_serializer_context(self):
        return {'request': self.request}

    def get_queryset(self):
        qs = Vouch.objects.all()
        vouchee_id = self.request.query_params.get('vouchee')
        if vouchee_id:
            qs = qs.filter(vouchee_id=vouchee_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(voucher=self.request.user)


class ReputationSummaryView(APIView):
    """GET /api/reputation/<user_id>/ — điểm tổng hợp reputation của 1 user."""
    permission_classes = [permissions.AllowAny]

    def get(self, request, user_id):
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        vouches = Vouch.objects.filter(vouchee=user)
        aggregates = vouches.aggregate(
            avg_technical_quality=Avg('technical_quality'),
            avg_reliability=Avg('reliability'),
        )

        data = {
            'user_id': user.id,
            'username': user.username,
            'vouch_count': vouches.count(),
            'avg_technical_quality': aggregates['avg_technical_quality'],
            'avg_reliability': aggregates['avg_reliability'],
        }
        return Response(ReputationSummarySerializer(data).data)