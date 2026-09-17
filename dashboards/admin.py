from django.contrib import admin
from .models import Message, MessageRecipient


class MessageRecipientInline(admin.TabularInline):
    model = MessageRecipient
    extra = 0
    raw_id_fields = ('user',)
    readonly_fields = ('delivered_at', 'read_at')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('subject', 'sender', 'target_type', 'target_label',
                    'is_pinned', 'sent_at', 'recipient_count')
    list_filter = ('target_type', 'is_pinned', 'sent_at')
    search_fields = ('subject', 'body', 'sender__email')
    raw_id_fields = ('sender',)
    readonly_fields = ('sent_at',)
    inlines = [MessageRecipientInline]

    @admin.display(description='Recipients')
    def recipient_count(self, obj):
        return obj.recipients.count()


@admin.register(MessageRecipient)
class MessageRecipientAdmin(admin.ModelAdmin):
    list_display = ('message', 'user', 'is_read', 'is_deleted', 'delivered_at')
    list_filter = ('is_read', 'is_deleted')
    search_fields = ('user__email', 'message__subject')
    raw_id_fields = ('user', 'message')