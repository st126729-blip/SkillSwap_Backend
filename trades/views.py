from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Q
from .models import Trade
from .serializers import TradeSerializer
from .permissions import IsTradeParticipant, IsTradeRecipient


class TradeViewSet(viewsets.ModelViewSet):
    serializer_class = TradeSerializer
    permission_classes = [permissions.IsAuthenticated, IsTradeParticipant]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Trade.objects.all()
        return Trade.objects.filter(Q(initiator=user) | Q(recipient=user))

    def perform_create(self, serializer):
        serializer.save(initiator=self.request.user)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsTradeRecipient])
    def accept(self, request, pk=None):
        trade = self.get_object()
        try:
            trade.accept()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TradeSerializer(trade).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsTradeRecipient])
    def reject(self, request, pk=None):
        trade = self.get_object()
        try:
            trade.reject()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TradeSerializer(trade).data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsTradeParticipant])
    def cancel(self, request, pk=None):
        trade = self.get_object()
        if trade.initiator != request.user and not request.user.is_staff:
            return Response({'detail': 'Only the initiator can cancel this trade.'}, status=status.HTTP_403_FORBIDDEN)
        try:
            trade.cancel()
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(TradeSerializer(trade).data)