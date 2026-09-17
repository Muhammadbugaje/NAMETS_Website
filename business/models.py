# business/models.py
# Business App — Complete Models (Cloudinary-backed)

from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator

from cloudinary.models import CloudinaryField

import uuid
import hashlib
import random
import string
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


# ============================================================
# PAYMENT RECORDING
# ============================================================

def record_payment_to_ledger(amount, category, description, account, user=None):
    """
    Create a Transaction entry that automatically updates the
    BankAccount.current_balance via Transaction.save().
    """
    if not account or amount is None:
        return None
    try:
        return Transaction.objects.create(
            account=account,
            category=category,
            amount=amount,
            description=description,
            created_by=user,
        )
    except Exception:
        logger.exception("Failed to record ledger transaction")
        return None


# ============================================================
# 1. COLLECTION CENTER
# ============================================================

class CollectionCenter(models.Model):
    """Physical pickup location for shop orders, free claims, and bookings."""
    name = models.CharField(max_length=100, help_text="e.g., ICT Office")
    location = models.TextField(help_text="e.g., Room 203, Faculty of Engineering")
    contact_person = models.CharField(max_length=100, blank=True)
    contact_phone = models.CharField(max_length=20, blank=True)
    opening_hours = models.CharField(max_length=200, blank=True, help_text="e.g., Mon-Fri 9am-4pm")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Collection Center"
        verbose_name_plural = "Collection Centers"

    def __str__(self):
        return self.name


# ============================================================
# 2. BANK ACCOUNTS & LEDGER
# ============================================================

class BankAccount(models.Model):
    ACCOUNT_TYPES = [
        ('general', 'General NAMETS Account'),
        ('mosque', 'Mosque Fund'),
        ('donations', 'Donations Account'),
        ('shop', 'Shop Revenue'),
        ('project', 'Project Account'),
    ]

    name = models.CharField(max_length=100)
    account_type = models.CharField(max_length=20, choices=ACCOUNT_TYPES, default='general')
    account_number = models.CharField(max_length=50, blank=True)
    bank_name = models.CharField(max_length=100, blank=True)
    current_balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False, help_text="Show on public donations page")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Bank Account"
        verbose_name_plural = "Bank Accounts"

    def __str__(self):
        return f"{self.name} — ₦{self.current_balance:,.2f}"


class Transaction(models.Model):
    """Financial transaction with atomic balance update and correction tracking."""

    INCOME_CATEGORIES = [
        ('donation', 'Donation'),
        ('shop_sales', 'Shop Sales'),
        ('booking_revenue', 'Booking/Ticket Revenue'),
        ('islamiyya_revenue', 'Islamiyya Registration'),
        ('form_revenue', 'Form/Registration Revenue'),
        ('other_income', 'Other Income'),
    ]

    EXPENSE_CATEGORIES = [
        ('equipment', 'Equipment Purchase'),
        ('event_cost', 'Event Cost'),
        ('utility', 'Utility Bill'),
        ('rent', 'Rent'),
        ('transport', 'Transport'),
        ('other_expense', 'Other Expense'),
    ]

    CATEGORY_CHOICES = INCOME_CATEGORIES + EXPENSE_CATEGORIES

    account = models.ForeignKey(
        BankAccount,
        on_delete=models.CASCADE,
        related_name='transactions'
    )
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=15, decimal_places=2, validators=[MinValueValidator(0.01)])
    description = models.TextField()
    internal_note = models.TextField(blank=True)
    date = models.DateTimeField(default=timezone.now)

    # Uploaded to Cloudinary under namets/receipts/
    receipt_attachment = CloudinaryField(
        'receipt',
        folder='namets/receipts',
        resource_type='auto',   # allows PDF + image + any file type
        blank=True,
        null=True,
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_transactions'
    )

    is_correction = models.BooleanField(default=False)
    corrects = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='corrections',
        help_text="If this is a correction, which transaction is being corrected?"
    )

    previous_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    new_balance = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-date']
        indexes = [
            models.Index(fields=['date']),
            models.Index(fields=['category']),
            models.Index(fields=['account', 'date']),
            models.Index(fields=['is_correction']),
        ]
        verbose_name = "Transaction"
        verbose_name_plural = "Transactions"

    def __str__(self):
        return f"{self.get_category_display()} — ₦{self.amount:,.2f}"

    def is_income(self):
        return self.category in [c[0] for c in self.INCOME_CATEGORIES]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            self.previous_balance = self.account.current_balance
            if self.is_income():
                self.account.current_balance += self.amount
            else:
                self.account.current_balance -= self.amount
            self.new_balance = self.account.current_balance
            super().save(*args, **kwargs)
            self.account.save(update_fields=['current_balance', 'updated_at'])

    def create_correction(self, new_amount, new_category, new_description, created_by, reason=""):
        if self.is_correction:
            raise ValueError("Cannot correct a correction entry.")

        with transaction.atomic():
            correction_amount = new_amount - self.amount if self.is_income() else self.amount - new_amount

            if correction_amount == 0:
                raise ValueError("No change in amount. Correction not created.")

            correction_category = new_category if new_category != self.category else self.category

            correction = Transaction.objects.create(
                account=self.account,
                category=correction_category,
                amount=abs(correction_amount),
                description=f"CORRECTION: {new_description or self.description}",
                internal_note=f"Original: {self.description}. Reason: {reason}",
                created_by=created_by,
                is_correction=True,
                corrects=self,
            )

            return correction


