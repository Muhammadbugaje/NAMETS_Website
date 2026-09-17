# business/importers.py
# Business App — Complete Import/Export Specs for Phase 2 Framework

from core.importers.spec import ImportSpec, ColumnSpec
from core.importers.registry import register
from django.utils import timezone
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
# 1. COLLECTION CENTER IMPORT/EXPORT
# ============================================================

class CollectionCenterImportSpec(ImportSpec):
    key = "collection_centers"
    label = "Collection Centers"
    model = CollectionCenter
    
    columns = [
        ColumnSpec("name", "Name", example="ICT Office"),
        ColumnSpec("location", "Location", example="Room 203, Faculty of Engineering"),
        ColumnSpec("contact_person", "Contact Person", required=False, example="Bro. Ahmed"),
        ColumnSpec("contact_phone", "Contact Phone", required=False, example="08012345678"),
        ColumnSpec("opening_hours", "Opening Hours", required=False, example="Mon-Fri 9am-4pm"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        if not row.get("name", "").strip():
            errors.append("Name is required.")
        return errors
    
    def build_instance(self, row):
        return CollectionCenter.objects.create(
            name=row["name"].strip(),
            location=row.get("location", "").strip(),
            contact_person=row.get("contact_person", "").strip(),
            contact_phone=row.get("contact_phone", "").strip(),
            opening_hours=row.get("opening_hours", "").strip(),
            is_active=True,
        )
    
    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "location": instance.location,
            "contact_person": instance.contact_person,
            "contact_phone": instance.contact_phone,
            "opening_hours": instance.opening_hours,
        }


# ============================================================
# 2. BANK ACCOUNT IMPORT/EXPORT
# ============================================================

class BankAccountImportSpec(ImportSpec):
    key = "bank_accounts"
    label = "Bank Accounts"
    model = BankAccount
    
    columns = [
        ColumnSpec("name", "Account Name", example="NAMETS General Account"),
        ColumnSpec("account_type", "Account Type", example="general", 
                   choices=['general', 'mosque', 'donations', 'shop', 'project']),
        ColumnSpec("account_number", "Account Number", required=False, example="1234567890"),
        ColumnSpec("bank_name", "Bank Name", required=False, example="GTBank"),
        ColumnSpec("description", "Description", required=False, example="Main operating account"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        if not row.get("name", "").strip():
            errors.append("Account name is required.")
        account_type = row.get("account_type", "").strip().lower()
        valid_types = [c[0] for c in BankAccount.ACCOUNT_TYPES]
        if account_type and account_type not in valid_types:
            errors.append(f"Account type must be one of: {', '.join(valid_types)}")
        return errors
    
    def build_instance(self, row):
        return BankAccount.objects.create(
            name=row["name"].strip(),
            account_type=row.get("account_type", "general").strip().lower(),
            account_number=row.get("account_number", "").strip(),
            bank_name=row.get("bank_name", "").strip(),
            description=row.get("description", "").strip(),
            is_active=True,
            current_balance=0,
        )
    
    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "account_type": instance.account_type,
            "account_number": instance.account_number,
            "bank_name": instance.bank_name,
            "description": instance.description,
        }


# ============================================================
# 3. TRANSACTION IMPORT/EXPORT
# ============================================================

class TransactionImportSpec(ImportSpec):
    key = "transactions"
    label = "Transactions"
    model = Transaction
    
    columns = [
        ColumnSpec("account_name", "Account Name", example="NAMETS General Account"),
        ColumnSpec("category", "Category", example="donation",
                   choices=[c[0] for c in Transaction.CATEGORY_CHOICES]),
        ColumnSpec("amount", "Amount", example="5000.00"),
        ColumnSpec("description", "Description", example="Zakat collection"),
        ColumnSpec("internal_note", "Internal Note", required=False, example="Received from Bro. Ahmed"),
        ColumnSpec("date", "Date (YYYY-MM-DD HH:MM)", required=False, example="2026-09-09 14:30"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        # Validate account exists
        account_name = row.get("account_name", "").strip()
        if account_name and not BankAccount.objects.filter(name__iexact=account_name).exists():
            errors.append(f"Account '{account_name}' not found. Create it first.")
        
        # Validate amount
        amount = row.get("amount", "").strip()
        if amount:
            try:
                val = float(amount)
                if val <= 0:
                    errors.append("Amount must be greater than zero.")
            except ValueError:
                errors.append(f"Amount must be a number, got '{amount}'.")
        
        # Validate category
        category = row.get("category", "").strip().lower()
        valid_categories = [c[0] for c in Transaction.CATEGORY_CHOICES]
        if category and category not in valid_categories:
            errors.append(f"Category must be one of: {', '.join(valid_categories)}")
        
        return errors
    
    def build_instance(self, row):
        account = BankAccount.objects.get(name__iexact=row["account_name"].strip())
        date_str = row.get("date", "").strip()
        if date_str:
            try:
                # Try multiple formats
                for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y']:
                    try:
                        date = timezone.datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                else:
                    date = timezone.now()
            except:
                date = timezone.now()
        else:
            date = timezone.now()
        
        return Transaction.objects.create(
            account=account,
            category=row["category"].strip().lower(),
            amount=float(row["amount"]),
            description=row["description"].strip(),
            internal_note=row.get("internal_note", "").strip(),
            date=date,
            is_correction=False,
        )
    
    def row_from_instance(self, instance):
        return {
            "account_name": instance.account.name,
            "category": instance.category,
            "amount": float(instance.amount),
            "description": instance.description,
            "internal_note": instance.internal_note,
            "date": instance.date.strftime("%Y-%m-%d %H:%M"),
        }


# ============================================================
# 4. EQUIPMENT ITEM IMPORT/EXPORT
# ============================================================

class EquipmentItemImportSpec(ImportSpec):
    key = "equipment"
    label = "Equipment Items"
    model = EquipmentItem
    
    columns = [
        ColumnSpec("name", "Name", example="Portable PA System"),
        ColumnSpec("description", "Description", required=False, example="100W speaker with microphone"),
        ColumnSpec("serial_number", "Serial Number", required=False, example="SN-2026-001"),
        ColumnSpec("condition", "Condition", example="good",
                   choices=['excellent', 'good', 'fair', 'poor', 'broken', 'lost']),
        ColumnSpec("quantity", "Quantity", example="2"),
        ColumnSpec("location", "Location", required=False, example="ICT Store"),
        ColumnSpec("notes", "Notes", required=False, example="Handle with care"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        if not row.get("name", "").strip():
            errors.append("Name is required.")
        
        quantity = row.get("quantity", "").strip()
        if quantity:
            try:
                val = int(quantity)
                if val < 0:
                    errors.append("Quantity cannot be negative.")
            except ValueError:
                errors.append(f"Quantity must be a whole number, got '{quantity}'.")
        
        condition = row.get("condition", "").strip().lower()
        valid_conditions = [c[0] for c in EquipmentItem.CONDITION_CHOICES]
        if condition and condition not in valid_conditions:
            errors.append(f"Condition must be one of: {', '.join(valid_conditions)}")
        
        return errors
    
    def build_instance(self, row):
        qty = int(row.get("quantity", 1))
        return EquipmentItem.objects.create(
            name=row["name"].strip(),
            description=row.get("description", "").strip(),
            serial_number=row.get("serial_number", "").strip(),
            condition=row.get("condition", "good").strip().lower(),
            quantity=qty,
            available_quantity=qty,
            location=row.get("location", "").strip(),
            notes=row.get("notes", "").strip(),
            is_active=True,
        )
    
    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "description": instance.description,
            "serial_number": instance.serial_number,
            "condition": instance.condition,
            "quantity": instance.quantity,
            "location": instance.location,
            "notes": instance.notes,
        }


# ============================================================
# 5. SHOP ITEM IMPORT/EXPORT
# ============================================================

class ShopItemImportSpec(ImportSpec):
    key = "shop_items"
    label = "Shop Items"
    model = ShopItem
    
    columns = [
        ColumnSpec("name", "Name", example="Lab Coat Size M"),
        ColumnSpec("description", "Description", required=False, example="White cotton lab coat"),
        ColumnSpec("price", "Price (₦)", example="5000.00"),
        ColumnSpec("is_free", "Is Free?", required=False, example="No"),
        ColumnSpec("category", "Category", example="labcoats",
                   choices=['merchandise', 'stationery', 'books', 'labcoats', 'accessories', 'other']),
        ColumnSpec("quantity_in_stock", "Quantity in Stock", example="10"),
        ColumnSpec("collection_center", "Collection Center", required=False, example="ICT Office"),
        ColumnSpec("collection_instructions", "Collection Instructions", required=False, example="Bring ID"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        if not row.get("name", "").strip():
            errors.append("Name is required.")
        
        # Validate price
        price = row.get("price", "").strip()
        if price:
            try:
                val = float(price)
                if val < 0:
                    errors.append("Price cannot be negative.")
            except ValueError:
                errors.append(f"Price must be a number, got '{price}'.")
        
        # Validate stock
        stock = row.get("quantity_in_stock", "").strip()
        if stock:
            try:
                val = int(stock)
                if val < 0:
                    errors.append("Stock cannot be negative.")
            except ValueError:
                errors.append(f"Stock must be a whole number, got '{stock}'.")
        
        # Validate category
        category = row.get("category", "").strip().lower()
        valid_categories = [c[0] for c in ShopItem.CATEGORY_CHOICES]
        if category and category not in valid_categories:
            errors.append(f"Category must be one of: {', '.join(valid_categories)}")
        
        return errors
    
    def build_instance(self, row):
        is_free = row.get("is_free", "").strip().lower() in ("yes", "true", "1")
        qty = int(row.get("quantity_in_stock", 0))
        
        # Find collection center
        center_name = row.get("collection_center", "").strip()
        center = None
        if center_name:
            center = CollectionCenter.objects.filter(name__iexact=center_name).first()
        
        return ShopItem.objects.create(
            name=row["name"].strip(),
            description=row.get("description", "").strip(),
            price=float(row.get("price", 0)),
            is_free=is_free,
            category=row.get("category", "other").strip().lower(),
            quantity_in_stock=qty,
            available_quantity=qty,
            collection_center=center,
            collection_instructions=row.get("collection_instructions", "").strip(),
            is_active=True,
            is_public=True,
        )
    
    def row_from_instance(self, instance):
        return {
            "name": instance.name,
            "description": instance.description,
            "price": float(instance.price),
            "is_free": "Yes" if instance.is_free else "No",
            "category": instance.category,
            "quantity_in_stock": instance.quantity_in_stock,
            "collection_center": instance.collection_center.name if instance.collection_center else "",
            "collection_instructions": instance.collection_instructions,
        }


# ============================================================
# 6. SELLABLE FORM IMPORT/EXPORT
# ============================================================

class SellableFormImportSpec(ImportSpec):
    key = "sellable_forms"
    label = "Sellable Forms"
    model = SellableForm
    
    columns = [
        ColumnSpec("title", "Title", example="Islamiyyah Registration"),
        ColumnSpec("description", "Description", required=False, example="Register for Islamiyyah classes"),
        ColumnSpec("price", "Price (₦)", example="2000.00"),
        ColumnSpec("payment_methods", "Payment Methods", example="paystack",
                   choices=['paystack', 'manual', 'both']),
        ColumnSpec("instruction_text", "Instructions", required=False, example="Bring your student ID"),
        ColumnSpec("collection_center", "Collection Center", required=False, example="ICT Office"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        if not row.get("title", "").strip():
            errors.append("Title is required.")
        
        price = row.get("price", "").strip()
        if price:
            try:
                val = float(price)
                if val < 0:
                    errors.append("Price cannot be negative.")
            except ValueError:
                errors.append(f"Price must be a number, got '{price}'.")
        
        return errors
    
    def build_instance(self, row):
        center_name = row.get("collection_center", "").strip()
        center = None
        if center_name:
            center = CollectionCenter.objects.filter(name__iexact=center_name).first()
        
        return SellableForm.objects.create(
            title=row["title"].strip(),
            description=row.get("description", "").strip(),
            price=float(row.get("price", 0)),
            payment_methods=row.get("payment_methods", "paystack").strip().lower(),
            instruction_text=row.get("instruction_text", "").strip(),
            collection_center=center,
            is_active=True,
            is_public=True,
        )
    
    def row_from_instance(self, instance):
        return {
            "title": instance.title,
            "description": instance.description,
            "price": float(instance.price),
            "payment_methods": instance.payment_methods,
            "instruction_text": instance.instruction_text,
            "collection_center": instance.collection_center.name if instance.collection_center else "",
        }


# ============================================================
# 7. BOOKING LISTING IMPORT/EXPORT
# ============================================================

class BookingListingImportSpec(ImportSpec):
    key = "booking_listings"
    label = "Booking Listings"
    model = BookingListing
    
    columns = [
        ColumnSpec("category", "Category", example="event_ticket",
                   choices=['event_ticket', 'travel', 'workshop', 'other']),
        ColumnSpec("title", "Title", example="NAMETS Week 2026"),
        ColumnSpec("description", "Description", required=False, example="Annual NAMETS Week celebration"),
        ColumnSpec("price", "Price (₦)", example="1000.00"),
        ColumnSpec("quantity_available", "Quantity Available", example="50"),
        ColumnSpec("venue", "Venue", required=False, example="Engineering Mosque"),
        ColumnSpec("date_time", "Date/Time", required=False, example="2026-09-15 10:00"),
        ColumnSpec("instructions", "Instructions", required=False, example="Bring your ticket"),
        ColumnSpec("collection_center", "Collection Center", required=False, example="ICT Office"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        if not row.get("title", "").strip():
            errors.append("Title is required.")
        
        price = row.get("price", "").strip()
        if price:
            try:
                val = float(price)
                if val < 0:
                    errors.append("Price cannot be negative.")
            except ValueError:
                errors.append(f"Price must be a number, got '{price}'.")
        
        qty = row.get("quantity_available", "").strip()
        if qty:
            try:
                val = int(qty)
                if val < 0:
                    errors.append("Quantity cannot be negative.")
            except ValueError:
                errors.append(f"Quantity must be a whole number, got '{qty}'.")
        
        return errors
    
    def build_instance(self, row):
        center_name = row.get("collection_center", "").strip()
        center = None
        if center_name:
            center = CollectionCenter.objects.filter(name__iexact=center_name).first()
        
        date_str = row.get("date_time", "").strip()
        date = None
        if date_str:
            try:
                for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y']:
                    try:
                        date = timezone.datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except:
                pass
        
        return BookingListing.objects.create(
            category=row.get("category", "other").strip().lower(),
            title=row["title"].strip(),
            description=row.get("description", "").strip(),
            price=float(row.get("price", 0)),
            quantity_available=int(row.get("quantity_available", 0)),
            venue=row.get("venue", "").strip(),
            date_time=date,
            instructions=row.get("instructions", "").strip(),
            collection_center=center,
            is_active=True,
            is_public=True,
        )
    
    def row_from_instance(self, instance):
        return {
            "category": instance.category,
            "title": instance.title,
            "description": instance.description,
            "price": float(instance.price),
            "quantity_available": instance.quantity_available,
            "venue": instance.venue,
            "date_time": instance.date_time.strftime("%Y-%m-%d %H:%M") if instance.date_time else "",
            "instructions": instance.instructions,
            "collection_center": instance.collection_center.name if instance.collection_center else "",
        }


# ============================================================
# 8. FREE CLAIM IMPORT/EXPORT (Admin Only)
# ============================================================

class FreeClaimImportSpec(ImportSpec):
    key = "free_claims"
    label = "Free Claims"
    model = FreeClaim
    
    columns = [
        ColumnSpec("item_name", "Item Name", example="Book: Engineering Mathematics"),
        ColumnSpec("claimant_name", "Claimant Name", example="Aminu Abdullah"),
        ColumnSpec("claimant_email", "Email", example="amin@email.com"),
        ColumnSpec("claimant_phone", "Phone", example="08012345678"),
        ColumnSpec("collection_center", "Collection Center", required=False, example="ICT Office"),
        ColumnSpec("status", "Status", example="pending", choices=['pending', 'claimed', 'expired']),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        item_name = row.get("item_name", "").strip()
        if item_name and not ShopItem.objects.filter(name__iexact=item_name, is_free=True).exists():
            errors.append(f"Free item '{item_name}' not found.")
        
        if not row.get("claimant_name", "").strip():
            errors.append("Claimant name is required.")
        
        return errors
    
    def build_instance(self, row):
        item = ShopItem.objects.get(name__iexact=row["item_name"].strip(), is_free=True)
        center_name = row.get("collection_center", "").strip()
        center = None
        if center_name:
            center = CollectionCenter.objects.filter(name__iexact=center_name).first()
        
        return FreeClaim.objects.create(
            item=item,
            claimant_name=row["claimant_name"].strip(),
            claimant_email=row.get("claimant_email", "").strip(),
            claimant_phone=row.get("claimant_phone", "").strip(),
            collection_center=center,
            status=row.get("status", "pending").strip().lower(),
        )
    
    def row_from_instance(self, instance):
        return {
            "item_name": instance.item.name,
            "claimant_name": instance.claimant_name,
            "claimant_email": instance.claimant_email,
            "claimant_phone": instance.claimant_phone,
            "collection_center": instance.collection_center.name if instance.collection_center else "",
            "status": instance.status,
        }


# ============================================================
# 9. BOOKING IMPORT/EXPORT (Admin Only)
# ============================================================

class BookingImportSpec(ImportSpec):
    key = "bookings"
    label = "Bookings"
    model = Booking
    
    columns = [
        ColumnSpec("listing_title", "Listing Title", example="NAMETS Week 2026"),
        ColumnSpec("booker_name", "Booker Name", example="Aminu Abdullah"),
        ColumnSpec("booker_email", "Email", example="amin@email.com"),
        ColumnSpec("booker_phone", "Phone", example="08012345678"),
        ColumnSpec("quantity", "Quantity", example="1"),
        ColumnSpec("total_amount", "Total Amount (₦)", example="1000.00"),
        ColumnSpec("status", "Status", example="pending", choices=['pending', 'paid', 'checked_in', 'cancelled']),
        ColumnSpec("collection_center", "Collection Center", required=False, example="ICT Office"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        listing_title = row.get("listing_title", "").strip()
        if listing_title and not BookingListing.objects.filter(title__iexact=listing_title).exists():
            errors.append(f"Booking listing '{listing_title}' not found.")
        
        if not row.get("booker_name", "").strip():
            errors.append("Booker name is required.")
        
        qty = row.get("quantity", "").strip()
        if qty:
            try:
                val = int(qty)
                if val < 1:
                    errors.append("Quantity must be at least 1.")
            except ValueError:
                errors.append(f"Quantity must be a whole number, got '{qty}'.")
        
        return errors
    
    def build_instance(self, row):
        listing = BookingListing.objects.get(title__iexact=row["listing_title"].strip())
        center_name = row.get("collection_center", "").strip()
        center = None
        if center_name:
            center = CollectionCenter.objects.filter(name__iexact=center_name).first()
        
        qty = int(row.get("quantity", 1))
        total = float(row.get("total_amount", listing.price * qty))
        
        return Booking.objects.create(
            listing=listing,
            booker_name=row["booker_name"].strip(),
            booker_email=row.get("booker_email", "").strip(),
            booker_phone=row.get("booker_phone", "").strip(),
            quantity=qty,
            total_amount=total,
            status=row.get("status", "pending").strip().lower(),
            collection_center=center,
        )
    
    def row_from_instance(self, instance):
        return {
            "listing_title": instance.listing.title,
            "booker_name": instance.booker_name,
            "booker_email": instance.booker_email,
            "booker_phone": instance.booker_phone,
            "quantity": instance.quantity,
            "total_amount": float(instance.total_amount),
            "status": instance.status,
            "collection_center": instance.collection_center.name if instance.collection_center else "",
        }


# ============================================================
# 10. FORM PURCHASE IMPORT/EXPORT (Admin Only)
# ============================================================

class FormPurchaseImportSpec(ImportSpec):
    key = "form_purchases"
    label = "Form Purchases"
    model = FormPurchase
    
    columns = [
        ColumnSpec("form_title", "Form Title", example="Islamiyyah Registration"),
        ColumnSpec("buyer_name", "Buyer Name", example="Aminu Abdullah"),
        ColumnSpec("buyer_email", "Email", example="amin@email.com"),
        ColumnSpec("buyer_phone", "Phone", example="08012345678"),
        ColumnSpec("amount_paid", "Amount Paid (₦)", example="2000.00"),
        ColumnSpec("payment_method", "Payment Method", example="paystack", choices=['paystack', 'manual', 'both']),
        ColumnSpec("status", "Status", example="pending", choices=['pending', 'paid', 'verified', 'cancelled']),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        form_title = row.get("form_title", "").strip()
        if form_title and not SellableForm.objects.filter(title__iexact=form_title).exists():
            errors.append(f"Sellable form '{form_title}' not found.")
        
        if not row.get("buyer_name", "").strip():
            errors.append("Buyer name is required.")
        
        amount = row.get("amount_paid", "").strip()
        if amount:
            try:
                val = float(amount)
                if val < 0:
                    errors.append("Amount cannot be negative.")
            except ValueError:
                errors.append(f"Amount must be a number, got '{amount}'.")
        
        return errors
    
    def build_instance(self, row):
        form = SellableForm.objects.get(title__iexact=row["form_title"].strip())
        
        return FormPurchase.objects.create(
            form=form,
            buyer_name=row["buyer_name"].strip(),
            buyer_email=row.get("buyer_email", "").strip(),
            buyer_phone=row.get("buyer_phone", "").strip(),
            amount_paid=float(row.get("amount_paid", 0)),
            payment_method=row.get("payment_method", "paystack").strip().lower(),
            status=row.get("status", "pending").strip().lower(),
        )
    
    def row_from_instance(self, instance):
        return {
            "form_title": instance.form.title,
            "buyer_name": instance.buyer_name,
            "buyer_email": instance.buyer_email,
            "buyer_phone": instance.buyer_phone,
            "amount_paid": float(instance.amount_paid),
            "payment_method": instance.payment_method,
            "status": instance.status,
        }


# ============================================================
# 11. SHOP ORDER IMPORT/EXPORT (Admin Only)
# ============================================================

class ShopOrderImportSpec(ImportSpec):
    key = "shop_orders"
    label = "Shop Orders"
    model = ShopOrder
    
    columns = [
        ColumnSpec("item_name", "Item Name", example="Lab Coat Size M"),
        ColumnSpec("buyer_name", "Buyer Name", example="Aminu Abdullah"),
        ColumnSpec("buyer_email", "Email", example="amin@email.com"),
        ColumnSpec("buyer_phone", "Phone", example="08012345678"),
        ColumnSpec("quantity", "Quantity", example="1"),
        ColumnSpec("total_amount", "Total Amount (₦)", example="5000.00"),
        ColumnSpec("status", "Status", example="pending", choices=['pending', 'paid', 'collected', 'cancelled']),
        ColumnSpec("collection_center", "Collection Center", required=False, example="ICT Office"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        item_name = row.get("item_name", "").strip()
        if item_name and not ShopItem.objects.filter(name__iexact=item_name).exists():
            errors.append(f"Shop item '{item_name}' not found.")
        
        if not row.get("buyer_name", "").strip():
            errors.append("Buyer name is required.")
        
        qty = row.get("quantity", "").strip()
        if qty:
            try:
                val = int(qty)
                if val < 1:
                    errors.append("Quantity must be at least 1.")
            except ValueError:
                errors.append(f"Quantity must be a whole number, got '{qty}'.")
        
        return errors
    
    def build_instance(self, row):
        item = ShopItem.objects.get(name__iexact=row["item_name"].strip())
        center_name = row.get("collection_center", "").strip()
        center = None
        if center_name:
            center = CollectionCenter.objects.filter(name__iexact=center_name).first()
        
        qty = int(row.get("quantity", 1))
        total = float(row.get("total_amount", item.price * qty))
        
        return ShopOrder.objects.create(
            item=item,
            buyer_name=row["buyer_name"].strip(),
            buyer_email=row.get("buyer_email", "").strip(),
            buyer_phone=row.get("buyer_phone", "").strip(),
            quantity=qty,
            total_amount=total,
            status=row.get("status", "pending").strip().lower(),
            collection_center=center,
        )
    
    def row_from_instance(self, instance):
        return {
            "item_name": instance.item.name,
            "buyer_name": instance.buyer_name,
            "buyer_email": instance.buyer_email,
            "buyer_phone": instance.buyer_phone,
            "quantity": instance.quantity,
            "total_amount": float(instance.total_amount),
            "status": instance.status,
            "collection_center": instance.collection_center.name if instance.collection_center else "",
        }


# ============================================================
# 12. EQUIPMENT BORROW IMPORT/EXPORT (Admin Only)
# ============================================================

class EquipmentBorrowImportSpec(ImportSpec):
    key = "equipment_borrows"
    label = "Equipment Borrow Records"
    model = EquipmentBorrow
    
    columns = [
        ColumnSpec("item_name", "Item Name", example="Portable PA System"),
        ColumnSpec("borrower_name", "Borrower Name", example="Aminu Abdullah"),
        ColumnSpec("borrower_phone", "Phone", example="08012345678"),
        ColumnSpec("borrower_email", "Email", required=False, example="amin@email.com"),
        ColumnSpec("borrower_department", "Department", required=False, example="Mechanical Engineering"),
        ColumnSpec("expected_return_date", "Expected Return Date", example="2026-09-16 17:00"),
        ColumnSpec("notes", "Notes", required=False, example="For event use"),
    ]
    
    def validate_row(self, row):
        errors = super().validate_row(row)
        
        item_name = row.get("item_name", "").strip()
        if item_name and not EquipmentItem.objects.filter(name__iexact=item_name).exists():
            errors.append(f"Equipment item '{item_name}' not found.")
        
        if not row.get("borrower_name", "").strip():
            errors.append("Borrower name is required.")
        
        return errors
    
    def build_instance(self, row):
        item = EquipmentItem.objects.get(name__iexact=row["item_name"].strip())
        
        date_str = row.get("expected_return_date", "").strip()
        date = timezone.now() + timezone.timedelta(days=7)
        if date_str:
            try:
                for fmt in ['%Y-%m-%d %H:%M', '%Y-%m-%d', '%d/%m/%Y %H:%M', '%d/%m/%Y']:
                    try:
                        date = timezone.datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
            except:
                pass
        
        # We need to set borrowed_by to a user; for import, we can use a default or require it
        # For simplicity, we'll use the first superuser or create a placeholder
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user = User.objects.filter(is_active=True).first()
        
        if not user:
            # Create a placeholder user if none exists (shouldn't happen in production)
            user = User.objects.create_user(username='import_user', password='temp123')
        
        return EquipmentBorrow.objects.create(
            item=item,
            borrowed_by=user,
            borrower_name=row["borrower_name"].strip(),
            borrower_phone=row.get("borrower_phone", "").strip(),
            borrower_email=row.get("borrower_email", "").strip(),
            borrower_department=row.get("borrower_department", "").strip(),
            expected_return_date=date,
            notes=row.get("notes", "").strip(),
            status='borrowed',
        )
    
    def row_from_instance(self, instance):
        return {
            "item_name": instance.item.name,
            "borrower_name": instance.borrower_name,
            "borrower_phone": instance.borrower_phone,
            "borrower_email": instance.borrower_email,
            "borrower_department": instance.borrower_department,
            "expected_return_date": instance.expected_return_date.strftime("%Y-%m-%d %H:%M"),
            "notes": instance.notes,
        }


# ============================================================
# REGISTER ALL SPECS
# ============================================================

register(CollectionCenterImportSpec())
register(BankAccountImportSpec())
register(TransactionImportSpec())
register(EquipmentItemImportSpec())
register(EquipmentBorrowImportSpec())
register(ShopItemImportSpec())
register(ShopOrderImportSpec())
register(SellableFormImportSpec())
register(FormPurchaseImportSpec())
register(BookingListingImportSpec())
register(BookingImportSpec())
register(FreeClaimImportSpec())