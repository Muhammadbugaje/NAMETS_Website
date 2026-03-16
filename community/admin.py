from django.contrib import admin
from .models import Patron, ExecutiveYear, Executive, Developer, Question, Answer, AboutPage
from utils.admin_helpers import cloudinary_thumbnail

# Register your models here.

class ExecutiveInline(admin.TabularInline):
    model = Executive
    extra = 1

@admin.register(Patron)
class PatronAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'name', 'designation', 'hierarchy_order', 'is_active')
    list_editable = ('hierarchy_order', 'is_active')
    search_fields = ('name', 'designation')

    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.image)
    image_thumbnail.short_description = 'Photo'

@admin.register(ExecutiveYear)
class ExecutiveYearAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'year_label', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')
    inlines = [ExecutiveInline]

    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.photo)
    image_thumbnail.short_description = 'Photo'    

@admin.register(Executive)
class ExecutiveAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'name', 'role', 'year', 'display_order', 'is_active')
    list_filter = ('year', 'is_active')
    list_editable = ('display_order', 'is_active')
    search_fields = ('name', 'role')

    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.photo)
    image_thumbnail.short_description = 'Photo'

@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ('image_thumbnail', 'name', 'role', 'display_order', 'is_active')
    list_editable = ('display_order', 'is_active')

    def image_thumbnail(self, obj):
        return cloudinary_thumbnail(obj.photo)
    image_thumbnail.short_description = 'Photo'

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'is_public', 'submitted_at')
    list_filter = ('is_public', 'category')
    search_fields = ('name', 'question_text')
    actions = ['mark_public']

    def mark_public(self, request, queryset):
        queryset.update(is_public=True)
    mark_public.short_description = "Mark selected questions as public"

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ('question', 'responded_by', 'responded_at')
    search_fields = ('question__question_text',)

@admin.register(AboutPage)
class AboutPageAdmin(admin.ModelAdmin):
    # singleton – only one instance allowed
    def has_add_permission(self, request):
        if AboutPage.objects.exists():
            return False
        return super().has_add_permission(request)