# ============================================================
# 3. INTERNAL EQUIPMENT
# ============================================================

class EquipmentItem(models.Model):
    CONDITION_CHOICES = [
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('broken', 'Broken'),
        ('lost', 'Lost'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, default='good')
    quantity = models.PositiveIntegerField(default=1, help_text="Total number of units owned")
    available_quantity = models.PositiveIntegerField(default=0, help_text="How many are currently available to borrow")
    location = models.CharField(max_length=200, blank=True)
    contact_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='equipment_contact',
        help_text="Who to ask for this item"
    )

    image = CloudinaryField(
        'image',
        folder='namets/equipment',
        resource_type='image',
        blank=True,
        null=True,
    )

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Equipment Item"
        verbose_name_plural = "Equipment Items"

    def __str__(self):
        return f"{self.name} ({self.condition})"

    def save(self, *args, **kwargs):
        if self.available_quantity > self.quantity:
            self.available_quantity = self.quantity
        super().save(*args, **kwargs)

    def is_available(self):
        return self.available_quantity > 0 and self.is_active


class EquipmentBorrow(models.Model):
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
        ('overdue', 'Overdue'),
    ]

    item = models.ForeignKey(
        EquipmentItem,
        on_delete=models.CASCADE,
        related_name='borrows'
    )
    borrowed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='equipment_borrowed'
    )
    borrower_name = models.CharField(max_length=150)
    borrower_phone = models.CharField(max_length=20)
    borrower_email = models.EmailField(blank=True)
    borrower_department = models.CharField(max_length=100, blank=True)
    borrowed_at = models.DateTimeField(auto_now_add=True)
    expected_return_date = models.DateTimeField()
    returned_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='borrowed')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-borrowed_at']
        indexes = [
            models.Index(fields=['status', 'expected_return_date']),
            models.Index(fields=['item', 'status']),
        ]
        verbose_name = "Equipment Borrow Record"
        verbose_name_plural = "Equipment Borrow Records"

    def __str__(self):
        return f"{self.item.name} → {self.borrower_name}"

    def is_overdue(self):
        return self.status in ('borrowed', 'overdue') and self.expected_return_date < timezone.now()

    def mark_returned(self):
        if self.status == 'returned':
            return False

        self.returned_at = timezone.now()
        self.status = 'returned'
        self.save()

        self.item.available_quantity += 1
        self.item.save(update_fields=['available_quantity', 'updated_at'])
        return True

    def save(self, *args, **kwargs):
        if not self.pk and self.status == 'borrowed':
            if self.item.available_quantity < 1:
                raise ValueError(f"'{self.item.name}' is not available for borrowing.")
            self.item.available_quantity -= 1
            self.item.save(update_fields=['available_quantity', 'updated_at'])

        if self.status == 'borrowed' and self.expected_return_date < timezone.now():
            self.status = 'overdue'

        super().save(*args, **kwargs)


# ============================================================
# 4. PUBLIC SHOP
# ============================================================

