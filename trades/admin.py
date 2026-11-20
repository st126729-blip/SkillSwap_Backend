from django.contrib import admin
from django.contrib import messages
from .models import Trade


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'initiator', 'recipient', 'credit_amount',
        'status', 'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('initiator__username', 'recipient__username')
    readonly_fields = ('status', 'created_at', 'updated_at')

    actions = ['accept_trades', 'reject_trades', 'cancel_trades']

    @admin.action(description='Accept selected trades')
    def accept_trades(self, request, queryset):
        success_count = 0
        for trade in queryset:
            try:
                trade.accept()
                success_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Trade #{trade.pk} failed: {e}",
                    level=messages.ERROR,
                )
        if success_count:
            self.message_user(request, f"{success_count} trade(s) accepted.")

    @admin.action(description='Reject selected trades')
    def reject_trades(self, request, queryset):
        success_count = 0
        for trade in queryset:
            try:
                trade.reject()
                success_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Trade #{trade.pk} failed: {e}",
                    level=messages.ERROR,
                )
        if success_count:
            self.message_user(request, f"{success_count} trade(s) rejected.")

    @admin.action(description='Cancel selected trades')
    def cancel_trades(self, request, queryset):
        success_count = 0
        for trade in queryset:
            try:
                trade.cancel()
                success_count += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Trade #{trade.pk} failed: {e}",
                    level=messages.ERROR,
                )
        if success_count:
            self.message_user(request, f"{success_count} trade(s) cancelled.")