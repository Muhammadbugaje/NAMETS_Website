# business/admin.py
# Business App — Complete Unfold Admin Registration

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from django.db.models import Sum, Count, Q
from unfold.admin import ModelAdmin
from unfold.decorators import action
from unfold.contrib.forms.widgets import WysiwygWidget

from .models import (
    CollectionCenter,
    BankAccount,
    Transaction,
    EquipmentItem,
    EquipmentBorrow,
    ShopItem,
    ShopOrder,
    FreeClaim,
    SellableForm,
    FormPurchase,
    BookingListing,
    Booking,
)


# ============================================================
# INLINE CLASSES
# ============================================================

class TransactionCorrectionInline(admin.TabularInline):
    """Show correction entries inline on the original transaction."""
    model = Transaction
    fk_name = 'corrects'
    fields = ['id', 'category', 'amount', 'description', 'date', 'created_by']
    readonly_fields = ['id', 'category', 'amount', 'description', 'date', 'created_by']
    extra = 0
    can_delete = False
    max_num = 0
    verbose_name = "Correction Entry"
    verbose_name_plural = "Correction Entries"
    classes = ['collapse']


class EquipmentBorrowInline(admin.TabularInline):
    """Show borrow history inline on equipment item."""
    model = EquipmentBorrow
    fields = ['borrower_name', 'borrowed_at', 'expected_return_date', 'status', 'is_overdue_display']
    readonly_fields = ['borrowed_at', 'is_overdue_display']
    extra = 0
    can_delete = False
    verbose_name = "Borrow Record"
    verbose_name_plural = "Borrow History"
    classes = ['collapse']

    def is_overdue_display(self, obj):
        if obj.is_overdue():
            return format_html('<span style="color: #dc3545;">🔴 Overdue</span>')
        return format_html('<span style="color: #28a745;">✅ On Time</span>')
    is_overdue_display.short_description = "Status"


class ShopOrderInline(admin.TabularInline):
    """Show orders inline on shop item."""
    model = ShopOrder
    fields = ['buyer_name', 'quantity', 'total_amount', 'status', 'created_at']
    readonly_fields = ['created_at']
    extra = 0
    can_delete = False
    verbose_name = "Order"
    verbose_name_plural = "Orders"
    classes = ['collapse']


class FreeClaimInline(admin.TabularInline):
    """Show free claims inline on shop item."""
    model = FreeClaim
    fields = ['claimant_name', 'status', 'created_at']
    readonly_fields = ['created_at']
    extra = 0
    can_delete = False
    verbose_name = "Free Claim"
    verbose_name_plural = "Free Claims"
    classes = ['collapse']


class BookingInline(admin.TabularInline):
    """Show bookings inline on booking listing."""
    model = Booking
    fields = ['booker_name', 'quantity', 'total_amount', 'status', 'created_at']
    readonly_fields = ['created_at']
    extra = 0
    can_delete = False
    verbose_name = "Booking"
    verbose_name_plural = "Bookings"
    classes = ['collapse']


class FormPurchaseInline(admin.TabularInline):
    """Show form purchases inline on sellable form."""
    model = FormPurchase
    fields = ['buyer_name', 'amount_paid', 'status', 'access_code', 'created_at']
    readonly_fields = ['access_code', 'created_at']
    extra = 0
    can_delete = False
    verbose_name = "Purchase"
    verbose_name_plural = "Purchases"
    classes = ['collapse']


# ============================================================
# ADMIN REGISTRATIONS
# ============================================================

@admin.register(CollectionCenter)
class CollectionCenterAdmin(ModelAdmin):
    list_display = ['name', 'location', 'contact_person', 'contact_phone', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'location', 'contact_person']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'location', 'is_active'),
        }),
        ('Contact Details', {
            'fields': ('contact_person', 'contact_phone'),
            'classes': ('collapse',),
        }),
        ('Hours & Additional Info', {
            'fields': ('opening_hours',),
            'classes': ('collapse',),
        }),
    )


