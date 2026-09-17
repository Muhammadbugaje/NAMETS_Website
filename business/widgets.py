# business/widgets.py
# Business App — Dashboard Widgets for EXCO Dashboard

from core.dashboard_widgets import DashboardWidget, register_widget
from django.db.models import Sum, Count, Q
from django.utils import timezone
from .models import (
    BankAccount,
    Transaction,
    EquipmentItem,
    EquipmentBorrow,
    ShopItem,
    ShopOrder,
    FreeClaim,
    Booking,
    BookingListing,
    CollectionCenter,
)


# ============================================================
# 1. FINANCIAL WIDGETS
# ============================================================

class TotalBalanceWidget(DashboardWidget):
    """Total balance across all active bank accounts."""
    permission = "business.view_bankaccount"
    label = "Total Bank Balance"
    icon = "fa-wallet"
    url_name = "business:admin_bank_account_list"

    def get_count(self):
        total = BankAccount.objects.filter(is_active=True).aggregate(
            total=Sum('current_balance')
        )['total']
        if total:
            return f"₦{total:,.2f}"
        return "₦0.00"


class RecentTransactionsWidget(DashboardWidget):
    """Number of transactions in the last 7 days."""
    permission = "business.view_transaction"
    label = "Recent Transactions (7 days)"
    icon = "fa-receipt"
    url_name = "business:admin_transaction_list"

    def get_count(self):
        week_ago = timezone.now() - timezone.timedelta(days=7)
        return Transaction.objects.filter(date__gte=week_ago).count()


class TotalIncomeWidget(DashboardWidget):
    """Total income (donations, shop sales, booking revenue)."""
    permission = "business.view_transaction"
    label = "Total Income"
    icon = "fa-arrow-up"
    url_name = "business:admin_transaction_list"

    def get_count(self):
        total = Transaction.objects.filter(
            category__in=[c[0] for c in Transaction.INCOME_CATEGORIES]
        ).aggregate(total=Sum('amount'))['total']
        if total:
            return f"₦{total:,.2f}"
        return "₦0.00"


class TotalExpensesWidget(DashboardWidget):
    """Total expenses."""
    permission = "business.view_transaction"
    label = "Total Expenses"
    icon = "fa-arrow-down"
    url_name = "business:admin_transaction_list"

    def get_count(self):
        total = Transaction.objects.filter(
            category__in=[c[0] for c in Transaction.EXPENSE_CATEGORIES]
        ).aggregate(total=Sum('amount'))['total']
        if total:
            return f"₦{total:,.2f}"
        return "₦0.00"


# ============================================================
# 2. EQUIPMENT WIDGETS
# ============================================================

class TotalEquipmentWidget(DashboardWidget):
    """Total equipment items."""
    permission = "business.view_equipmentitem"
    label = "Equipment Items"
    icon = "fa-boxes"
    url_name = "business:admin_equipment_list"

    def get_count(self):
        return EquipmentItem.objects.filter(is_active=True).count()


class OverdueEquipmentWidget(DashboardWidget):
    """Overdue equipment borrows."""
    permission = "business.view_equipmentborrow"
    label = "Overdue Equipment"
    icon = "fa-clock"
    url_name = "business:admin_equipment_borrow_list"

    def get_count(self):
        return EquipmentBorrow.objects.filter(
            status='borrowed',
            expected_return_date__lt=timezone.now()
        ).count()


class ActiveEquipmentBorrowsWidget(DashboardWidget):
    """Currently borrowed equipment."""
    permission = "business.view_equipmentborrow"
    label = "Active Borrows"
    icon = "fa-hand-holding"
    url_name = "business:admin_equipment_borrow_list"

    def get_count(self):
        return EquipmentBorrow.objects.filter(status='borrowed').count()


# ============================================================
# 3. SHOP WIDGETS
# ============================================================

class TotalShopItemsWidget(DashboardWidget):
    """Total shop items in stock."""
    permission = "business.view_shopitem"
    label = "Shop Items"
    icon = "fa-store"
    url_name = "business:admin_shop_list"

    def get_count(self):
        return ShopItem.objects.filter(is_active=True).count()


