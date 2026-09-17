# business/forms.py
# Business App — Complete Forms with Validation

from django import forms
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.forms import inlineformset_factory
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
# COLLECTION CENTER FORM
# ============================================================

class CollectionCenterForm(forms.ModelForm):
    class Meta:
        model = CollectionCenter
        fields = ['name', 'location', 'contact_person', 'contact_phone', 'opening_hours', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., ICT Office'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Room 203, Faculty of Engineering'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Bro. Ahmed'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 08012345678'}),
            'opening_hours': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Mon-Fri 9am-4pm'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Collection Center Name',
            'location': 'Location / Address',
            'contact_person': 'Contact Person',
            'contact_phone': 'Contact Phone',
            'opening_hours': 'Opening Hours',
            'is_active': 'Active',
        }
        help_texts = {
            'opening_hours': 'Specify days and times when this center is open.',
        }


# ============================================================
# BANK ACCOUNT FORMS
# ============================================================

class BankAccountForm(forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ['name', 'account_type', 'account_number', 'bank_name', 'current_balance', 'is_active', 'is_public', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-control'}),
            'account_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 1234567890'}),
            'bank_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., GTBank'}),
            'current_balance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'name': 'Account Name',
            'account_type': 'Account Type',
            'account_number': 'Account Number',
            'bank_name': 'Bank Name',
            'current_balance': 'Current Balance (₦)',
            'is_active': 'Active',
            'is_public': 'Show on Public Donations Page',
            'description': 'Description',
        }
        help_texts = {
            'is_public': 'If checked, this account will be visible on the public donations page.',
            'current_balance': 'Initial balance. This will be updated automatically with transactions.',
        }

    def clean_current_balance(self):
        balance = self.cleaned_data.get('current_balance')
        if balance is not None and balance < 0:
            raise forms.ValidationError("Balance cannot be negative.")
        return balance


# ============================================================
# TRANSACTION FORMS
# ============================================================


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ['account', 'category', 'amount', 'description', 'internal_note', 'date', 'receipt_attachment']
        widgets = {
            'account': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'description': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief description of the transaction'}),
            'internal_note': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Internal notes (EXCO only)'}),
            'date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'receipt_attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'account': 'Bank Account',
            'category': 'Category',
            'amount': 'Amount (₦)',
            'description': 'Description',
            'internal_note': 'Internal Note',
            'date': 'Date/Time',
            'receipt_attachment': 'Receipt',
        }

    def __init__(self, *args, **kwargs):
        expense_only = kwargs.pop('expense_only', False)
        income_only = kwargs.pop('income_only', False)
        super().__init__(*args, **kwargs)

        self.fields['account'].queryset = BankAccount.objects.filter(is_active=True)
        self.fields['account'].empty_label = "— Select Account —"
        self.fields['date'].initial = timezone.now()
        self.fields['date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']

        # Restrict category choices based on mode
        if expense_only:
            self.fields['category'].choices = Transaction.EXPENSE_CATEGORIES
            self.fields['category'].initial = 'other_expense'
        elif income_only:
            self.fields['category'].choices = Transaction.INCOME_CATEGORIES

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        if date and date > timezone.now():
            self.add_error('date', "Transaction date cannot be in the future.")
        return cleaned_data



