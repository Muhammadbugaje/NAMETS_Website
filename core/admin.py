from unfold.admin import ModelAdmin, TabularInline
from django.contrib import admin
from .models import SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(ModelAdmin):
    list_display = ['tutor_applications_open', 'membership_applications_open', 'tutor_evaluations_open', 'islamiyya_registration_open']
    # You can add other fields as needed

from django.contrib import admin
from unfold.admin import ModelAdmin
from .models import EmailLog, DailyEmailCounter

@admin.register(EmailLog)
class EmailLogAdmin(ModelAdmin):
    list_display = ('recipient_email', 'subject', 'category', 'provider', 'status', 'sent_at')
    list_filter = ('status', 'provider', 'category')
    search_fields = ('recipient_email', 'subject', 'error_message')
    readonly_fields = ('recipient_email', 'subject', 'category', 'provider', 'status', 'error_message', 'sent_at')
    ordering = ('-sent_at',)

@admin.register(DailyEmailCounter)
class DailyEmailCounterAdmin(ModelAdmin):
    list_display = ('date', 'brevo_count', 'gmail_count')
    readonly_fields = ('date', 'brevo_count', 'gmail_count')


from django.contrib import admin
from django.utils.html import format_html
from .models import HeroSlide


from django.contrib import admin
from django.utils.html import format_html
from .models import HeroSlide


@admin.register(HeroSlide)
class HeroSlideAdmin(admin.ModelAdmin):
    list_display = ('preview', 'title', 'order', 'has_buttons_display', 'is_active', 'active_window')
    list_display_links = ('preview', 'title')
    list_editable = ('order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('title', 'subtitle')
    ordering = ('order', '-created_at')

    fieldsets = (
        ('Content', {
            'fields': ('title', 'subtitle'),
            'description': 'Leave any field blank to hide it on the slide.',
        }),
        ('Images', {
            'fields': ('desktop_image', 'mobile_image'),
            'description': 'Desktop 16:9 (1920×1080) · Mobile 4:5 (1080×1350). WebP recommended.',
        }),
        ('Primary Button (optional)', {
            'fields': ('primary_button_text', 'primary_button_url'),
            'classes': ('collapse',),
            'description': 'Gold button. Leave both blank to hide.',
        }),
        ('Secondary Button (optional)', {
            'fields': ('secondary_button_text', 'secondary_button_url'),
            'classes': ('collapse',),
            'description': 'Ghost/glass button. Leave both blank to hide.',
        }),
        ('Scheduling', {
            'fields': ('is_active', 'order', 'active_from', 'active_until'),
            'description': 'Leave dates blank to run indefinitely.',
        }),
    )

    # ---------- list columns ----------
    @admin.display(description='')
    def preview(self, obj):
        url = obj.desktop_url or obj.mobile_url
        if not url:
            return '—'
        return format_html(
            '<img src="{}" style="height:42px;width:74px;'
            'object-fit:cover;border-radius:6px;'
            'box-shadow:0 2px 6px rgba(0,0,0,0.15);" />',
            url,
        )

    @admin.display(description='Buttons')
    def has_buttons_display(self, obj):
        bits = []
        if obj.has_primary_button:
            bits.append('🟡 Primary')
        if obj.has_secondary_button:
            bits.append('⚪ Secondary')
        return ' · '.join(bits) if bits else '—'

    @admin.display(description='Active window')
    def active_window(self, obj):
        if not obj.active_from and not obj.active_until:
            return 'Always'
        start = obj.active_from.strftime('%b %d, %Y') if obj.active_from else '…'
        end   = obj.active_until.strftime('%b %d, %Y') if obj.active_until else '…'
        return f'{start} → {end}'