class PendingShopOrdersWidget(DashboardWidget):
    """Pending shop orders waiting for payment/collection."""
    permission = "business.view_shoporder"
    label = "Pending Orders"
    icon = "fa-cart-shopping"
    url_name = "business:admin_shop_order_list"

    def get_count(self):
        return ShopOrder.objects.filter(status='pending').count()


class OutOfStockItemsWidget(DashboardWidget):
    """Shop items that are out of stock."""
    permission = "business.view_shopitem"
    label = "Out of Stock"
    icon = "fa-circle-exclamation"
    url_name = "business:admin_shop_list"

    def get_count(self):
        return ShopItem.objects.filter(
            is_active=True,
            available_quantity__lte=0
        ).count()


# ============================================================
# 4. FREE CLAIMS WIDGETS
# ============================================================

class PendingFreeClaimsWidget(DashboardWidget):
    """Pending free claims awaiting collection."""
    permission = "business.view_freeclaim"
    label = "Pending Free Claims"
    icon = "fa-gift"
    url_name = "business:admin_free_claim_list"

    def get_count(self):
        return FreeClaim.objects.filter(status='pending').count()


# ============================================================
# 5. BOOKING WIDGETS
# ============================================================

class PendingBookingsWidget(DashboardWidget):
    """Pending bookings awaiting payment."""
    permission = "business.view_booking"
    label = "Pending Bookings"
    icon = "fa-ticket"
    url_name = "business:admin_booking_list"

    def get_count(self):
        return Booking.objects.filter(status='pending').count()


class UpcomingBookingsWidget(DashboardWidget):
    """Upcoming bookings (paid, not checked in)."""
    permission = "business.view_booking"
    label = "Upcoming Bookings"
    icon = "fa-calendar-check"
    url_name = "business:admin_booking_list"

    def get_count(self):
        return Booking.objects.filter(
            status='paid',
            listing__date_time__gte=timezone.now()
        ).count()


class AvailableBookingsWidget(DashboardWidget):
    """Available spots across all active listings."""
    permission = "business.view_bookinglisting"
    label = "Available Spots"
    icon = "fa-chair"
    url_name = "business:admin_booking_listing_list"

    def get_count(self):
        return BookingListing.objects.filter(
            is_active=True,
            quantity_available__gt=0
        ).aggregate(total=Sum('quantity_available'))['total'] or 0


# ============================================================
# 6. COLLECTION CENTER WIDGETS
# ============================================================

class ActiveCollectionCentersWidget(DashboardWidget):
    """Active collection centers."""
    permission = "business.view_collectioncenter"
    label = "Collection Centers"
    icon = "fa-location-dot"
    url_name = "business:admin_collection_center_list"

    def get_count(self):
        return CollectionCenter.objects.filter(is_active=True).count()


# ============================================================
# 7. SELLABLE FORMS WIDGETS
# ============================================================

class SellableFormsWidget(DashboardWidget):
    """Active sellable forms."""
    permission = "business.view_sellableform"
    label = "Sellable Forms"
    icon = "fa-file-lines"
    url_name = "business:admin_sellable_form_list"

    def get_count(self):
        return SellableForm.objects.filter(is_active=True).count()


class PendingFormPurchasesWidget(DashboardWidget):
    """Pending form purchases awaiting payment."""
    permission = "business.view_formpurchase"
    label = "Pending Form Purchases"
    icon = "fa-file-pen"
    url_name = "business:admin_form_purchase_list"

    def get_count(self):
        return FormPurchase.objects.filter(status='pending').count()


# ============================================================
# REGISTER ALL WIDGETS
# ============================================================

register_widget(TotalBalanceWidget)
register_widget(RecentTransactionsWidget)
register_widget(TotalIncomeWidget)
register_widget(TotalExpensesWidget)

register_widget(TotalEquipmentWidget)
register_widget(OverdueEquipmentWidget)
register_widget(ActiveEquipmentBorrowsWidget)

register_widget(TotalShopItemsWidget)
register_widget(PendingShopOrdersWidget)
register_widget(OutOfStockItemsWidget)

register_widget(PendingFreeClaimsWidget)

register_widget(PendingBookingsWidget)
register_widget(UpcomingBookingsWidget)
register_widget(AvailableBookingsWidget)

register_widget(ActiveCollectionCentersWidget)

register_widget(SellableFormsWidget)
register_widget(PendingFormPurchasesWidget)