class ShopItem(models.Model):
    CATEGORY_CHOICES = [
        ('merchandise', 'Merchandise'),
        ('stationery', 'Stationery'),
        ('books', 'Books'),
        ('labcoats', 'Lab Coats'),
        ('accessories', 'Accessories'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_free = models.BooleanField(default=False, help_text="If true, no payment required")
    quantity_in_stock = models.PositiveIntegerField(default=0)
    available_quantity = models.PositiveIntegerField(default=0)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='merchandise')

    image = CloudinaryField(
        'image',
        folder='namets/shop',
        resource_type='image',
        blank=True,
        null=True,
    )

    collection_center = models.ForeignKey(
        CollectionCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Where to pick up this item"
    )
    collection_instructions = models.TextField(blank=True, help_text="Additional pickup instructions")
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True, help_text="Show on public shop page")
    account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='shop_items',
        help_text="Which bank account receives payment for this item?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = "Shop Item"
        verbose_name_plural = "Shop Items"

    @property
    def total_revenue(self):
        from django.db.models import Sum
        return self.orders.filter(
            status__in=['paid', 'collected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

    @property
    def quantity_sold(self):
        from django.db.models import Sum
        return self.orders.filter(
            status__in=['paid', 'collected']
        ).aggregate(total=Sum('quantity'))['total'] or 0

    def __str__(self):
        return f"{self.name} — ₦{self.price:,.2f}"

    def save(self, *args, **kwargs):
        if self.available_quantity > self.quantity_in_stock:
            self.available_quantity = self.quantity_in_stock
        super().save(*args, **kwargs)

    def is_in_stock(self):
        return self.available_quantity > 0


class ShopOrder(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('collected', 'Collected'),
        ('cancelled', 'Cancelled'),
    ]

    item = models.ForeignKey(ShopItem, on_delete=models.CASCADE, related_name='orders')
    quantity = models.PositiveIntegerField(default=1)
    buyer_name = models.CharField(max_length=150)
    buyer_email = models.EmailField()
    buyer_phone = models.CharField(max_length=20)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True)
    collection_code = models.CharField(max_length=20, unique=True, blank=True)
    collection_center = models.ForeignKey(
        CollectionCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    collected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['collection_code']),
            models.Index(fields=['status']),
        ]
        verbose_name = "Shop Order"
        verbose_name_plural = "Shop Orders"

    def __str__(self):
        return f"{self.item.name} x{self.quantity} — {self.buyer_name}"

    def save(self, *args, **kwargs):
        if not self.collection_code:
            self.collection_code = self._generate_code()
        if not self.collection_center and self.item.collection_center:
            self.collection_center = self.item.collection_center
        super().save(*args, **kwargs)

    def _generate_code(self):
        prefix = "SHOP"
        year = timezone.now().year
        last = ShopOrder.objects.filter(
            collection_code__startswith=f"{prefix}-{year}-"
        ).order_by('-collection_code').first()
        if last:
            last_num = int(last.collection_code.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        return f"{prefix}-{year}-{next_num:04d}"

    def mark_paid(self, reference=""):
        if self.status == 'paid':
            return False
        self.status = 'paid'
        if reference:
            self.payment_reference = reference
        self.save()

        self.item.available_quantity -= self.quantity
        self.item.save(update_fields=['available_quantity', 'updated_at'])

        record_payment_to_ledger(
            amount=self.total_amount,
            category='shop_sales',
            description=f"Shop order {self.collection_code}: {self.item.name} × {self.quantity}",
            account=self.item.account,
        )
        return True

    def mark_collected(self):
        if self.status == 'collected':
            return False
        self.status = 'collected'
        self.collected_at = timezone.now()
        self.save()
        return True


# ============================================================
# 5. FREE CLAIMS
# ============================================================

class FreeClaim(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('claimed', 'Claimed'),
        ('expired', 'Expired'),
    ]

    item = models.ForeignKey(
        ShopItem,
        on_delete=models.CASCADE,
        related_name='free_claims',
        limit_choices_to={'is_free': True}
    )
    claimant_name = models.CharField(max_length=150)
    claimant_email = models.EmailField()
    claimant_phone = models.CharField(max_length=20)
    claim_code = models.CharField(max_length=20, unique=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    collection_center = models.ForeignKey(
        CollectionCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_at = models.DateTimeField(null=True, blank=True)
    expiry_date = models.DateTimeField(null=True, blank=True, help_text="Reservation expires after this date")

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['claim_code']),
            models.Index(fields=['status']),
        ]
        verbose_name = "Free Claim"
        verbose_name_plural = "Free Claims"

    def __str__(self):
        return f"{self.item.name} → {self.claimant_name}"

    def save(self, *args, **kwargs):
        if not self.claim_code:
            self.claim_code = self._generate_code()
        if not self.collection_center and self.item.collection_center:
            self.collection_center = self.item.collection_center
        if not self.expiry_date:
            self.expiry_date = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    def _generate_code(self):
        prefix = "CLAIM"
        year = timezone.now().year
        last = FreeClaim.objects.filter(
            claim_code__startswith=f"{prefix}-{year}-"
        ).order_by('-claim_code').first()
        if last:
            last_num = int(last.claim_code.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        return f"{prefix}-{year}-{next_num:04d}"

    def mark_claimed(self):
        if self.status == 'claimed':
            return False
        self.status = 'claimed'
        self.claimed_at = timezone.now()
        self.save()
        return True

    def is_expired(self):
        return self.expiry_date and self.expiry_date < timezone.now()


# ============================================================
# 6. SELLABLE FORMS
# ============================================================

class SellableForm(models.Model):
    """A form that requires payment before submission."""
    PAYMENT_METHODS = [
        ('paystack', 'Paystack'),
        ('manual', 'Manual Bank Transfer'),
        ('both', 'Both'),
    ]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    payment_methods = models.CharField(max_length=20, choices=PAYMENT_METHODS, default='paystack')
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sellable_forms',
        help_text="Which bank account receives payment for this form?"
    )
    instruction_text = models.TextField(blank=True, help_text="Instructions shown after payment")
    collection_center = models.ForeignKey(
        CollectionCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['title']
        verbose_name = "Sellable Form"
        verbose_name_plural = "Sellable Forms"

    @property
    def total_revenue(self):
        from django.db.models import Sum
        return self.purchases.filter(
            status__in=['paid', 'verified']
        ).aggregate(total=Sum('amount_paid'))['total'] or 0

    @property
    def total_sold(self):
        return self.purchases.filter(status__in=['paid', 'verified']).count()

    def __str__(self):
        return f"{self.title} — ₦{self.price:,.2f}"


class FormPurchase(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('verified', 'Manually Verified'),
        ('cancelled', 'Cancelled'),
    ]

    form = models.ForeignKey(SellableForm, on_delete=models.CASCADE, related_name='purchases')
    buyer_name = models.CharField(max_length=150)
    buyer_email = models.EmailField()
    buyer_phone = models.CharField(max_length=20)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=20, choices=SellableForm.PAYMENT_METHODS, default='paystack')
    payment_reference = models.CharField(max_length=100, blank=True)
    access_code = models.CharField(max_length=20, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['access_code']),
            models.Index(fields=['status']),
        ]
        verbose_name = "Form Purchase"
        verbose_name_plural = "Form Purchases"

    def __str__(self):
        return f"{self.form.title} — {self.buyer_name}"

    def save(self, *args, **kwargs):
        if not self.access_code:
            self.access_code = self._generate_code()
        super().save(*args, **kwargs)

    def _generate_code(self):
        prefix = "FORM"
        year = timezone.now().year
        last = FormPurchase.objects.filter(
            access_code__startswith=f"{prefix}-{year}-"
        ).order_by('-access_code').first()
        if last:
            last_num = int(last.access_code.split('-')[-1])
            next_num = last_num + 1
        else:
            next_num = 1
        return f"{prefix}-{year}-{next_num:04d}"

    def mark_paid(self, reference=""):
        if self.status == 'paid':
            return False
        self.status = 'paid'
        if reference:
            self.payment_reference = reference
        self.paid_at = timezone.now()
        self.save()

        record_payment_to_ledger(
            amount=self.amount_paid,
            category='form_revenue',
            description=f"Form purchase {self.access_code}: {self.form.title}",
            account=self.form.account,
        )
        return True


