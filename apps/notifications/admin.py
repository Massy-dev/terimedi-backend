from django.contrib import admin

# Register your models here.
from django.contrib import admin
from .models import DeviceToken, Notification, NotificationPreference


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'token_preview', 'is_active', 'created_at']
    list_filter = ['platform', 'is_active', 'created_at']
    search_fields = ['user__username', 'token']
    readonly_fields = ['created_at', 'updated_at']
    
    def token_preview(self, obj):
        """Afficher un aperçu du token"""
        return f"{obj.token[:30]}..." if obj.token else ""
    token_preview.short_description = "Token"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'notification_type',
        'title',
        'channel',
        'is_sent',
        'is_read',
        'created_at'
    ]
    list_filter = [
        'notification_type',
        'channel',
        'is_sent',
        'is_read',
        'created_at'
    ]
    search_fields = ['user__username', 'title', 'body']
    readonly_fields = ['created_at', 'sent_at', 'read_at']
    
    fieldsets = (
        ('Informations', {
            'fields': ('user', 'notification_type', 'title', 'body', 'data')
        }),
        ('Configuration', {
            'fields': ('channel',)
        }),
        ('Statut', {
            'fields': ('is_sent', 'is_read', 'sent_at', 'read_at', 'error_message')
        }),
        ('Dates', {
            'fields': ('created_at',)
        }),
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = [
        'user',
        'enable_fcm',
        'enable_websocket',
        'updated_at'
    ]
    list_filter = ['enable_fcm', 'enable_websocket', 'updated_at']
    search_fields = ['user__username']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Utilisateur', {
            'fields': ('user',)
        }),
        ('Types de notifications', {
            'fields': (
                'quote_sent',
                'quote_accepted',
                'quote_rejected',
                'order_created',
                'order_confirmed',
                'order_preparing',
                'order_ready',
                'order_delivering',
                'order_delivered',
                'order_cancelled',
                'general'
            )
        }),
        ('Canaux', {
            'fields': ('enable_fcm', 'enable_websocket')
        }),
        ('Dates', {
            'fields': ('updated_at',)
        }),
    )