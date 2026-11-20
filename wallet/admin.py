from django.contrib import admin
from .models import Wallet, LedgerEntry


@admin.register(Wallet)
class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username',)
    readonly_fields = ('balance', 'updated_at')  # không cho sửa tay balance qua admin


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ('wallet', 'entry_type', 'amount', 'balance_after', 'reference_id', 'created_at')
    list_filter = ('entry_type', 'created_at')
    search_fields = ('wallet__user__username', 'reference_id')
    readonly_fields = [f.name for f in LedgerEntry._meta.fields]  # toàn bộ field readonly

    def has_add_permission(self, request):
        return False  # không cho tạo tay qua admin — chỉ tạo qua add_credit()

    def has_delete_permission(self, request, obj=None):
        return False  # không cho xóa — ledger phải immutable

    def has_change_permission(self, request, obj=None):
        return False  # không cho sửa