# ============================================================
# 7. BOOKINGS / TICKETS
# ============================================================

class BookingListing(models.Model):
    CATEGORY_CHOICES = [
        ('event_ticket', 'Event Ticket'),
        ('travel', 'Travel Booking'),
        ('workshop', 'Workshop'),
        ('other', 'Other'),
    ]

    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    quantity_available = models.PositiveIntegerField(default=0)
    venue = models.CharField(max_length=200, blank=True)
    date_time = models.DateTimeField(null=True, blank=True)

    image = CloudinaryField(
        'image',
        folder='namets/bookings',
        resource_type='image',
        blank=True,
        null=True,
    )

    instructions = models.TextField(blank=True, help_text="What to bring, contact info, etc.")
    collection_center = models.ForeignKey(
        CollectionCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    account = models.ForeignKey(
        BankAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='booking_listings',
        help_text="Which bank account receives payment for this listing?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Booking Listing"
        verbose_name_plural = "Booking Listings"

    @property
    def total_revenue(self):
        from django.db.models import Sum
        return self.bookings.filter(
            status__in=['paid', 'checked_in']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

    @property
    def quantity_sold(self):
        from django.db.models import Sum
        return self.bookings.filter(
            status__in=['paid', 'checked_in']
        ).aggregate(total=Sum('quantity'))['total'] or 0

    def __str__(self):
        return f"{self.title} — ₦{self.price:,.2f}"

    def is_available(self):
        return self.quantity_available > 0 and self.is_active


class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid'),
        ('checked_in', 'Checked In'),
        ('cancelled', 'Cancelled'),
    ]

    listing = models.ForeignKey(BookingListing, on_delete=models.CASCADE, related_name='bookings')
    booker_name = models.CharField(max_length=150)
    booker_email = models.EmailField()
    booker_phone = models.CharField(max_length=20)
    quantity = models.PositiveIntegerField(default=1)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_reference = models.CharField(max_length=100, blank=True)
    qr_token = models.CharField(max_length=64, unique=True, blank=True)
    collection_center = models.ForeignKey(
        CollectionCenter,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    checked_in_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['qr_token']),
            models.Index(fields=['status']),
        ]
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"

    def __str__(self):
        return f"{self.listing.title} — {self.booker_name}"

    def save(self, *args, **kwargs):
        if not self.qr_token:
            self.qr_token = self._generate_qr_token()
        if not self.collection_center and self.listing.collection_center:
            self.collection_center = self.listing.collection_center
        super().save(*args, **kwargs)

    def _generate_qr_token(self):
        return hashlib.sha256(
            f"{uuid.uuid4()}{timezone.now().timestamp()}{random.random()}".encode()
        ).hexdigest()[:32]

    def mark_paid(self, reference=""):
        if self.status == 'paid':
            return False
        self.status = 'paid'
        if reference:
            self.payment_reference = reference
        self.paid_at = timezone.now()
        self.save()

        self.listing.quantity_available -= self.quantity
        self.listing.save(update_fields=['quantity_available', 'updated_at'])

        record_payment_to_ledger(
            amount=self.total_amount,
            category='booking_revenue',
            description=f"Booking {self.listing.title} — {self.booker_name} × {self.quantity}",
            account=self.listing.account,
        )
        return True

    def check_in(self):
        if self.status == 'checked_in':
            return False
        self.status = 'checked_in'
        self.checked_in_at = timezone.now()
        self.save()
        return True


# ============================================================
# 8. GUEST LOOKUP MIXIN
# ============================================================

class GuestLookupMixin:
    """Mixin for models that need guest lookup by code or email+phone."""

    @classmethod
    def lookup_by_code(cls, code):
        try:
            return cls.objects.get(code_field=code)
        except cls.DoesNotExist:
            return None

    @classmethod
    def lookup_by_contact(cls, email, phone):
        return cls.objects.filter(email=email, phone=phone).first()


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def generate_claim_code(prefix, model, year=None):
    """Generate a unique code for any model."""
    if year is None:
        year = timezone.now().year

    if model == ShopOrder:
        field_name = 'collection_code'
        code_prefix = f"{prefix}-{year}-"
    elif model == FreeClaim:
        field_name = 'claim_code'
        code_prefix = f"{prefix}-{year}-"
    elif model == FormPurchase:
        field_name = 'access_code'
        code_prefix = f"{prefix}-{year}-"
    else:
        field_name = 'code'
        code_prefix = f"{prefix}-{year}-"

    last = model.objects.filter(
        **{f"{field_name}__startswith": code_prefix}
    ).order_by(f'-{field_name}').first()

    if last:
        last_num = int(getattr(last, field_name).split('-')[-1])
        next_num = last_num + 1
    else:
        next_num = 1

    return f"{code_prefix}{next_num:04d}"