class TransactionCorrectionForm(forms.Form):
    """Form for creating a correction entry."""
    new_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'placeholder': '0.00'}),
        label="New Amount (₦)"
    )
    new_category = forms.ChoiceField(
        choices=Transaction.CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="New Category"
    )
    new_description = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Updated description (optional)'}),
        label="New Description"
    )
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Why is this correction needed?'}),
        label="Reason for Correction",
        help_text="This will be visible in the audit trail."
    )

    def clean_new_amount(self):
        amount = self.cleaned_data.get('new_amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")
        return amount


# ============================================================
# EQUIPMENT FORMS
# ============================================================

class EquipmentItemForm(forms.ModelForm):
    class Meta:
        model = EquipmentItem
        fields = [
            'name', 'description', 'serial_number', 'condition',
            'quantity', 'available_quantity', 'location', 'contact_person',
            'image', 'is_active', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Serial/Asset number (if any)'}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'available_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Where is this stored?'}),
            'contact_person': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'name': 'Item Name',
            'description': 'Description',
            'serial_number': 'Serial/Asset Number',
            'condition': 'Condition',
            'quantity': 'Total Quantity',
            'available_quantity': 'Available to Borrow',
            'location': 'Location',
            'contact_person': 'Contact Person',
            'image': 'Photo',
            'is_active': 'Active',
            'notes': 'Additional Notes',
        }
        help_texts = {
            'quantity': 'Total number of units owned.',
            'available_quantity': 'How many are currently available to borrow.',
            'contact_person': 'Who to ask about this item.',
        }

    def clean(self):
        cleaned = super().clean()
        quantity = cleaned.get('quantity', 0)
        available = cleaned.get('available_quantity', 0)
        if available > quantity:
            self.add_error('available_quantity', "Available quantity cannot exceed total quantity.")
        return cleaned


class EquipmentBorrowForm(forms.ModelForm):
    class Meta:
        model = EquipmentBorrow
        fields = [
            'item', 'borrower_name', 'borrower_phone', 'borrower_email',
            'borrower_department', 'expected_return_date', 'status', 'notes'
        ]
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'borrower_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'borrower_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 08012345678'}),
            'borrower_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@example.com'}),
            'borrower_department': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Department (optional)'}),
            'expected_return_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
        labels = {
            'item': 'Item',
            'borrower_name': 'Borrower Name',
            'borrower_phone': 'Borrower Phone',
            'borrower_email': 'Borrower Email',
            'borrower_department': 'Department',
            'expected_return_date': 'Expected Return Date',
            'status': 'Status',
            'notes': 'Notes',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = EquipmentItem.objects.filter(is_active=True, available_quantity__gt=0)
        self.fields['expected_return_date'].input_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M']
        if not self.instance.pk:
            self.fields['expected_return_date'].initial = timezone.now() + timezone.timedelta(days=7)

    def clean_expected_return_date(self):
        date = self.cleaned_data.get('expected_return_date')
        if date and date < timezone.now():
            raise forms.ValidationError("Expected return date cannot be in the past.")
        return date


# ============================================================
# SHOP FORMS
# ============================================================

class ShopItemForm(forms.ModelForm):
    class Meta:
        model = ShopItem
        fields = [
            'name', 'description', 'price', 'is_free', 'category',
            'quantity_in_stock', 'available_quantity', 'image',
            'collection_center', 'collection_instructions',
            'is_active', 'is_public', 'account',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_free': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'quantity_in_stock': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'available_quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
            'collection_instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Item Name',
            'description': 'Description',
            'price': 'Price (₦)',
            'is_free': 'Free Item',
            'category': 'Category',
            'quantity_in_stock': 'Quantity in Stock',
            'available_quantity': 'Available to Order',
            'image': 'Image',
            'collection_center': 'Collection Center',
            'collection_instructions': 'Collection Instructions',
            'is_active': 'Active',
            'is_public': 'Show on Public Shop',
        }
        help_texts = {
            'is_free': 'If checked, this item is free (no payment required).',
            'available_quantity': 'How many are currently available for purchase.',
            'collection_instructions': 'Additional pickup instructions for customers.',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection_center'].queryset = CollectionCenter.objects.filter(is_active=True)
        self.fields['collection_center'].empty_label = "— Select Collection Center —"
        self.fields['account'].empty_label = "— No account (do not track) —"    

    def clean(self):
        cleaned = super().clean()
        stock = cleaned.get('quantity_in_stock', 0)
        available = cleaned.get('available_quantity', 0)
        if available > stock:
            self.add_error('available_quantity', "Available quantity cannot exceed stock quantity.")
        return cleaned


class ShopOrderForm(forms.ModelForm):
    class Meta:
        model = ShopOrder
        fields = [
            'item', 'quantity', 'buyer_name', 'buyer_email', 'buyer_phone',
            'total_amount', 'status', 'collection_center', 'collection_code'
        ]
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'buyer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'buyer_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'buyer_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
            'collection_code': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'item': 'Item',
            'quantity': 'Quantity',
            'buyer_name': 'Full Name',
            'buyer_email': 'Email Address',
            'buyer_phone': 'Phone Number',
            'total_amount': 'Total Amount (₦)',
            'status': 'Order Status',
            'collection_center': 'Collection Center',
            'collection_code': 'Collection Code',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ShopItem.objects.filter(is_active=True)
        self.fields['collection_center'].queryset = CollectionCenter.objects.filter(is_active=True)
        self.fields['collection_center'].empty_label = "— Select Collection Center —"
        if not self.instance.pk:
            self.fields['status'].initial = 'pending'


class ShopOrderGuestForm(forms.ModelForm):
    """Guest-facing form for placing an order."""
    class Meta:
        model = ShopOrder
        fields = ['buyer_name', 'buyer_email', 'buyer_phone', 'quantity']
        widgets = {
            'buyer_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'buyer_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'buyer_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08012345678'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
        }
        labels = {
            'buyer_name': 'Full Name',
            'buyer_email': 'Email Address',
            'buyer_phone': 'Phone Number',
            'quantity': 'Quantity',
        }


# ============================================================
# FREE CLAIM FORMS
# ============================================================

class FreeClaimForm(forms.ModelForm):
    class Meta:
        model = FreeClaim
        fields = ['item', 'claimant_name', 'claimant_email', 'claimant_phone', 'collection_center']
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'claimant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'claimant_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'claimant_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08012345678'}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'item': 'Item',
            'claimant_name': 'Full Name',
            'claimant_email': 'Email Address',
            'claimant_phone': 'Phone Number',
            'collection_center': 'Collection Center',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ShopItem.objects.filter(is_active=True, is_free=True)
        self.fields['collection_center'].queryset = CollectionCenter.objects.filter(is_active=True)
        self.fields['collection_center'].empty_label = "— Select Collection Center —"


class FreeClaimAdminForm(forms.ModelForm):
    """Admin version with status field."""
    class Meta:
        model = FreeClaim
        fields = [
            'item', 'claimant_name', 'claimant_email', 'claimant_phone',
            'status', 'collection_center', 'expiry_date'
        ]
        widgets = {
            'item': forms.Select(attrs={'class': 'form-control'}),
            'claimant_name': forms.TextInput(attrs={'class': 'form-control'}),
            'claimant_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'claimant_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        }


# ============================================================
# SELLABLE FORM FORMS
# ============================================================

class SellableFormForm(forms.ModelForm):
    class Meta:
        model = SellableForm
        fields = [
            'title', 'description', 'price', 'payment_methods',
            'is_active', 'is_public', 'instruction_text', 'collection_center', 'account'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'payment_methods': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'instruction_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'title': 'Form Title',
            'description': 'Description',
            'price': 'Price (₦)',
            'payment_methods': 'Payment Methods',
            'is_active': 'Active',
            'is_public': 'Show on Public Page',
            'instruction_text': 'Instructions (shown after payment)',
            'collection_center': 'Collection Center',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection_center'].queryset = CollectionCenter.objects.filter(is_active=True)
        self.fields['collection_center'].empty_label = "— Select Collection Center —"
        self.fields['account'].empty_label = "— No account (do not track) —"        


class FormPurchaseForm(forms.ModelForm):
    class Meta:
        model = FormPurchase
        fields = [
            'form', 'buyer_name', 'buyer_email', 'buyer_phone',
            'amount_paid', 'payment_method', 'status'
        ]
        widgets = {
            'form': forms.Select(attrs={'class': 'form-control'}),
            'buyer_name': forms.TextInput(attrs={'class': 'form-control'}),
            'buyer_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'buyer_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'form': 'Form',
            'buyer_name': 'Full Name',
            'buyer_email': 'Email Address',
            'buyer_phone': 'Phone Number',
            'amount_paid': 'Amount Paid (₦)',
            'payment_method': 'Payment Method',
            'status': 'Status',
        }


# ============================================================
# BOOKING FORMS
# ============================================================

class BookingListingForm(forms.ModelForm):
    class Meta:
        model = BookingListing
        fields = [
            'category', 'title', 'description', 'price', 'quantity_available',
            'venue', 'date_time', 'image', 'instructions',
            'collection_center', 'is_active', 'is_public', 'account',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'quantity_available': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '1'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Where is this event?'}),
            'date_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'instructions': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'category': 'Category',
            'title': 'Listing Title',
            'description': 'Description',
            'price': 'Price (₦)',
            'quantity_available': 'Available Spots',
            'venue': 'Venue',
            'date_time': 'Date & Time',
            'image': 'Image',
            'instructions': 'Instructions',
            'collection_center': 'Collection Center',
            'is_active': 'Active',
            'is_public': 'Show on Public Page',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['collection_center'].queryset = CollectionCenter.objects.filter(is_active=True)
        self.fields['collection_center'].empty_label = "— Select Collection Center —"
        self.fields['account'].empty_label = "— No account (do not track) —"
        if not self.instance.pk:
            self.fields['quantity_available'].initial = 0
            self.fields['price'].initial = 0

    def clean(self):
        cleaned = super().clean()
        quantity = cleaned.get('quantity_available', 0)
        if quantity < 0:
            self.add_error('quantity_available', "Available spots cannot be negative.")
        return cleaned


class BookingGuestForm(forms.ModelForm):
    """Guest-facing form for making a booking."""
    class Meta:
        model = Booking
        fields = ['booker_name', 'booker_email', 'booker_phone', 'quantity']
        widgets = {
            'booker_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
            'booker_email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
            'booker_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08012345678'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
        }
        labels = {
            'booker_name': 'Full Name',
            'booker_email': 'Email Address',
            'booker_phone': 'Phone Number',
            'quantity': 'Quantity',
        }


class BookingAdminForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = [
            'listing', 'booker_name', 'booker_email', 'booker_phone',
            'quantity', 'total_amount', 'status', 'collection_center'
        ]
        widgets = {
            'listing': forms.Select(attrs={'class': 'form-control'}),
            'booker_name': forms.TextInput(attrs={'class': 'form-control'}),
            'booker_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'booker_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
            'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'collection_center': forms.Select(attrs={'class': 'form-control'}),
        }


# ============================================================
# GUEST LOOKUP FORM
# ============================================================

class GuestLookupForm(forms.Form):
    """Form for guest lookup by code or email+phone."""
    lookup_type = forms.ChoiceField(
        choices=[
            ('code', 'By Code'),
            ('contact', 'By Email & Phone'),
        ],
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
        label="Search Method"
    )
    code = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., SHOP-2026-0001'}),
        label="Collection/Claim/Booking Code"
    )
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
        label="Email Address"
    )
    phone = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08012345678'}),
        label="Phone Number"
    )

    def clean(self):
        cleaned = super().clean()
        lookup_type = cleaned.get('lookup_type')
        code = cleaned.get('code', '').strip()
        email = cleaned.get('email', '').strip()
        phone = cleaned.get('phone', '').strip()

        if lookup_type == 'code' and not code:
            self.add_error('code', "Please enter a code.")
        if lookup_type == 'contact' and (not email and not phone):
            self.add_error('email', "Please provide email or phone.")
            self.add_error('phone', "Please provide email or phone.")

        return cleaned