@admin.register(BankAccount)
class BankAccountAdmin(ModelAdmin):
    list_display = ['name', 'account_type', 'account_number', 'bank_name', 'current_balance_display', 'is_public']
    list_filter = ['account_type', 'is_active', 'is_public']
    search_fields = ['name', 'account_number', 'bank_name']
    readonly_fields = ['current_balance', 'created_at', 'updated_at']
    fieldsets = (
        ('Account Details', {
            'fields': ('name', 'account_type', 'account_number', 'bank_name'),
        }),
        ('Balance & Status', {
            'fields': ('current_balance', 'is_active', 'is_public', 'description'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def current_balance_display(self, obj):
        return f"₦{obj.current_balance:,.2f}"
    current_balance_display.short_description = "Balance"


@admin.register(Transaction)
class TransactionAdmin(ModelAdmin):
    list_display = ['date', 'category_display', 'amount_display', 'account', 'description_short', 'is_correction_icon', 'created_by']
    list_filter = ['category', 'account', 'is_correction', 'date']
    search_fields = ['description', 'internal_note']
    readonly_fields = ['previous_balance', 'new_balance', 'is_correction']
    inlines = [TransactionCorrectionInline]
    fieldsets = (
        ('Transaction Details', {
            'fields': ('account', 'category', 'amount', 'description', 'internal_note', 'date', 'receipt_attachment'),
        }),
        ('Audit Trail', {
            'fields': ('previous_balance', 'new_balance', 'is_correction', 'corrects', 'created_by'),
            'classes': ('collapse',),
        }),
    )

    def category_display(self, obj):
        return obj.get_category_display()
    category_display.short_description = "Category"

    def amount_display(self, obj):
        if obj.is_income():
            color = '#28a745'
            sign = '+'
        else:
            color = '#dc3545'
            sign = '-'
        return format_html(f'<span style="color: {color}; font-weight: 600;">{sign}₦{obj.amount:,.2f}</span>')
    amount_display.short_description = "Amount"

    def description_short(self, obj):
        return obj.description[:50] + ('...' if len(obj.description) > 50 else '')
    description_short.short_description = "Description"

    def is_correction_icon(self, obj):
        if obj.is_correction:
            return format_html('<span style="color: #fd7e14;">⚠️ Correction</span>')
        return format_html('<span style="color: #28a745;">✓ Original</span>')
    is_correction_icon.short_description = "Type"

    @action(description="Mark selected as corrections", permissions=['change'])
    def mark_as_correction(self, request, queryset):
        count = queryset.update(is_correction=True)
        self.message_user(request, f"✅ {count} transaction(s) marked as corrections.")

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(EquipmentItem)
class EquipmentItemAdmin(ModelAdmin):
    list_display = ['name', 'condition_badge', 'quantity_display', 'location', 'contact_person', 'is_active']
    list_filter = ['condition', 'is_active', 'location']
    search_fields = ['name', 'description', 'serial_number']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [EquipmentBorrowInline]
    fieldsets = (
        ('Item Details', {
            'fields': ('name', 'description', 'serial_number'),
        }),
        ('Quantity & Condition', {
            'fields': ('quantity', 'available_quantity', 'condition'),
        }),
        ('Location & Contact', {
            'fields': ('location', 'contact_person'),
        }),
        ('Status & Image', {
            'fields': ('is_active', 'image', 'notes'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def condition_badge(self, obj):
        colors = {
            'excellent': '#28a745',
            'good': '#17a2b8',
            'fair': '#ffc107',
            'poor': '#fd7e14',
            'broken': '#dc3545',
            'lost': '#6c757d',
        }
        color = colors.get(obj.condition, '#6c757d')
        return format_html(f'<span style="background: {color}; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">{obj.get_condition_display()}</span>')
    condition_badge.short_description = "Condition"

    def quantity_display(self, obj):
        if obj.available_quantity > 0:
            return format_html(f'<span style="color: #28a745;">{obj.available_quantity} / {obj.quantity} available</span>')
        return format_html(f'<span style="color: #dc3545;">{obj.available_quantity} / {obj.quantity} available</span>')
    quantity_display.short_description = "Stock"


@admin.register(EquipmentBorrow)
class EquipmentBorrowAdmin(ModelAdmin):
    list_display = ['item', 'borrower_name', 'borrowed_by', 'borrowed_at', 'expected_return_date', 'status_badge']
    list_filter = ['status', 'item']
    search_fields = ['borrower_name', 'borrower_phone', 'borrower_email', 'item__name']
    readonly_fields = ['borrowed_at', 'returned_at']
    fieldsets = (
        ('Item & Borrower', {
            'fields': ('item', 'borrower_name', 'borrower_phone', 'borrower_email', 'borrower_department'),
        }),
        ('Dates', {
            'fields': ('borrowed_at', 'expected_return_date', 'returned_at'),
        }),
        ('Status & Notes', {
            'fields': ('status', 'notes'),
        }),
    )

    def status_badge(self, obj):
        if obj.status == 'overdue':
            return format_html('<span style="background: #dc3545; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">🔴 Overdue</span>')
        elif obj.status == 'returned':
            return format_html('<span style="background: #28a745; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">✅ Returned</span>')
        elif obj.is_overdue():
            return format_html('<span style="background: #dc3545; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">⚠️ Overdue</span>')
        return format_html('<span style="background: #17a2b8; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">📖 Borrowed</span>')
    status_badge.short_description = "Status"

    @action(description="Mark selected as returned", permissions=['change'])
    def mark_returned(self, request, queryset):
        count = 0
        for borrow in queryset:
            if borrow.mark_returned():
                count += 1
        self.message_user(request, f"✅ {count} borrow record(s) marked as returned.")


@admin.register(ShopItem)
class ShopItemAdmin(ModelAdmin):
    list_display = ['name', 'price_display', 'stock_display', 'category', 'collection_center', 'is_public']
    list_filter = ['category', 'is_active', 'is_public', 'is_free']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [ShopOrderInline, FreeClaimInline]
    fieldsets = (
        ('Item Details', {
            'fields': ('name', 'description', 'category'),
        }),
        ('Pricing & Stock', {
            'fields': ('price', 'is_free', 'quantity_in_stock', 'available_quantity'),
        }),
        ('Collection', {
            'fields': ('collection_center', 'collection_instructions'),
        }),
        ('Image & Status', {
            'fields': ('image', 'is_active', 'is_public'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def price_display(self, obj):
        if obj.is_free:
            return format_html('<span style="color: #28a745;">🆓 Free</span>')
        return f"₦{obj.price:,.2f}"
    price_display.short_description = "Price"

    def stock_display(self, obj):
        if obj.available_quantity > 0:
            return format_html(f'<span style="color: #28a745;">{obj.available_quantity} / {obj.quantity_in_stock}</span>')
        return format_html(f'<span style="color: #dc3545;">{obj.available_quantity} / {obj.quantity_in_stock}</span>')
    stock_display.short_description = "Stock"


@admin.register(ShopOrder)
class ShopOrderAdmin(ModelAdmin):
    list_display = ['buyer_name', 'item', 'quantity', 'total_amount_display', 'status_badge', 'collection_code', 'created_at']
    list_filter = ['status', 'item']
    search_fields = ['buyer_name', 'buyer_email', 'buyer_phone', 'collection_code']
    readonly_fields = ['collection_code', 'created_at', 'collected_at']
    fieldsets = (
        ('Order Details', {
            'fields': ('item', 'quantity', 'total_amount'),
        }),
        ('Buyer Information', {
            'fields': ('buyer_name', 'buyer_email', 'buyer_phone'),
        }),
        ('Status & Collection', {
            'fields': ('status', 'collection_center', 'collection_code', 'payment_reference'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'collected_at'),
            'classes': ('collapse',),
        }),
    )

    def total_amount_display(self, obj):
        return f"₦{obj.total_amount:,.2f}"
    total_amount_display.short_description = "Total"

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'paid': '#17a2b8',
            'collected': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(f'<span style="background: {color}; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">{obj.get_status_display()}</span>')
    status_badge.short_description = "Status"

    @action(description="Mark selected as paid", permissions=['change'])
    def mark_paid(self, request, queryset):
        count = 0
        for order in queryset:
            if order.mark_paid():
                count += 1
        self.message_user(request, f"✅ {count} order(s) marked as paid.")

    @action(description="Mark selected as collected", permissions=['change'])
    def mark_collected(self, request, queryset):
        count = 0
        for order in queryset:
            if order.mark_collected():
                count += 1
        self.message_user(request, f"✅ {count} order(s) marked as collected.")


@admin.register(FreeClaim)
class FreeClaimAdmin(ModelAdmin):
    list_display = ['claimant_name', 'item', 'claim_code', 'status_badge', 'created_at', 'expiry_date']
    list_filter = ['status', 'item']
    search_fields = ['claimant_name', 'claimant_email', 'claimant_phone', 'claim_code']
    readonly_fields = ['claim_code', 'created_at', 'claimed_at']
    fieldsets = (
        ('Item & Claimant', {
            'fields': ('item', 'claimant_name', 'claimant_email', 'claimant_phone'),
        }),
        ('Collection', {
            'fields': ('collection_center', 'claim_code'),
        }),
        ('Status & Dates', {
            'fields': ('status', 'expiry_date', 'created_at', 'claimed_at'),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'claimed': '#28a745',
            'expired': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(f'<span style="background: {color}; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">{obj.get_status_display()}</span>')
    status_badge.short_description = "Status"

    @action(description="Mark selected as claimed", permissions=['change'])
    def mark_claimed(self, request, queryset):
        count = 0
        for claim in queryset:
            if claim.mark_claimed():
                count += 1
        self.message_user(request, f"✅ {count} claim(s) marked as claimed.")


@admin.register(SellableForm)
class SellableFormAdmin(ModelAdmin):
    list_display = ['title', 'price_display', 'payment_methods', 'is_active', 'is_public']
    list_filter = ['payment_methods', 'is_active', 'is_public']
    search_fields = ['title', 'description']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [FormPurchaseInline]
    fieldsets = (
        ('Form Details', {
            'fields': ('title', 'description', 'price'),
        }),
        ('Payment & Status', {
            'fields': ('payment_methods', 'is_active', 'is_public'),
        }),
        ('Instructions', {
            'fields': ('instruction_text', 'collection_center'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def price_display(self, obj):
        return f"₦{obj.price:,.2f}"
    price_display.short_description = "Price"


@admin.register(FormPurchase)
class FormPurchaseAdmin(ModelAdmin):
    list_display = ['buyer_name', 'form', 'amount_paid_display', 'status_badge', 'access_code', 'created_at']
    list_filter = ['status', 'payment_method', 'form']
    search_fields = ['buyer_name', 'buyer_email', 'buyer_phone', 'access_code']
    readonly_fields = ['access_code', 'created_at', 'paid_at']
    fieldsets = (
        ('Form & Buyer', {
            'fields': ('form', 'buyer_name', 'buyer_email', 'buyer_phone'),
        }),
        ('Payment', {
            'fields': ('amount_paid', 'payment_method', 'payment_reference', 'status'),
        }),
        ('Access', {
            'fields': ('access_code',),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'paid_at'),
            'classes': ('collapse',),
        }),
    )

    def amount_paid_display(self, obj):
        return f"₦{obj.amount_paid:,.2f}"
    amount_paid_display.short_description = "Amount"

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'paid': '#17a2b8',
            'verified': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(f'<span style="background: {color}; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">{obj.get_status_display()}</span>')
    status_badge.short_description = "Status"

    @action(description="Mark selected as paid", permissions=['change'])
    def mark_paid(self, request, queryset):
        count = 0
        for purchase in queryset:
            if purchase.mark_paid():
                count += 1
        self.message_user(request, f"✅ {count} purchase(s) marked as paid.")

    @action(description="Mark selected as verified", permissions=['change'])
    def mark_verified(self, request, queryset):
        count = queryset.update(status='verified')
        self.message_user(request, f"✅ {count} purchase(s) marked as verified.")


@admin.register(BookingListing)
class BookingListingAdmin(ModelAdmin):
    list_display = ['title', 'category', 'price_display', 'quantity_available', 'date_time', 'venue', 'is_active']
    list_filter = ['category', 'is_active', 'is_public']
    search_fields = ['title', 'description', 'venue']
    readonly_fields = ['created_at', 'updated_at']
    inlines = [BookingInline]
    fieldsets = (
        ('Listing Details', {
            'fields': ('category', 'title', 'description'),
        }),
        ('Pricing & Availability', {
            'fields': ('price', 'quantity_available'),
        }),
        ('Event Info', {
            'fields': ('venue', 'date_time', 'instructions'),
        }),
        ('Collection & Status', {
            'fields': ('collection_center', 'image', 'is_active', 'is_public'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def price_display(self, obj):
        return f"₦{obj.price:,.2f}"
    price_display.short_description = "Price"


@admin.register(Booking)
class BookingAdmin(ModelAdmin):
    list_display = ['booker_name', 'listing', 'quantity', 'total_amount_display', 'status_badge', 'qr_token_short', 'created_at']
    list_filter = ['status', 'listing']
    search_fields = ['booker_name', 'booker_email', 'booker_phone', 'qr_token']
    readonly_fields = ['qr_token', 'created_at', 'paid_at', 'checked_in_at']
    fieldsets = (
        ('Booking Details', {
            'fields': ('listing', 'quantity', 'total_amount'),
        }),
        ('Booker Information', {
            'fields': ('booker_name', 'booker_email', 'booker_phone'),
        }),
        ('Payment & Status', {
            'fields': ('payment_reference', 'status', 'qr_token'),
        }),
        ('Collection & Check-in', {
            'fields': ('collection_center', 'checked_in_at'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'paid_at'),
            'classes': ('collapse',),
        }),
    )

    def total_amount_display(self, obj):
        return f"₦{obj.total_amount:,.2f}"
    total_amount_display.short_description = "Total"

    def qr_token_short(self, obj):
        return obj.qr_token[:12] + '...' if obj.qr_token else '-'
    qr_token_short.short_description = "QR Token"

    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'paid': '#17a2b8',
            'checked_in': '#28a745',
            'cancelled': '#dc3545',
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(f'<span style="background: {color}; color: #fff; padding: 2px 10px; border-radius: 12px; font-size: 0.75rem;">{obj.get_status_display()}</span>')
    status_badge.short_description = "Status"

    @action(description="Mark selected as paid", permissions=['change'])
    def mark_paid(self, request, queryset):
        count = 0
        for booking in queryset:
            if booking.mark_paid():
                count += 1
        self.message_user(request, f"✅ {count} booking(s) marked as paid.")

    @action(description="Mark selected as checked in", permissions=['change'])
    def mark_checked_in(self, request, queryset):
        count = 0
        for booking in queryset:
            if booking.check_in():
                count += 1
        self.message_user(request, f"✅ {count} booking(s) checked in.")


# ============================================================
# DASHBOARD STATS — Admin Index
# ============================================================

class BusinessDashboardAdmin(ModelAdmin):
    """Custom admin dashboard for Business app."""
    change_list_template = "admin/business/dashboard.html"

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('dashboard/', self.admin_site.admin_view(self.dashboard_view), name='business_dashboard'),
        ]
        return custom_urls + urls

    def dashboard_view(self, request):
        from django.shortcuts import render
        context = {
            'title': 'Business Dashboard',
            'total_transactions': Transaction.objects.count(),
            'total_income': Transaction.objects.filter(
                category__in=[c[0] for c in Transaction.INCOME_CATEGORIES]
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'total_expenses': Transaction.objects.filter(
                category__in=[c[0] for c in Transaction.EXPENSE_CATEGORIES]
            ).aggregate(total=Sum('amount'))['total'] or 0,
            'overdue_items': EquipmentBorrow.objects.filter(
                status='borrowed',
                expected_return_date__lt=timezone.now()
            ).count(),
            'pending_orders': ShopOrder.objects.filter(status='pending').count(),
            'pending_claims': FreeClaim.objects.filter(status='pending').count(),
            'pending_bookings': Booking.objects.filter(status='pending').count(),
        }
        return render(request, 'admin/business/dashboard.html', context)


# ============================================================
# OPTIONAL: Custom Admin Site (if you want a separate business admin)
# ============================================================

# If you want a separate admin site for business:
# business_admin_site = admin.AdminSite(name='business_admin')
# business_admin_site.register(CollectionCenter, CollectionCenterAdmin)
# ... etc.

# Then wire it in urls.py:
# path('business-admin/', business_admin_site.urls),