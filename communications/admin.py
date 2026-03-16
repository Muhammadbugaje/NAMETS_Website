from django.contrib import admin
from .models import Announcement, PrayerSchedule, Subscriber, DonationCampaign, MosqueInfo, MosqueRule
from django.urls import reverse
from django.utils.html import format_html
from django.shortcuts import redirect
from django.contrib import messages
from utils.admin_helpers import cloudinary_thumbnail

# Register your models here.

@admin.register(Announcement)
# customize how admin display list items, makes it easier than just liting them
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'title', 'category', 'is_pinned', 'publish_at', 'is_active', 'send_email')
    list_filter = ('category', 'is_pinned', 'is_active', 'send_email') # sidebar filters
    search_fields = ('title', 'content') 
    prepopulated_fields = {'slug': ('title',)}
    actions = ['mark_send_email'] # bulk action to select emails for sending

    # update email status of sent email
    def mark_send_email(self, request, queryset):
        queryset.update(send_email=True)
    mark_send_email.short_description = "Mark selected announcements for email sending"

    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Image'


@admin.register(PrayerSchedule)
class PrayerScheduleAdmin(admin.ModelAdmin):
    list_display = ('date', 'fajr_adhan', 'dhuhr_adhan', 'asr_adhan', 'maghrib_adhan', 'isha_adhan', 'is_active')
    list_filter = ('is_active',)
    date_hierarchy = 'date'


@admin.register(DonationCampaign)
class DonationCampaignAdmin(admin.ModelAdmin):
    list_display = ('title', 'goal_amount', 'is_active', 'created_at')
    list_filter = ('is_active',)
    
    
@admin.register(MosqueInfo)
class MosqueInfoAdmin(admin.ModelAdmin):
    list_display = ('location', 'imam_name', 'contact_email', 'contact_phone')

@admin.register(MosqueRule)
class MosqueRuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'order', 'is_active')
    list_editable = ('order', 'is_active')
    
def send_custom_message_action(modeladmin, request, queryset):
    # Store selected subscriber IDs in session or pass via URL
    request.session['selected_subscriber_ids'] = list(queryset.values_list('id', flat=True))
    return redirect('admin_send_custom_message')
send_custom_message_action.short_description = "Send custom message to selected subscribers"    
    
@admin.register(Subscriber)
class SubscriberAdmin(admin.ModelAdmin):
    list_display = ('email', 'is_verified', 'notify_announcements', 'notify_events', 'notify_prayer_changes', 'subscribed_at', 'is_active', 'unsubscribe_link')
    list_filter = ('is_verified', 'notify_announcements', 'notify_events', 'notify_prayer_changes', 'is_active')
    search_fields = ('email',)
    actions = [send_custom_message_action]

    def unsubscribe_link(self, obj):
        url = reverse('communications:unsubscribe', args=[obj.token])
        return format_html('<a href="{}" target="_blank">Unsubscribe link</a>', url)
    unsubscribe_link.short_description = 'Unsubscribe URL'