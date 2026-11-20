from rest_framework import serializers
from .models import Wallet, LedgerEntry


class WalletSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wallet
        fields = ['id', 'balance', 'updated_at']


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ['id', 'wallet', 'entry_type', 'amount', 'balance_after', 'reference_id', 'note', 'created_at']