from rest_framework import generics, permissions
from .models import Wallet, LedgerEntry
from .serializers import WalletSerializer, LedgerEntrySerializer


class MyWalletView(generics.RetrieveAPIView):
    serializer_class = WalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        wallet, _ = Wallet.objects.get_or_create(user=self.request.user)
        return wallet


class MyLedgerView(generics.ListAPIView):
    serializer_class = LedgerEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LedgerEntry.objects.filter(wallet__user=self.request.user)


from django.shortcuts import render

# Create your views here.
