from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'username', 'tier', 'is_active', 'date_joined']
    list_filter = ['tier', 'is_active']
    search_fields = ['email', 'username']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Subscription', {'fields': ('tier', 'email_alerts_enabled', 'browser_alerts_enabled')}),
    )
    ordering = ['-date_joined']