# ============================================================
# INLINE FORMSETS
# ============================================================

# Transaction corrections inline formset (for admin)
TransactionCorrectionFormSet = inlineformset_factory(
    Transaction,
    Transaction,
    fields=['category', 'amount', 'description', 'date'],
    extra=0,
    can_delete=False,
    widgets={
        'category': forms.Select(attrs={'class': 'form-control'}),
        'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        'description': forms.TextInput(attrs={'class': 'form-control'}),
        'date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
    }
)

# Equipment borrow inline formset (for admin)
EquipmentBorrowFormSet = inlineformset_factory(
    EquipmentItem,
    EquipmentBorrow,
    fields=['borrower_name', 'borrower_phone', 'expected_return_date', 'status'],
    extra=1,
    can_delete=True,
    widgets={
        'borrower_name': forms.TextInput(attrs={'class': 'form-control'}),
        'borrower_phone': forms.TextInput(attrs={'class': 'form-control'}),
        'expected_return_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        'status': forms.Select(attrs={'class': 'form-control'}),
    }
)

# Shop order inline formset (for admin)
ShopOrderFormSet = inlineformset_factory(
    ShopItem,
    ShopOrder,
    fields=['buyer_name', 'quantity', 'total_amount', 'status'],
    extra=1,
    can_delete=True,
    widgets={
        'buyer_name': forms.TextInput(attrs={'class': 'form-control'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        'status': forms.Select(attrs={'class': 'form-control'}),
    }
)

# Booking inline formset (for admin)
BookingFormSet = inlineformset_factory(
    BookingListing,
    Booking,
    fields=['booker_name', 'quantity', 'total_amount', 'status'],
    extra=1,
    can_delete=True,
    widgets={
        'booker_name': forms.TextInput(attrs={'class': 'form-control'}),
        'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        'total_amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        'status': forms.Select(attrs={'class': 'form-control'}),
    }
)

# Form purchase inline formset (for admin)
FormPurchaseFormSet = inlineformset_factory(
    SellableForm,
    FormPurchase,
    fields=['buyer_name', 'amount_paid', 'payment_method', 'status'],
    extra=1,
    can_delete=True,
    widgets={
        'buyer_name': forms.TextInput(attrs={'class': 'form-control'}),
        'amount_paid': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        'payment_method': forms.Select(attrs={'class': 'form-control'}),
        'status': forms.Select(attrs={'class': 'form-control'}),
    }
)


# ============================================================
# PAYMENT FORMS (for Public Checkout)
# ============================================================

class PaymentCheckoutForm(forms.Form):
    """Generic checkout form for Paystack payments."""
    name = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Your full name'}),
        label="Full Name"
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'your@email.com'}),
        label="Email Address"
    )
    phone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': '08012345678'}),
        label="Phone Number"
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'step': '1'}),
        label="Quantity"
    )