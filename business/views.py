# business/views.py
# Business App — Complete Views (Public + Admin/EXCO)

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.conf import settings
from django.urls import reverse
import json
import hashlib
import hmac
import uuid
import requests

from datetime import timedelta
from django.db.models import Q, Sum, Count
from django.utils import timezone

from django.http import Http404

from django.views.decorators.http import require_POST

from django.db.models import Sum
from datetime import timedelta


from . import models

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
from .forms import (
    CollectionCenterForm,
    BankAccountForm,
    TransactionForm,
    TransactionCorrectionForm,
    EquipmentItemForm,
    EquipmentBorrowForm,
    ShopItemForm,
    ShopOrderForm,
    ShopOrderGuestForm,
    FreeClaimForm,
    FreeClaimAdminForm,
    SellableFormForm,
    FormPurchaseForm,
    BookingListingForm,
    BookingGuestForm,
    BookingAdminForm,
    GuestLookupForm,
)
from accounts.decorators import office_required
from core.email_utils import send_templated_email
from core.importers.spec import ColumnSpec, ImportSpec
from core.importers.excel_io import build_export_xlsx

import logging
logger = logging.getLogger(__name__)


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def get_guest_lookup_results(model, code_field, code_value, email, phone):
    """
    Helper to lookup a guest record by code or email+phone.
    Returns a queryset or None.
    """
    if code_value:
        filter_kwargs = {code_field: code_value}
        return model.objects.filter(**filter_kwargs).first()
    
    if email or phone:
        q = Q()
        if email:
            q &= Q(booker_email__iexact=email) | Q(buyer_email__iexact=email) | Q(claimant_email__iexact=email)
        if phone:
            q &= Q(booker_phone__iexact=phone) | Q(buyer_phone__iexact=phone) | Q(claimant_phone__iexact=phone)
        # Try each model — simplified, we'll handle per model in the view
        return None
    
    return None


def generate_paystack_reference():
    """Generate a unique Paystack reference."""
    return f"NAMETS-{uuid.uuid4().hex[:8].upper()}-{timezone.now().timestamp():.0f}"


# ============================================================
# 1. PUBLIC VIEWS (Guest-Facing)
# ============================================================

# ---------- SHOP PUBLIC ----------

def shop_catalog(request):
    """Public shop catalog — show items available for purchase."""
    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    
    items = ShopItem.objects.filter(is_active=True, is_public=True, quantity_in_stock__gt=0)
    
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_filter:
        items = items.filter(category=category_filter)
    
    items = items.order_by('-created_at')
    
    paginator = Paginator(items, 12)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)
    
    return render(request, 'business/public/shop_catalog.html', {
        'items': items_page,
        'page_obj': items_page,
        'is_paginated': items_page.has_other_pages(),
        'query': query,
        'category_filter': category_filter,
    })


def shop_item_detail(request, item_id):
    """Public shop item detail page."""
    item = get_object_or_404(ShopItem, id=item_id, is_active=True, is_public=True)
    
    if request.method == 'POST':
        form = ShopOrderGuestForm(request.POST)
        if form.is_valid():
            if not item.is_in_stock():
                messages.error(request, "This item is out of stock.")
                return redirect('business:shop_item_detail', item_id=item.id)
            
            order = form.save(commit=False)
            order.item = item
            order.total_amount = item.price * order.quantity
            
            if item.is_free:
                # Free item — auto-approve
                order.status = 'paid'
                order.save()
                # Decrement stock
                item.available_quantity -= order.quantity
                item.save()
                messages.success(request, f"✅ '{item.name}' claimed successfully! Your collection code: {order.collection_code}")
                return redirect('business:guest_lookup')  # Or a success page
            else:
                # Paid item — initiate Paystack payment
                order.status = 'pending'
                order.save()
                return redirect('business:shop_checkout', order_id=order.id)
    else:
        form = ShopOrderGuestForm()
    
    return render(request, 'business/public/shop_detail.html', {
        'item': item,
        'form': form,
    })


def shop_checkout(request, order_id):
    """Paystack checkout for shop orders."""
    order = get_object_or_404(ShopOrder, id=order_id, status='pending')

    if order.item.is_free:
        messages.error(request, "This item is free. Please go back and claim it.")
        return redirect('business:shop_item_detail', item_id=order.item.id)

    paystack_public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    paystack_secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')

    if not paystack_public_key or not paystack_secret_key:
        messages.error(request, "Payment is currently unavailable. Please try again later.")
        return redirect('business:shop_catalog')

    reference = generate_paystack_reference()
    order.payment_reference = reference
    order.save()

    return render(request, 'business/public/paystack_checkout.html', {
        'order': order,
        'paystack_public_key': paystack_public_key,
        'reference': reference,
        'amount': int(order.total_amount * 100),
        'callback_url': request.build_absolute_uri(reverse('business:paystack_callback')),
        'type': 'shop',
        'customer_name': order.buyer_name,
        'customer_email': order.buyer_email,
        'order_title': order.item.name,
        'order_quantity': order.quantity,
        'order_total': order.total_amount,
    })
    
    
    
    
def _verify_paystack_reference(reference):
    """
    Verify a payment reference directly with Paystack's API.
    Returns the transaction data dict on success, None otherwise.
    """
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    if not secret_key or not reference:
        return None
    try:
        resp = requests.get(
            f'https://api.paystack.co/transaction/verify/{reference}',
            headers={'Authorization': f'Bearer {secret_key}'},
            timeout=15,
        )
        data = resp.json()
        if data.get('status') and data.get('data', {}).get('status') == 'success':
            return data['data']
        logger.warning(f"Paystack verify non-success: {data}")
    except Exception as e:
        logger.error(f"Paystack verify error: {e}")
    return None


# ---------- FREE CLAIMS PUBLIC ----------

def free_claims_catalog(request):
    """Public free items catalog."""
    items = ShopItem.objects.filter(
        is_active=True, 
        is_public=True, 
        is_free=True,
        available_quantity__gt=0
    ).order_by('-created_at')
    
    return render(request, 'business/public/free_claims.html', {
        'items': items,
    })


def free_claim_submit(request, item_id):
    """Submit a free claim."""
    item = get_object_or_404(ShopItem, id=item_id, is_active=True, is_free=True)
    
    if not item.is_in_stock():
        messages.error(request, "This item is out of stock.")
        return redirect('business:free_claims_catalog')
    
    if request.method == 'POST':
        form = FreeClaimForm(request.POST)
        if form.is_valid():
            claim = form.save(commit=False)
            claim.item = item
            claim.save()
            
            # Decrement available quantity
            item.available_quantity -= 1
            item.save()
            
            messages.success(request, f"✅ '{item.name}' claimed successfully! Your claim code: {claim.claim_code}")
            
            # Send confirmation email
            send_templated_email(
                subject=f"Your NAMETS Claim Code: {claim.claim_code}",
                recipients=[claim.claimant_email],
                template_name='emails/free_claim_confirmation.html',
                context={
                    'claim': claim,
                    'item': item,
                },
                category='general'
            )
            
            return redirect('business:free_claim_success', claim_code=claim.claim_code)
    else:
        form = FreeClaimForm(initial={'item': item})
    
    return render(request, 'business/public/free_claim_form.html', {
        'item': item,
        'form': form,
    })


def free_claim_success(request, claim_code):
    """Success page after free claim."""
    claim = get_object_or_404(FreeClaim, claim_code=claim_code)
    return render(request, 'business/public/free_claim_success.html', {'claim': claim})


# ---------- BOOKINGS PUBLIC ----------

def bookings_catalog(request):
    """Public booking listings."""
    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    
    listings = BookingListing.objects.filter(
        is_active=True, 
        is_public=True,
        quantity_available__gt=0
    )
    
    if query:
        listings = listings.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if category_filter:
        listings = listings.filter(category=category_filter)
    
    listings = listings.order_by('-date_time', '-created_at')
    
    return render(request, 'business/public/booking_listings.html', {
        'listings': listings,
        'query': query,
        'category_filter': category_filter,
    })


def booking_detail(request, booking_id):
    """Public booking detail page."""
    listing = get_object_or_404(BookingListing, id=booking_id, is_active=True, is_public=True)
    
    if request.method == 'POST':
        form = BookingGuestForm(request.POST)
        if form.is_valid():
            if not listing.is_available():
                messages.error(request, "This booking is no longer available.")
                return redirect('business:booking_detail', booking_id=listing.id)
            
            booking = form.save(commit=False)
            booking.listing = listing
            booking.total_amount = listing.price * booking.quantity
            
            if listing.price == 0:
                # Free booking — auto-approve
                booking.status = 'paid'
                booking.save()
                listing.quantity_available -= booking.quantity
                listing.save()
                messages.success(request, f"✅ '{listing.title}' booked successfully!")
                return redirect('business:guest_lookup')
            else:
                # Paid booking — initiate Paystack
                booking.status = 'pending'
                booking.save()
                return redirect('business:booking_checkout', booking_id=booking.id)
    else:
        form = BookingGuestForm()
    
    return render(request, 'business/public/booking_detail.html', {
        'listing': listing,
        'form': form,
    })


def booking_checkout(request, booking_id):
    """Paystack checkout for bookings."""
    booking = get_object_or_404(Booking, id=booking_id, status='pending')

    paystack_public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    paystack_secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')

    if not paystack_public_key or not paystack_secret_key:
        messages.error(request, "Payment is currently unavailable. Please try again later.")
        return redirect('business:booking_detail', booking_id=booking.listing.id)

    reference = generate_paystack_reference()
    booking.payment_reference = reference
    booking.save()

    return render(request, 'business/public/paystack_checkout.html', {
        'order': booking,
        'paystack_public_key': paystack_public_key,
        'reference': reference,
        'amount': int(booking.total_amount * 100),
        'callback_url': request.build_absolute_uri(reverse('business:paystack_callback')),
        'type': 'booking',
        'customer_name': booking.booker_name,
        'customer_email': booking.booker_email,
        'order_title': booking.listing.title,
        'order_quantity': booking.quantity,
        'order_total': booking.total_amount,
    })


# ---------- SELLABLE FORMS PUBLIC ----------

def sellable_forms_catalog(request):
    """Public sellable forms catalog."""
    forms = SellableForm.objects.filter(is_active=True, is_public=True).order_by('title')
    return render(request, 'business/public/sellable_forms.html', {'forms': forms})



def sellable_form_purchase(request, form_id):
    """Purchase a sellable form."""
    form_obj = get_object_or_404(SellableForm, id=form_id, is_active=True, is_public=True)
    
    if request.method == 'POST':
        # For now, just show the checkout
        purchase = FormPurchase.objects.create(
            form=form_obj,
            buyer_name=request.POST.get('buyer_name', ''),
            buyer_email=request.POST.get('buyer_email', ''),
            buyer_phone=request.POST.get('buyer_phone', ''),
            amount_paid=form_obj.price,
            payment_method='paystack',
            status='pending',
        )
        return redirect('business:form_checkout', purchase_id=purchase.id)
    
    return render(request, 'business/public/sellable_form_purchase.html', {'form': form_obj})


def form_checkout(request, purchase_id):
    """Paystack checkout for form purchases."""
    purchase = get_object_or_404(FormPurchase, id=purchase_id, status='pending')

    paystack_public_key = getattr(settings, 'PAYSTACK_PUBLIC_KEY', '')
    paystack_secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')

    if not paystack_public_key or not paystack_secret_key:
        messages.error(request, "Payment is currently unavailable. Please try again later.")
        return redirect('business:sellable_forms_catalog')

    reference = generate_paystack_reference()
    purchase.payment_reference = reference
    purchase.save()

    return render(request, 'business/public/paystack_checkout.html', {
        'order': purchase,
        'paystack_public_key': paystack_public_key,
        'reference': reference,
        'amount': int(purchase.amount_paid * 100),
        'callback_url': request.build_absolute_uri(reverse('business:paystack_callback')),
        'type': 'form',
        'customer_name': purchase.buyer_name,
        'customer_email': purchase.buyer_email,
        'order_title': purchase.form.title,
        'order_quantity': None,
        'order_total': purchase.amount_paid,
    })


# ---------- PUBLIC DONATIONS ----------

def public_donations(request):
    """Public donations page showing bank accounts with is_public=True."""
    accounts = BankAccount.objects.filter(is_active=True, is_public=True)
    campaigns = []
    # If you have donation campaigns, show them here
    try:
        from communications.models import DonationCampaign
        campaigns = DonationCampaign.objects.filter(is_active=True)
    except ImportError:
        pass
    
    return render(request, 'business/public/donations.html', {
        'accounts': accounts,
        'campaigns': campaigns,
    })




def _perform_guest_lookup(lookup_type, code, email, phone):
    """
    Shared lookup logic for guest_lookup (POST form + GET redirect).
    Returns (results, guest_info).
    """
    results = []
    guest_info = {'name': '', 'email': email, 'phone': phone}

    if lookup_type == 'code' and code:
        shop_order = ShopOrder.objects.filter(collection_code__iexact=code).first()
        if shop_order:
            results.append({
                'type': 'Shop Order', 'object': shop_order,
                'status': shop_order.status,
                'url_name': 'business:shop_item_detail',
                'url_arg': shop_order.item.id,
                'cancel_type': 'shop_order',
            })

        free_claim = FreeClaim.objects.filter(claim_code__iexact=code).first()
        if free_claim:
            results.append({
                'type': 'Free Claim', 'object': free_claim,
                'status': free_claim.status,
                'url_name': 'business:free_claims_catalog',
                'url_arg': None,
                'cancel_type': 'free_claim',
            })

        form_purchase = FormPurchase.objects.filter(access_code__iexact=code).first()
        if form_purchase:
            results.append({
                'type': 'Form Purchase', 'object': form_purchase,
                'status': form_purchase.status,
                'url_name': 'business:sellable_forms_catalog',
                'url_arg': None,
                'cancel_type': 'form_purchase',
            })

        booking = Booking.objects.filter(qr_token__startswith=code).first()
        if booking:
            results.append({
                'type': 'Booking', 'object': booking,
                'status': booking.status,
                'url_name': 'business:booking_detail',
                'url_arg': booking.listing.id,
                'cancel_type': 'booking',
            })

    elif lookup_type == 'contact' and (email or phone):
        # Shop orders
        q = Q()
        if email:
            q |= Q(buyer_email__iexact=email)
        if phone:
            q |= Q(buyer_phone__iexact=phone)
        for o in ShopOrder.objects.filter(q):
            results.append({
                'type': 'Shop Order', 'object': o,
                'status': o.status,
                'url_name': 'business:shop_item_detail',
                'url_arg': o.item.id,
                'cancel_type': 'shop_order',
            })

        # Free claims
        q = Q()
        if email:
            q |= Q(claimant_email__iexact=email)
        if phone:
            q |= Q(claimant_phone__iexact=phone)
        for f in FreeClaim.objects.filter(q):
            results.append({
                'type': 'Free Claim', 'object': f,
                'status': f.status,
                'url_name': 'business:free_claims_catalog',
                'url_arg': None,
                'cancel_type': 'free_claim',
            })

        # Form purchases
        q = Q()
        if email:
            q |= Q(buyer_email__iexact=email)
        if phone:
            q |= Q(buyer_phone__iexact=phone)
        for fp in FormPurchase.objects.filter(q):
            results.append({
                'type': 'Form Purchase', 'object': fp,
                'status': fp.status,
                'url_name': 'business:sellable_forms_catalog',
                'url_arg': None,
                'cancel_type': 'form_purchase',
            })

        # Bookings
        q = Q()
        if email:
            q |= Q(booker_email__iexact=email)
        if phone:
            q |= Q(booker_phone__iexact=phone)
        for b in Booking.objects.filter(q):
            results.append({
                'type': 'Booking', 'object': b,
                'status': b.status,
                'url_name': 'business:booking_detail',
                'url_arg': b.listing.id,
                'cancel_type': 'booking',
            })

    # Extract guest display info from first result
    if results:
        obj = results[0]['object']
        guest_info['name'] = (
            getattr(obj, 'booker_name', '') or
            getattr(obj, 'buyer_name', '') or
            getattr(obj, 'claimant_name', '') or ''
        )
        if not guest_info['email']:
            guest_info['email'] = (
                getattr(obj, 'booker_email', '') or
                getattr(obj, 'buyer_email', '') or
                getattr(obj, 'claimant_email', '') or ''
            )
        if not guest_info['phone']:
            guest_info['phone'] = (
                getattr(obj, 'booker_phone', '') or
                getattr(obj, 'buyer_phone', '') or
                getattr(obj, 'claimant_phone', '') or ''
            )

    return results, guest_info


# ---------- GUEST LOOKUP ----------
def guest_lookup(request):
    """
    Unified guest lookup. Handles:
    - POST from the search form
    - GET redirect back after cancel (query params)
    """
    results = []
    lookup_type = None
    guest_info = {'name': '', 'email': '', 'phone': ''}
    search_params = {'lookup_type': '', 'code': '', 'email': '', 'phone': ''}

    if request.method == 'POST':
        form = GuestLookupForm(request.POST)
        if form.is_valid():
            lookup_type = form.cleaned_data.get('lookup_type')
            code = form.cleaned_data.get('code', '').strip()
            email = form.cleaned_data.get('email', '').strip()
            phone = form.cleaned_data.get('phone', '').strip()

            search_params = {
                'lookup_type': lookup_type,
                'code': code,
                'email': email,
                'phone': phone,
            }

            results, guest_info = _perform_guest_lookup(lookup_type, code, email, phone)

            if not results:
                if lookup_type == 'code':
                    messages.warning(request, "No record found with that code.")
                else:
                    messages.warning(request, "No records found with that email or phone.")

    elif request.GET.get('lookup_type'):
        # Came back from a cancel redirect — re-run the same lookup
        form = GuestLookupForm(request.GET)
        if form.is_valid():
            lookup_type = form.cleaned_data.get('lookup_type')
            code = form.cleaned_data.get('code', '').strip()
            email = form.cleaned_data.get('email', '').strip()
            phone = form.cleaned_data.get('phone', '').strip()

            search_params = {
                'lookup_type': lookup_type,
                'code': code,
                'email': email,
                'phone': phone,
            }

            results, guest_info = _perform_guest_lookup(lookup_type, code, email, phone)
    else:
        form = GuestLookupForm()

    return render(request, 'business/public/guest_lookup.html', {
        'form': form,
        'results': results,
        'lookup_type': lookup_type,
        'guest_info': guest_info,
        'search_params': search_params,
    })



# ============================================================
# 2. PAYSTACK PAYMENT VIEWS
# ============================================================

@csrf_exempt
def paystack_webhook(request):
    """Handle Paystack webhook events."""
    # Verify signature
    signature = request.headers.get('x-paystack-signature')
    secret_key = getattr(settings, 'PAYSTACK_SECRET_KEY', '')
    
    if not signature or not secret_key:
        return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
    
    try:
        body = request.body
        expected = hmac.new(
            secret_key.encode(),
            body,
            hashlib.sha512
        ).hexdigest()
        
        if not hmac.compare_digest(signature, expected):
            return JsonResponse({'status': 'error', 'message': 'Invalid signature'}, status=400)
    except Exception as e:
        logger.error(f"Webhook signature verification failed: {e}")
        return JsonResponse({'status': 'error', 'message': 'Verification failed'}, status=400)
    
    try:
        data = json.loads(body)
        event = data.get('event')
        
        if event == 'charge.success':
            reference = data.get('data', {}).get('reference', '')
            logger.info(f"Paystack webhook: successful charge for {reference}")
            
            # Find which type of purchase this is
            shop_order = ShopOrder.objects.filter(payment_reference=reference, status='pending').first()
            if shop_order:
                shop_order.mark_paid(reference)
                logger.info(f"Shop order {shop_order.collection_code} marked as paid.")
                
                # Send confirmation email
                send_templated_email(
                    subject=f"Payment Confirmation: {shop_order.item.name}",
                    recipients=[shop_order.buyer_email],
                    template_name='emails/shop_order_confirmation.html',
                    context={'order': shop_order},
                    category='general'
                )
                return JsonResponse({'status': 'ok'})
            
            booking = Booking.objects.filter(payment_reference=reference, status='pending').first()
            if booking:
                booking.mark_paid(reference)
                logger.info(f"Booking {booking.qr_token[:12]} marked as paid.")
                
                # Send confirmation email with QR code
                send_templated_email(
                    subject=f"Booking Confirmation: {booking.listing.title}",
                    recipients=[booking.booker_email],
                    template_name='emails/booking_confirmation.html',
                    context={'booking': booking},
                    category='general'
                )
                return JsonResponse({'status': 'ok'})
            
            form_purchase = FormPurchase.objects.filter(payment_reference=reference, status='pending').first()
            if form_purchase:
                form_purchase.mark_paid(reference)
                logger.info(f"Form purchase {form_purchase.access_code} marked as paid.")
                
                send_templated_email(
                    subject=f"Access Code: {form_purchase.form.title}",
                    recipients=[form_purchase.buyer_email],
                    template_name='emails/form_purchase_confirmation.html',
                    context={'purchase': form_purchase},
                    category='general'
                )
                return JsonResponse({'status': 'ok'})
            
            logger.warning(f"Unhandled payment reference: {reference}")
            return JsonResponse({'status': 'warning', 'message': 'Reference not found'}, status=200)
        
        # Handle other events (optional)
        return JsonResponse({'status': 'ok'})
    
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


def paystack_callback(request):
    """
    Handle Paystack callback (return from payment page).
    NO @login_required — guests must be able to land here.
    Verifies payment directly with Paystack's API (works even without webhook).
    """
    reference = request.GET.get('reference', '').strip()
    if not reference:
        messages.error(request, "No payment reference found.")
        return redirect('business:guest_lookup')

    # Verify directly with Paystack (webhook fallback)
    verified = _verify_paystack_reference(reference)

    # --- Shop Order ---
    shop_order = ShopOrder.objects.filter(payment_reference=reference).first()
    if shop_order:
        if verified and shop_order.status == 'pending':
            shop_order.mark_paid(reference)
            messages.success(
                request,
                f"✅ Payment successful! Your collection code is {shop_order.collection_code}. "
                f"Show it at the collection center."
            )
        elif shop_order.status == 'paid':
            messages.success(request, f"✅ Payment confirmed. Code: {shop_order.collection_code}")
        else:
            messages.warning(request, "Payment is still pending. Please try again or contact support.")
        return redirect('business:guest_lookup')

    # --- Booking ---
    booking = Booking.objects.filter(payment_reference=reference).first()
    if booking:
        if verified and booking.status == 'pending':
            booking.mark_paid(reference)
            messages.success(
                request,
                f"✅ Payment successful! Your booking is confirmed. "
                f"Reference: {booking.qr_token[:12]}…"
            )
        elif booking.status == 'paid':
            messages.success(request, f"✅ Payment confirmed. Reference: {booking.qr_token[:12]}…")
        else:
            messages.warning(request, "Payment is still pending. Please try again or contact support.")
        return redirect('business:guest_lookup')

    # --- Form Purchase ---
    form_purchase = FormPurchase.objects.filter(payment_reference=reference).first()
    if form_purchase:
        if verified and form_purchase.status == 'pending':
            form_purchase.mark_paid(reference)
            messages.success(
                request,
                f"✅ Payment successful! Your access code is {form_purchase.access_code}."
            )
        elif form_purchase.status == 'paid':
            messages.success(request, f"✅ Payment confirmed. Code: {form_purchase.access_code}")
        else:
            messages.warning(request, "Payment is still pending. Please try again or contact support.")
        return redirect('business:guest_lookup')

    messages.error(request, "We couldn't find your transaction. Please contact support.")
    return redirect('business:guest_lookup')


# ============================================================
# 3. ADMIN/EXCO VIEWS
# ============================================================

# ---------- COLLECTION CENTER ADMIN ----------

@login_required
def admin_collection_center_list(request):
    if not request.user.has_perm('business.view_collectioncenter'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    query = request.GET.get('q', '')
    centers = CollectionCenter.objects.all().order_by('name')
    if query:
        centers = centers.filter(Q(name__icontains=query) | Q(location__icontains=query))
    
    paginator = Paginator(centers, 20)
    page = request.GET.get('page')
    centers_page = paginator.get_page(page)
    
    return render(request, 'business/admin/collection_center_list.html', {
        'centers': centers_page,
        'page_obj': centers_page,
        'is_paginated': centers_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_collection_center_create(request):
    if not request.user.has_perm('business.add_collectioncenter'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_collection_center_list')
    
    if request.method == 'POST':
        form = CollectionCenterForm(request.POST)
        if form.is_valid():
            center = form.save()
            messages.success(request, f"✅ Collection center '{center.name}' created.")
            return redirect('business:admin_collection_center_list')
    else:
        form = CollectionCenterForm()
    
    return render(request, 'business/admin/collection_center_form.html', {
        'form': form,
        'title': 'Add Collection Center',
        'button_text': 'Create Center',
    })


@login_required
def admin_collection_center_edit(request, pk):
    center = get_object_or_404(CollectionCenter, pk=pk)
    if not request.user.has_perm('business.change_collectioncenter'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_collection_center_list')
    
    if request.method == 'POST':
        form = CollectionCenterForm(request.POST, instance=center)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Collection center '{center.name}' updated.")
            return redirect('business:admin_collection_center_list')
    else:
        form = CollectionCenterForm(instance=center)
    
    return render(request, 'business/admin/collection_center_form.html', {
        'form': form,
        'center': center,
        'title': 'Edit Collection Center',
        'button_text': 'Update Center',
    })


@login_required
def admin_collection_center_delete(request, pk):
    center = get_object_or_404(CollectionCenter, pk=pk)
    if not request.user.has_perm('business.delete_collectioncenter'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_collection_center_list')
    
    if request.method == 'POST':
        name = center.name
        center.delete()
        messages.success(request, f"🗑️ Collection center '{name}' deleted.")
        return redirect('business:admin_collection_center_list')
    
    return render(request, 'business/admin/collection_center_confirm_delete.html', {
        'center': center,
    })


# ---------- BANK ACCOUNT ADMIN ----------

@login_required
def admin_bank_account_list(request):
    if not request.user.has_perm('business.view_bankaccount'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    query = request.GET.get('q', '')
    accounts = BankAccount.objects.all().order_by('name')
    if query:
        accounts = accounts.filter(Q(name__icontains=query) | Q(bank_name__icontains=query))
    
    paginator = Paginator(accounts, 20)
    page = request.GET.get('page')
    accounts_page = paginator.get_page(page)
    
    return render(request, 'business/admin/bank_account_list.html', {
        'accounts': accounts_page,
        'page_obj': accounts_page,
        'is_paginated': accounts_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_bank_account_create(request):
    if not request.user.has_perm('business.add_bankaccount'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_bank_account_list')
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            messages.success(request, f"✅ Bank account '{account.name}' created.")
            return redirect('business:admin_bank_account_list')
    else:
        form = BankAccountForm()
    
    return render(request, 'business/admin/bank_account_form.html', {
        'form': form,
        'title': 'Add Bank Account',
        'button_text': 'Create Account',
    })


@login_required
def admin_bank_account_edit(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    if not request.user.has_perm('business.change_bankaccount'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_bank_account_list')
    
    if request.method == 'POST':
        form = BankAccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Bank account '{account.name}' updated.")
            return redirect('business:admin_bank_account_list')
    else:
        form = BankAccountForm(instance=account)
    
    return render(request, 'business/admin/bank_account_form.html', {
        'form': form,
        'account': account,
        'title': 'Edit Bank Account',
        'button_text': 'Update Account',
    })


@login_required
def admin_bank_account_delete(request, pk):
    account = get_object_or_404(BankAccount, pk=pk)
    if not request.user.has_perm('business.delete_bankaccount'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_bank_account_list')
    
    if request.method == 'POST':
        name = account.name
        account.delete()
        messages.success(request, f"🗑️ Bank account '{name}' deleted.")
        return redirect('business:admin_bank_account_list')
    
    return render(request, 'business/admin/bank_account_confirm_delete.html', {
        'account': account,
    })


# ---------- TRANSACTION ADMIN ----------

@login_required
def admin_transaction_list(request):
    if not request.user.has_perm('business.view_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_transaction_list')
        
        if action == 'delete' and request.user.has_perm('business.delete_transaction'):
            count = Transaction.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} transaction(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_transaction_list')
    
    # Filters
    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    account_filter = request.GET.get('account', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    correction_filter = request.GET.get('correction', '')
    
    transactions = Transaction.objects.all().order_by('-date')
    
    if query:
        transactions = transactions.filter(Q(description__icontains=query) | Q(internal_note__icontains=query))
    if category_filter:
        transactions = transactions.filter(category=category_filter)
    if account_filter:
        transactions = transactions.filter(account_id=account_filter)
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)
    if correction_filter == 'yes':
        transactions = transactions.filter(is_correction=True)
    elif correction_filter == 'no':
        transactions = transactions.filter(is_correction=False)
    
    paginator = Paginator(transactions, 30)
    page = request.GET.get('page')
    transactions_page = paginator.get_page(page)
    
    accounts = BankAccount.objects.filter(is_active=True)
    
    return render(request, 'business/admin/transaction_list.html', {
        'transactions': transactions_page,
        'page_obj': transactions_page,
        'is_paginated': transactions_page.has_other_pages(),
        'query': query,
        'category_filter': category_filter,
        'account_filter': account_filter,
        'date_from': date_from,
        'date_to': date_to,
        'correction_filter': correction_filter,
        'accounts': accounts,
        'category_choices': Transaction.CATEGORY_CHOICES,
    })


@login_required
def admin_transaction_create(request):
    if not request.user.has_perm('business.add_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_transaction_list')
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.save()
            messages.success(request, f"✅ Transaction added: {transaction.get_category_display()} — ₦{transaction.amount:,.2f}")
            return redirect('business:admin_transaction_list')
    else:
        form = TransactionForm()
    
    return render(request, 'business/admin/transaction_form.html', {
        'form': form,
        'title': 'Add Transaction',
        'button_text': 'Add Transaction',
    })


@login_required
def admin_transaction_edit(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if not request.user.has_perm('business.change_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_transaction_list')
    
    if transaction.is_correction:
        messages.error(request, "Correction entries cannot be edited directly. Create a new correction instead.")
        return redirect('business:admin_transaction_list')
    
    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES, instance=transaction)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Transaction updated successfully.")
            return redirect('business:admin_transaction_list')
    else:
        form = TransactionForm(instance=transaction)
    
    return render(request, 'business/admin/transaction_form.html', {
        'form': form,
        'transaction': transaction,
        'title': 'Edit Transaction',
        'button_text': 'Update Transaction',
    })


@login_required
def admin_transaction_delete(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if not request.user.has_perm('business.delete_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_transaction_list')
    
    if transaction.is_correction:
        messages.error(request, "Correction entries cannot be deleted directly.")
        return redirect('business:admin_transaction_list')
    
    if request.method == 'POST':
        # Revert balance
        if transaction.is_income():
            transaction.account.current_balance -= transaction.amount
        else:
            transaction.account.current_balance += transaction.amount
        transaction.account.save()
        
        title = transaction.description[:50]
        transaction.delete()
        messages.success(request, f"🗑️ Transaction '{title}...' deleted. Balance reverted.")
        return redirect('business:admin_transaction_list')
    
    return render(request, 'business/admin/transaction_confirm_delete.html', {
        'transaction': transaction,
    })


@login_required
def admin_transaction_correct(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk)
    if not request.user.has_perm('business.add_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_transaction_list')
    
    if transaction.is_correction:
        messages.error(request, "This is already a correction entry. Correct the original transaction instead.")
        return redirect('business:admin_transaction_list')
    
    if request.method == 'POST':
        form = TransactionCorrectionForm(request.POST)
        if form.is_valid():
            new_amount = form.cleaned_data['new_amount']
            new_category = form.cleaned_data['new_category']
            new_description = form.cleaned_data.get('new_description', '')
            reason = form.cleaned_data['reason']
            
            try:
                correction = transaction.create_correction(
                    new_amount=new_amount,
                    new_category=new_category,
                    new_description=new_description or transaction.description,
                    created_by=request.user,
                    reason=reason
                )
                messages.success(
                    request,
                    f"✅ Correction created. Original corrected from ₦{transaction.amount:,.2f} to ₦{new_amount:,.2f}."
                )
                return redirect('business:admin_transaction_list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = TransactionCorrectionForm(initial={
            'new_amount': transaction.amount,
            'new_category': transaction.category,
            'new_description': transaction.description,
        })
    
    return render(request, 'business/admin/transaction_correct.html', {
        'form': form,
        'transaction': transaction,
    })


@login_required
def admin_transaction_export(request):
    if not request.user.has_perm('business.view_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_transaction_list')
    
    # Get filters from request
    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    account_filter = request.GET.get('account', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    transactions = Transaction.objects.all().order_by('-date')
    if query:
        transactions = transactions.filter(Q(description__icontains=query) | Q(internal_note__icontains=query))
    if category_filter:
        transactions = transactions.filter(category=category_filter)
    if account_filter:
        transactions = transactions.filter(account_id=account_filter)
    if date_from:
        transactions = transactions.filter(date__gte=date_from)
    if date_to:
        transactions = transactions.filter(date__lte=date_to)
    
    spec = ImportSpec()
    spec.key = 'transactions_export'
    spec.label = 'Transactions Export'
    spec.columns = [
        ColumnSpec('date', 'Date'),
        ColumnSpec('category', 'Category'),
        ColumnSpec('type', 'Type'),
        ColumnSpec('amount', 'Amount'),
        ColumnSpec('description', 'Description'),
        ColumnSpec('account', 'Account'),
        ColumnSpec('created_by', 'Created By'),
        ColumnSpec('is_correction', 'Correction'),
    ]
    
    def row_from_instance(t):
        return {
            'date': t.date.strftime('%Y-%m-%d %H:%M'),
            'category': t.get_category_display(),
            'type': 'Income' if t.is_income() else 'Expense',
            'amount': float(t.amount),
            'description': t.description,
            'account': t.account.name,
            'created_by': t.created_by.get_full_name() if t.created_by else '',
            'is_correction': 'Yes' if t.is_correction else 'No',
        }
    
    spec.export_queryset = lambda: transactions
    spec.row_from_instance = row_from_instance
    
    return build_export_xlsx(spec)


# ---------- EQUIPMENT ADMIN ----------

@login_required
def admin_equipment_list(request):
    if not request.user.has_perm('business.view_equipmentitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_equipment_list')
        
        if action == 'delete' and request.user.has_perm('business.delete_equipmentitem'):
            count = EquipmentItem.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} item(s) deleted.")
        elif action == 'activate' and request.user.has_perm('business.change_equipmentitem'):
            count = EquipmentItem.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} item(s) activated.")
        elif action == 'deactivate' and request.user.has_perm('business.change_equipmentitem'):
            count = EquipmentItem.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} item(s) deactivated.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_equipment_list')
    
    query = request.GET.get('q', '')
    condition_filter = request.GET.get('condition', '')
    status_filter = request.GET.get('status', '')
    
    items = EquipmentItem.objects.all().order_by('name')
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query) | Q(serial_number__icontains=query))
    if condition_filter:
        items = items.filter(condition=condition_filter)
    if status_filter == 'available':
        items = items.filter(available_quantity__gt=0)
    elif status_filter == 'unavailable':
        items = items.filter(available_quantity=0)
    
    paginator = Paginator(items, 20)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)
    
    return render(request, 'business/admin/equipment_list.html', {
        'items': items_page,
        'page_obj': items_page,
        'is_paginated': items_page.has_other_pages(),
        'query': query,
        'condition_filter': condition_filter,
        'status_filter': status_filter,
        'condition_choices': EquipmentItem.CONDITION_CHOICES,
    })


@login_required
def admin_equipment_create(request):
    if not request.user.has_perm('business.add_equipmentitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_list')
    
    if request.method == 'POST':
        form = EquipmentItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"✅ Equipment item '{item.name}' created.")
            return redirect('business:admin_equipment_list')
    else:
        form = EquipmentItemForm()
    
    return render(request, 'business/admin/equipment_form.html', {
        'form': form,
        'title': 'Add Equipment Item',
        'button_text': 'Create Item',
    })


@login_required
def admin_equipment_edit(request, pk):
    item = get_object_or_404(EquipmentItem, pk=pk)
    if not request.user.has_perm('business.change_equipmentitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_list')
    
    if request.method == 'POST':
        form = EquipmentItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Equipment item '{item.name}' updated.")
            return redirect('business:admin_equipment_list')
    else:
        form = EquipmentItemForm(instance=item)
    
    return render(request, 'business/admin/equipment_form.html', {
        'form': form,
        'item': item,
        'title': 'Edit Equipment Item',
        'button_text': 'Update Item',
    })


@login_required
def admin_equipment_delete(request, pk):
    item = get_object_or_404(EquipmentItem, pk=pk)
    if not request.user.has_perm('business.delete_equipmentitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_list')
    
    if request.method == 'POST':
        name = item.name
        item.delete()
        messages.success(request, f"🗑️ Equipment item '{name}' deleted.")
        return redirect('business:admin_equipment_list')
    
    return render(request, 'business/admin/equipment_confirm_delete.html', {
        'item': item,
    })


# ---------- EQUIPMENT BORROW ADMIN ----------

@login_required
def admin_equipment_borrow_list(request):
    if not request.user.has_perm('business.view_equipmentborrow'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_equipment_borrow_list')
        
        if action == 'mark_returned' and request.user.has_perm('business.change_equipmentborrow'):
            count = 0
            for borrow_id in ids:
                record = EquipmentBorrow.objects.filter(id=borrow_id, status__in=['borrowed', 'overdue']).first()
                if record and record.mark_returned():
                    count += 1
            messages.success(request, f"✅ {count} record(s) marked as returned.")
        elif action == 'delete' and request.user.has_perm('business.delete_equipmentborrow'):
            count = EquipmentBorrow.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} record(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_equipment_borrow_list')
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    item_filter = request.GET.get('item', '')
    
    records = EquipmentBorrow.objects.all().order_by('-borrowed_at')
    if query:
        records = records.filter(
            Q(borrower_name__icontains=query) |
            Q(item__name__icontains=query) |
            Q(borrower_phone__icontains=query)
        )
    if status_filter:
        records = records.filter(status=status_filter)
    if item_filter:
        records = records.filter(item_id=item_filter)
    
    # Auto-update overdue status
    for record in records:
        if record.status == 'borrowed' and record.expected_return_date < timezone.now():
            record.status = 'overdue'
            record.save()
    
    paginator = Paginator(records, 20)
    page = request.GET.get('page')
    records_page = paginator.get_page(page)
    
    items = EquipmentItem.objects.filter(is_active=True)
    
    return render(request, 'business/admin/equipment_borrow_list.html', {
        'records': records_page,
        'page_obj': records_page,
        'is_paginated': records_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
        'item_filter': item_filter,
        'items': items,
    })


@login_required
def admin_equipment_borrow_create(request):
    if not request.user.has_perm('business.add_equipmentborrow'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_borrow_list')
    
    if request.method == 'POST':
        form = EquipmentBorrowForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.borrowed_by = request.user
            try:
                record.save()
                messages.success(request, f"✅ '{record.item.name}' borrowed by {record.borrower_name}.")
                return redirect('business:admin_equipment_borrow_list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = EquipmentBorrowForm()
    
    return render(request, 'business/admin/equipment_borrow_form.html', {
        'form': form,
        'title': 'Borrow Equipment',
        'button_text': 'Borrow Item',
    })


@login_required
def admin_equipment_borrow_edit(request, pk):
    record = get_object_or_404(EquipmentBorrow, pk=pk)
    if not request.user.has_perm('business.change_equipmentborrow'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_borrow_list')
    
    if request.method == 'POST':
        form = EquipmentBorrowForm(request.POST, instance=record)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Borrow record updated.")
            return redirect('business:admin_equipment_borrow_list')
    else:
        form = EquipmentBorrowForm(instance=record)
    
    return render(request, 'business/admin/equipment_borrow_form.html', {
        'form': form,
        'record': record,
        'title': 'Edit Borrow Record',
        'button_text': 'Update Record',
    })


@login_required
def admin_equipment_borrow_delete(request, pk):
    record = get_object_or_404(EquipmentBorrow, pk=pk)
    if not request.user.has_perm('business.delete_equipmentborrow'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_borrow_list')
    
    if request.method == 'POST':
        record.delete()
        messages.success(request, "🗑️ Borrow record deleted.")
        return redirect('business:admin_equipment_borrow_list')
    
    return render(request, 'business/admin/equipment_borrow_confirm_delete.html', {
        'record': record,
    })


@login_required
def admin_equipment_borrow_mark_returned(request, pk):
    record = get_object_or_404(EquipmentBorrow, pk=pk)
    if not request.user.has_perm('business.change_equipmentborrow'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_borrow_list')
    
    if record.mark_returned():
        messages.success(request, f"✅ '{record.item.name}' returned successfully.")
    else:
        messages.info(request, "This item has already been returned.")
    
    return redirect('business:admin_equipment_borrow_list')


# ---------- SHOP ADMIN ----------

@login_required
def admin_shop_list(request):
    if not request.user.has_perm('business.view_shopitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_shop_list')
        
        if action == 'delete' and request.user.has_perm('business.delete_shopitem'):
            count = ShopItem.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} item(s) deleted.")
        elif action == 'activate' and request.user.has_perm('business.change_shopitem'):
            count = ShopItem.objects.filter(id__in=ids).update(is_active=True)
            messages.success(request, f"✅ {count} item(s) activated.")
        elif action == 'deactivate' and request.user.has_perm('business.change_shopitem'):
            count = ShopItem.objects.filter(id__in=ids).update(is_active=False)
            messages.success(request, f"✅ {count} item(s) deactivated.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_shop_list')
    
    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    status_filter = request.GET.get('status', '')
    
    items = ShopItem.objects.all().order_by('name')
    if query:
        items = items.filter(Q(name__icontains=query) | Q(description__icontains=query))
    if category_filter:
        items = items.filter(category=category_filter)
    if status_filter == 'active':
        items = items.filter(is_active=True)
    elif status_filter == 'inactive':
        items = items.filter(is_active=False)
    
    paginator = Paginator(items, 20)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)
    
    return render(request, 'business/admin/shop_list.html', {
        'items': items_page,
        'page_obj': items_page,
        'is_paginated': items_page.has_other_pages(),
        'query': query,
        'category_filter': category_filter,
        'status_filter': status_filter,
    })


@login_required
def admin_shop_create(request):
    if not request.user.has_perm('business.add_shopitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_shop_list')
    
    if request.method == 'POST':
        form = ShopItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"✅ Shop item '{item.name}' created.")
            return redirect('business:admin_shop_list')
    else:
        form = ShopItemForm()
    
    return render(request, 'business/admin/shop_form.html', {
        'form': form,
        'title': 'Add Shop Item',
        'button_text': 'Create Item',
    })


@login_required
def admin_shop_edit(request, pk):
    item = get_object_or_404(ShopItem, pk=pk)
    if not request.user.has_perm('business.change_shopitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_shop_list')
    
    if request.method == 'POST':
        form = ShopItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Shop item '{item.name}' updated.")
            return redirect('business:admin_shop_list')
    else:
        form = ShopItemForm(instance=item)
    
    return render(request, 'business/admin/shop_form.html', {
        'form': form,
        'item': item,
        'title': 'Edit Shop Item',
        'button_text': 'Update Item',
    })


@login_required
def admin_shop_delete(request, pk):
    item = get_object_or_404(ShopItem, pk=pk)
    if not request.user.has_perm('business.delete_shopitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_shop_list')
    
    if request.method == 'POST':
        name = item.name
        item.delete()
        messages.success(request, f"🗑️ Shop item '{name}' deleted.")
        return redirect('business:admin_shop_list')
    
    return render(request, 'business/admin/shop_confirm_delete.html', {
        'item': item,
    })


# ---------- SHOP ORDER ADMIN ----------

@login_required
def admin_shop_order_list(request):
    if not request.user.has_perm('business.view_shoporder'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_shop_order_list')
        
        if action == 'mark_paid' and request.user.has_perm('business.change_shoporder'):
            count = 0
            for order_id in ids:
                order = ShopOrder.objects.filter(id=order_id).first()
                if order and order.mark_paid():
                    count += 1
            messages.success(request, f"✅ {count} order(s) marked as paid.")
        elif action == 'mark_collected' and request.user.has_perm('business.change_shoporder'):
            count = 0
            for order_id in ids:
                order = ShopOrder.objects.filter(id=order_id).first()
                if order and order.mark_collected():
                    count += 1
            messages.success(request, f"✅ {count} order(s) marked as collected.")
        elif action == 'delete' and request.user.has_perm('business.delete_shoporder'):
            count = ShopOrder.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} order(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_shop_order_list')
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    item_filter = request.GET.get('item', '')
    
    orders = ShopOrder.objects.all().order_by('-created_at')
    if query:
        orders = orders.filter(
            Q(buyer_name__icontains=query) |
            Q(buyer_email__icontains=query) |
            Q(buyer_phone__icontains=query) |
            Q(collection_code__icontains=query)
        )
    if status_filter:
        orders = orders.filter(status=status_filter)
    if item_filter:
        orders = orders.filter(item_id=item_filter)
    
    paginator = Paginator(orders, 20)
    page = request.GET.get('page')
    orders_page = paginator.get_page(page)
    
    items = ShopItem.objects.filter(is_active=True)
    
    return render(request, 'business/admin/shop_order_list.html', {
        'orders': orders_page,
        'page_obj': orders_page,
        'is_paginated': orders_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
        'item_filter': item_filter,
        'items': items,
    })


@login_required
def admin_shop_order_edit(request, pk):
    order = get_object_or_404(ShopOrder, pk=pk)
    if not request.user.has_perm('business.change_shoporder'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_shop_order_list')
    
    if request.method == 'POST':
        form = ShopOrderForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Order updated.")
            return redirect('business:admin_shop_order_list')
    else:
        form = ShopOrderForm(instance=order)
    
    return render(request, 'business/admin/shop_order_form.html', {
        'form': form,
        'order': order,
        'title': 'Edit Shop Order',
        'button_text': 'Update Order',
    })


@login_required
def admin_shop_order_delete(request, pk):
    order = get_object_or_404(ShopOrder, pk=pk)
    if not request.user.has_perm('business.delete_shoporder'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_shop_order_list')
    
    if request.method == 'POST':
        order.delete()
        messages.success(request, "🗑️ Order deleted.")
        return redirect('business:admin_shop_order_list')
    
    return render(request, 'business/admin/shop_order_confirm_delete.html', {
        'order': order,
    })


# ---------- SELLABLE FORMS ADMIN ----------

@login_required
def admin_sellable_form_list(request):
    if not request.user.has_perm('business.view_sellableform'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    query = request.GET.get('q', '')
    forms = SellableForm.objects.all().order_by('title')
    if query:
        forms = forms.filter(Q(title__icontains=query) | Q(description__icontains=query))
    
    paginator = Paginator(forms, 20)
    page = request.GET.get('page')
    forms_page = paginator.get_page(page)
    
    return render(request, 'business/admin/sellable_form_list.html', {
        'forms': forms_page,
        'page_obj': forms_page,
        'is_paginated': forms_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_sellable_form_create(request):
    if not request.user.has_perm('business.add_sellableform'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_sellable_form_list')
    
    if request.method == 'POST':
        form = SellableFormForm(request.POST)
        if form.is_valid():
            sellable_form = form.save()
            messages.success(request, f"✅ Sellable form '{sellable_form.title}' created.")
            return redirect('business:admin_sellable_form_list')
    else:
        form = SellableFormForm()
    
    return render(request, 'business/admin/sellable_form_form.html', {
        'form': form,
        'title': 'Add Sellable Form',
        'button_text': 'Create Form',
    })


@login_required
def admin_sellable_form_edit(request, pk):
    sellable_form = get_object_or_404(SellableForm, pk=pk)
    if not request.user.has_perm('business.change_sellableform'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_sellable_form_list')
    
    if request.method == 'POST':
        form = SellableFormForm(request.POST, instance=sellable_form)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Sellable form '{sellable_form.title}' updated.")
            return redirect('business:admin_sellable_form_list')
    else:
        form = SellableFormForm(instance=sellable_form)
    
    return render(request, 'business/admin/sellable_form_form.html', {
        'form': form,
        'sellable_form': sellable_form,
        'title': 'Edit Sellable Form',
        'button_text': 'Update Form',
    })


@login_required
def admin_sellable_form_delete(request, pk):
    sellable_form = get_object_or_404(SellableForm, pk=pk)
    if not request.user.has_perm('business.delete_sellableform'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_sellable_form_list')
    
    if request.method == 'POST':
        title = sellable_form.title
        sellable_form.delete()
        messages.success(request, f"🗑️ Sellable form '{title}' deleted.")
        return redirect('business:admin_sellable_form_list')
    
    return render(request, 'business/admin/sellable_form_confirm_delete.html', {
        'sellable_form': sellable_form,
    })


# ---------- FORM PURCHASE ADMIN ----------

@login_required
def admin_form_purchase_list(request):
    if not request.user.has_perm('business.view_formpurchase'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_form_purchase_list')
        
        if action == 'mark_paid' and request.user.has_perm('business.change_formpurchase'):
            count = 0
            for purchase_id in ids:
                purchase = FormPurchase.objects.filter(id=purchase_id).first()
                if purchase and purchase.mark_paid():
                    count += 1
            messages.success(request, f"✅ {count} purchase(s) marked as paid.")
        elif action == 'mark_verified' and request.user.has_perm('business.change_formpurchase'):
            count = FormPurchase.objects.filter(id__in=ids).update(status='verified')
            messages.success(request, f"✅ {count} purchase(s) marked as verified.")
        elif action == 'delete' and request.user.has_perm('business.delete_formpurchase'):
            count = FormPurchase.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} purchase(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_form_purchase_list')
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    form_filter = request.GET.get('form', '')
    
    purchases = FormPurchase.objects.all().order_by('-created_at')
    if query:
        purchases = purchases.filter(
            Q(buyer_name__icontains=query) |
            Q(buyer_email__icontains=query) |
            Q(access_code__icontains=query)
        )
    if status_filter:
        purchases = purchases.filter(status=status_filter)
    if form_filter:
        purchases = purchases.filter(form_id=form_filter)
    
    paginator = Paginator(purchases, 20)
    page = request.GET.get('page')
    purchases_page = paginator.get_page(page)
    
    forms = SellableForm.objects.filter(is_active=True)
    
    return render(request, 'business/admin/form_purchase_list.html', {
        'purchases': purchases_page,
        'page_obj': purchases_page,
        'is_paginated': purchases_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
        'form_filter': form_filter,
        'forms': forms,
    })


@login_required
def admin_form_purchase_edit(request, pk):
    purchase = get_object_or_404(FormPurchase, pk=pk)
    if not request.user.has_perm('business.change_formpurchase'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_form_purchase_list')
    
    if request.method == 'POST':
        form = FormPurchaseForm(request.POST, instance=purchase)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Form purchase updated.")
            return redirect('business:admin_form_purchase_list')
    else:
        form = FormPurchaseForm(instance=purchase)
    
    return render(request, 'business/admin/form_purchase_form.html', {
        'form': form,
        'purchase': purchase,
        'title': 'Edit Form Purchase',
        'button_text': 'Update Purchase',
    })


@login_required
def admin_form_purchase_delete(request, pk):
    purchase = get_object_or_404(FormPurchase, pk=pk)
    if not request.user.has_perm('business.delete_formpurchase'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_form_purchase_list')
    
    if request.method == 'POST':
        purchase.delete()
        messages.success(request, "🗑️ Form purchase deleted.")
        return redirect('business:admin_form_purchase_list')
    
    return render(request, 'business/admin/form_purchase_confirm_delete.html', {
        'purchase': purchase,
    })


# ---------- BOOKING ADMIN ----------

@login_required
def admin_booking_listing_list(request):
    if not request.user.has_perm('business.view_bookinglisting'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    query = request.GET.get('q', '')
    category_filter = request.GET.get('category', '')
    
    listings = BookingListing.objects.all().order_by('-date_time', '-created_at')
    if query:
        listings = listings.filter(Q(title__icontains=query) | Q(description__icontains=query))
    if category_filter:
        listings = listings.filter(category=category_filter)
    
    paginator = Paginator(listings, 20)
    page = request.GET.get('page')
    listings_page = paginator.get_page(page)
    
    return render(request, 'business/admin/booking_listing_list.html', {
        'listings': listings_page,
        'page_obj': listings_page,
        'is_paginated': listings_page.has_other_pages(),
        'query': query,
        'category_filter': category_filter,
    })


@login_required
def admin_booking_listing_create(request):
    if not request.user.has_perm('business.add_bookinglisting'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_booking_listing_list')
    
    if request.method == 'POST':
        form = BookingListingForm(request.POST, request.FILES)
        if form.is_valid():
            listing = form.save()
            messages.success(request, f"✅ Booking listing '{listing.title}' created.")
            return redirect('business:admin_booking_listing_list')
    else:
        form = BookingListingForm()
    
    return render(request, 'business/admin/booking_listing_form.html', {
        'form': form,
        'title': 'Add Booking Listing',
        'button_text': 'Create Listing',
    })


@login_required
def admin_booking_listing_edit(request, pk):
    listing = get_object_or_404(BookingListing, pk=pk)
    if not request.user.has_perm('business.change_bookinglisting'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_booking_listing_list')
    
    if request.method == 'POST':
        form = BookingListingForm(request.POST, request.FILES, instance=listing)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Booking listing '{listing.title}' updated.")
            return redirect('business:admin_booking_listing_list')
    else:
        form = BookingListingForm(instance=listing)
    
    return render(request, 'business/admin/booking_listing_form.html', {
        'form': form,
        'listing': listing,
        'title': 'Edit Booking Listing',
        'button_text': 'Update Listing',
    })


@login_required
def admin_booking_listing_delete(request, pk):
    listing = get_object_or_404(BookingListing, pk=pk)
    if not request.user.has_perm('business.delete_bookinglisting'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_booking_listing_list')
    
    if request.method == 'POST':
        title = listing.title
        listing.delete()
        messages.success(request, f"🗑️ Booking listing '{title}' deleted.")
        return redirect('business:admin_booking_listing_list')
    
    return render(request, 'business/admin/booking_listing_confirm_delete.html', {
        'listing': listing,
    })


# ---------- BOOKING ADMIN ----------

@login_required
def admin_booking_list(request):
    if not request.user.has_perm('business.view_booking'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_booking_list')
        
        if action == 'mark_paid' and request.user.has_perm('business.change_booking'):
            count = 0
            for booking_id in ids:
                booking = Booking.objects.filter(id=booking_id).first()
                if booking and booking.mark_paid():
                    count += 1
            messages.success(request, f"✅ {count} booking(s) marked as paid.")
        elif action == 'check_in' and request.user.has_perm('business.change_booking'):
            count = 0
            for booking_id in ids:
                booking = Booking.objects.filter(id=booking_id).first()
                if booking and booking.check_in():
                    count += 1
            messages.success(request, f"✅ {count} booking(s) checked in.")
        elif action == 'delete' and request.user.has_perm('business.delete_booking'):
            count = Booking.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} booking(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_booking_list')
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    listing_filter = request.GET.get('listing', '')
    
    bookings = Booking.objects.all().order_by('-created_at')
    if query:
        bookings = bookings.filter(
            Q(booker_name__icontains=query) |
            Q(booker_email__icontains=query) |
            Q(booker_phone__icontains=query) |
            Q(qr_token__icontains=query)
        )
    if status_filter:
        bookings = bookings.filter(status=status_filter)
    if listing_filter:
        bookings = bookings.filter(listing_id=listing_filter)
    
    paginator = Paginator(bookings, 20)
    page = request.GET.get('page')
    bookings_page = paginator.get_page(page)
    
    listings = BookingListing.objects.filter(is_active=True)
    
    return render(request, 'business/admin/booking_list.html', {
        'bookings': bookings_page,
        'page_obj': bookings_page,
        'is_paginated': bookings_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
        'listing_filter': listing_filter,
        'listings': listings,
    })


@login_required
def admin_booking_edit(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not request.user.has_perm('business.change_booking'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_booking_list')
    
    if request.method == 'POST':
        form = BookingAdminForm(request.POST, instance=booking)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Booking updated.")
            return redirect('business:admin_booking_list')
    else:
        form = BookingAdminForm(instance=booking)
    
    return render(request, 'business/admin/booking_form.html', {
        'form': form,
        'booking': booking,
        'title': 'Edit Booking',
        'button_text': 'Update Booking',
    })


@login_required
def admin_booking_delete(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not request.user.has_perm('business.delete_booking'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_booking_list')
    
    if request.method == 'POST':
        booking.delete()
        messages.success(request, "🗑️ Booking deleted.")
        return redirect('business:admin_booking_list')
    
    return render(request, 'business/admin/booking_confirm_delete.html', {
        'booking': booking,
    })


@login_required
@require_POST
def admin_booking_check_in(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    if not request.user.has_perm('business.change_booking'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_booking_list')

    if booking.check_in():
        messages.success(request, f"✅ Booking for {booking.booker_name} checked in.")
    else:
        messages.info(request, "This booking has already been checked in.")

    return redirect('business:admin_booking_list')


# ---------- FREE CLAIM ADMIN ----------

@login_required
def admin_free_claim_list(request):
    if not request.user.has_perm('business.view_freeclaim'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')
    
    # Bulk actions
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        ids = request.POST.getlist('selected_ids')
        if not ids:
            messages.warning(request, "No items selected.")
            return redirect('business:admin_free_claim_list')
        
        if action == 'mark_claimed' and request.user.has_perm('business.change_freeclaim'):
            count = 0
            for claim_id in ids:
                claim = FreeClaim.objects.filter(id=claim_id).first()
                if claim and claim.mark_claimed():
                    count += 1
            messages.success(request, f"✅ {count} claim(s) marked as claimed.")
        elif action == 'delete' and request.user.has_perm('business.delete_freeclaim'):
            count = FreeClaim.objects.filter(id__in=ids).delete()[0]
            messages.success(request, f"🗑️ {count} claim(s) deleted.")
        else:
            messages.error(request, "Invalid action or permission denied.")
        return redirect('business:admin_free_claim_list')
    
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    item_filter = request.GET.get('item', '')
    
    claims = FreeClaim.objects.all().order_by('-created_at')
    if query:
        claims = claims.filter(
            Q(claimant_name__icontains=query) |
            Q(claimant_email__icontains=query) |
            Q(claim_code__icontains=query)
        )
    if status_filter:
        claims = claims.filter(status=status_filter)
    if item_filter:
        claims = claims.filter(item_id=item_filter)
    
    paginator = Paginator(claims, 20)
    page = request.GET.get('page')
    claims_page = paginator.get_page(page)
    
    items = ShopItem.objects.filter(is_free=True, is_active=True)
    
    return render(request, 'business/admin/free_claim_list.html', {
        'claims': claims_page,
        'page_obj': claims_page,
        'is_paginated': claims_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
        'item_filter': item_filter,
        'items': items,
    })


@login_required
def admin_free_claim_edit(request, pk):
    claim = get_object_or_404(FreeClaim, pk=pk)
    if not request.user.has_perm('business.change_freeclaim'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_free_claim_list')
    
    if request.method == 'POST':
        form = FreeClaimAdminForm(request.POST, instance=claim)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Claim updated.")
            return redirect('business:admin_free_claim_list')
    else:
        form = FreeClaimAdminForm(instance=claim)
    
    return render(request, 'business/admin/free_claim_form.html', {
        'form': form,
        'claim': claim,
        'title': 'Edit Free Claim',
        'button_text': 'Update Claim',
    })


@login_required
def admin_free_claim_delete(request, pk):
    claim = get_object_or_404(FreeClaim, pk=pk)
    if not request.user.has_perm('business.delete_freeclaim'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_free_claim_list')
    
    if request.method == 'POST':
        claim.delete()
        messages.success(request, "🗑️ Claim deleted.")
        return redirect('business:admin_free_claim_list')
    
    return render(request, 'business/admin/free_claim_confirm_delete.html', {
        'claim': claim,
    })


@login_required
def admin_free_claim_mark_claimed(request, pk):
    claim = get_object_or_404(FreeClaim, pk=pk)
    if not request.user.has_perm('business.change_freeclaim'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_free_claim_list')
    
    if claim.mark_claimed():
        messages.success(request, f"✅ Claim for {claim.claimant_name} marked as claimed.")
    else:
        messages.info(request, "This claim has already been marked as claimed.")
    
    return redirect('business:admin_free_claim_list')


# ---------- EXPORT VIEWS ----------

@login_required
def admin_equipment_export(request):
    if not request.user.has_perm('business.view_equipmentitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_equipment_list')
    
    queryset = EquipmentItem.objects.all()
    spec = ImportSpec()
    spec.key = 'equipment_export'
    spec.label = 'Equipment Export'
    spec.columns = [
        ColumnSpec('name', 'Name'),
        ColumnSpec('condition', 'Condition'),
        ColumnSpec('quantity', 'Quantity'),
        ColumnSpec('available_quantity', 'Available'),
        ColumnSpec('location', 'Location'),
        ColumnSpec('is_active', 'Active'),
    ]
    
    def row(instance):
        return {
            'name': instance.name,
            'condition': instance.get_condition_display(),
            'quantity': instance.quantity,
            'available_quantity': instance.available_quantity,
            'location': instance.location,
            'is_active': 'Yes' if instance.is_active else 'No',
        }
    
    spec.export_queryset = lambda: queryset
    spec.row_from_instance = row
    return build_export_xlsx(spec)


@login_required
def admin_shop_export(request):
    if not request.user.has_perm('business.view_shopitem'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_shop_list')
    
    queryset = ShopItem.objects.all()
    spec = ImportSpec()
    spec.key = 'shop_export'
    spec.label = 'Shop Export'
    spec.columns = [
        ColumnSpec('name', 'Name'),
        ColumnSpec('category', 'Category'),
        ColumnSpec('price', 'Price'),
        ColumnSpec('is_free', 'Free'),
        ColumnSpec('quantity_in_stock', 'Stock'),
        ColumnSpec('available_quantity', 'Available'),
        ColumnSpec('is_active', 'Active'),
    ]
    
    def row(instance):
        return {
            'name': instance.name,
            'category': instance.get_category_display(),
            'price': float(instance.price),
            'is_free': 'Yes' if instance.is_free else 'No',
            'quantity_in_stock': instance.quantity_in_stock,
            'available_quantity': instance.available_quantity,
            'is_active': 'Yes' if instance.is_active else 'No',
        }
    
    spec.export_queryset = lambda: queryset
    spec.row_from_instance = row
    return build_export_xlsx(spec)


# ============================================================
# 4. DASHBOARD (Business EXCO)
# ============================================================

@login_required
def dashboard(request):
    """Business EXCO dashboard with stats and recent activity."""
    # Stats
    total_items = EquipmentItem.objects.filter(is_active=True).count()
    borrowed_items = EquipmentBorrow.objects.filter(status__in=['borrowed', 'overdue']).count()
    overdue_items = EquipmentBorrow.objects.filter(
        status='borrowed',
        expected_return_date__lt=timezone.now()
    ).count()
    available_venues = CollectionCenter.objects.filter(is_active=True).count()

    # Financial stats
    total_income = Transaction.objects.filter(
        category__in=[c[0] for c in Transaction.INCOME_CATEGORIES]
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expenses = Transaction.objects.filter(
        category__in=[c[0] for c in Transaction.EXPENSE_CATEGORIES]
    ).aggregate(total=Sum('amount'))['total'] or 0

    net_balance = total_income - total_expenses

    # Pending counts
    pending_shop_orders = ShopOrder.objects.filter(status='pending').count()
    pending_free_claims = FreeClaim.objects.filter(status='pending').count()
    pending_bookings = Booking.objects.filter(status='pending').count()

    # Recent activity
    recent_transactions = Transaction.objects.all().order_by('-date')[:5]
    recent_borrows = EquipmentBorrow.objects.all().order_by('-borrowed_at')[:5]
    recent_orders = ShopOrder.objects.all().order_by('-created_at')[:5]

    # Bank account balances
    bank_accounts = BankAccount.objects.filter(is_active=True)

    # Revenue stats (last 30 days)
    since = timezone.now() - timedelta(days=30)
    revenue_qs = Transaction.objects.filter(
        category__in=['shop_sales', 'booking_revenue', 'form_revenue'],
        date__gte=since
    )

    revenue_total = revenue_qs.aggregate(total=Sum('amount'))['total'] or 0
    revenue_shop = revenue_qs.filter(category='shop_sales').aggregate(total=Sum('amount'))['total'] or 0
    revenue_bookings = revenue_qs.filter(category='booking_revenue').aggregate(total=Sum('amount'))['total'] or 0
    revenue_forms = revenue_qs.filter(category='form_revenue').aggregate(total=Sum('amount'))['total'] or 0

    # All-time revenue
    all_time_revenue = Transaction.objects.filter(
        category__in=['shop_sales', 'booking_revenue', 'form_revenue']
    ).aggregate(total=Sum('amount'))['total'] or 0

    context = {
        'total_items': total_items,
        'borrowed_items': borrowed_items,
        'overdue_items': overdue_items,
        'available_venues': available_venues,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_balance': net_balance,
        'pending_shop_orders': pending_shop_orders,
        'pending_free_claims': pending_free_claims,
        'pending_bookings': pending_bookings,
        'recent_transactions': recent_transactions,
        'recent_borrows': recent_borrows,
        'recent_orders': recent_orders,
        'bank_accounts': bank_accounts,
        'now': timezone.now(),
        'revenue_total': revenue_total,
        'revenue_shop': revenue_shop,
        'revenue_bookings': revenue_bookings,
        'revenue_forms': revenue_forms,
        'all_time_revenue': all_time_revenue,
    }

    return render(request, 'business/admin/dashboard.html', context)


# ============================================================
# 1. PUBLIC LANDING PAGE (Business Hub)
# ============================================================

def public_business_landing(request):
    """
    Public Business landing page — hub linking to shop, free claims,
    bookings, sellable forms, donations, and guest lookup.
    """
    # Pull a few featured items to showcase (optional)
    featured_shop_items = ShopItem.objects.filter(
        is_active=True, is_public=True, available_quantity__gt=0
    ).order_by('-created_at')[:3]

    featured_free_items = ShopItem.objects.filter(
        is_active=True, is_public=True, is_free=True, available_quantity__gt=0
    ).order_by('-created_at')[:2]

    upcoming_bookings = BookingListing.objects.filter(
        is_active=True, is_public=True, quantity_available__gt=0
    ).order_by('-date_time', '-created_at')[:2]

    return render(request, 'business/public/landing.html', {
        'featured_shop_items': featured_shop_items,
        'featured_free_items': featured_free_items,
        'upcoming_bookings': upcoming_bookings,
    })

@require_POST
def public_cancel_item(request, item_type, item_id):
    """
    Guest cancels their own pending order/booking/claim/purchase.
    Redirects back to the previous lookup results so the guest
    doesn't have to re-enter their contact info.
    """
    from urllib.parse import urlencode
    from django.urls import reverse

    model_map = {
        'shop_order':    ShopOrder,
        'booking':       Booking,
        'free_claim':    FreeClaim,
        'form_purchase': FormPurchase,
    }
    model = model_map.get(item_type)

    # Build the redirect URL back to the lookup page with the same params
    return_type = request.POST.get('return_type', '')
    return_code = request.POST.get('return_code', '').strip()
    return_email = request.POST.get('return_email', '').strip()
    return_phone = request.POST.get('return_phone', '').strip()

    params = {}
    if return_type == 'code' and return_code:
        params = {'lookup_type': 'code', 'code': return_code}
    elif return_type == 'contact' and (return_email or return_phone):
        params = {
            'lookup_type': 'contact',
            'email': return_email,
            'phone': return_phone,
        }

    base_url = reverse('business:guest_lookup')
    redirect_url = base_url + ('?' + urlencode(params) if params else '')

    if not model:
        messages.error(request, "Invalid item type.")
        return redirect(redirect_url)

    obj = get_object_or_404(model, pk=item_id)
    if obj.status != 'pending':
        messages.error(request, "Only pending items can be cancelled.")
        return redirect(redirect_url)

    obj.status = 'cancelled'
    obj.save(update_fields=['status'])
    messages.success(request, "✅ Your item has been cancelled successfully.")
    return redirect(redirect_url)


@login_required
@require_POST
def admin_form_purchase_mark_paid(request, pk):
    purchase = get_object_or_404(FormPurchase, pk=pk)
    if not request.user.has_perm('business.change_formpurchase'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_form_purchase_list')

    if purchase.status == 'paid':
        messages.info(request, "This purchase is already marked as paid.")
    else:
        purchase.mark_paid()
        messages.success(request, f"✅ Purchase {purchase.access_code} marked as paid.")

    return redirect('business:admin_form_purchase_list')


@login_required
@require_POST
def admin_form_purchase_mark_verified(request, pk):
    purchase = get_object_or_404(FormPurchase, pk=pk)
    if not request.user.has_perm('business.change_formpurchase'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_form_purchase_list')

    if purchase.status != 'paid':
        messages.error(request, "Only paid purchases can be verified.")
    else:
        purchase.status = 'verified'
        purchase.save(update_fields=['status'])
        messages.success(request, f"✅ Purchase {purchase.access_code} verified.")

    return redirect('business:admin_form_purchase_list')


def _generate_revenue_insights(totals, shop_total, booking_total, form_total, per_account, all_sources):
    """
    Turn raw revenue numbers into plain-English insights.
    (Designed to be swapped later with a real Gemini call.)
    """
    insights = []

    # --- Cast everything to float up front (Django's Sum returns Decimal) ---
    totals = float(totals or 0)
    shop_total = float(shop_total or 0)
    booking_total = float(booking_total or 0)
    form_total = float(form_total or 0)

    if totals == 0:
        return [{
            'icon': '📊',
            'title': 'No revenue yet',
            'body': 'As payments start coming in, insights about your top products, accounts, and trends will appear here.',
            'tone': 'neutral',
        }]

    # 1. Top category
    categories = [
        ('Shop', shop_total, '🛒'),
        ('Bookings', booking_total, '🎟️'),
        ('Forms', form_total, '📄'),
    ]
    categories.sort(key=lambda x: x[1], reverse=True)
    top = categories[0]
    if top[1] > 0:
        pct = (top[1] / totals) * 100
        insights.append({
            'icon': top[2],
            'title': f'{top[0]} leads your revenue',
            'body': f'{top[0]} accounts for ₦{top[1]:,.2f} — about {pct:.0f}% of total revenue.',
            'tone': 'positive',
        })

    # 2. Top account
    if per_account:
        acct = per_account[0]
        acct_total = float(acct['total'] or 0)
        insights.append({
            'icon': '🏦',
            'title': f'{acct["account__name"]} is your busiest account',
            'body': f'₦{acct_total:,.2f} across {acct["count"]} transaction(s). Make sure this account is reconciled.',
            'tone': 'info',
        })

    # 3. Best single performer
    if all_sources:
        all_sources_sorted = sorted(all_sources, key=lambda x: float(x['total'] or 0), reverse=True)
        best = all_sources_sorted[0]
        best_total = float(best['total'] or 0)
        insights.append({
            'icon': '⭐',
            'title': 'Best performer',
            'body': f'"{best["description"][:65]}" earned ₦{best_total:,.2f} — consider featuring it more.',
            'tone': 'positive',
        })

    # 4. Category gap
    if shop_total > 0 and booking_total < (shop_total * 0.4):
        insights.append({
            'icon': '💡',
            'title': 'Bookings could be stronger',
            'body': f'Bookings only made ₦{booking_total:,.2f} vs ₦{shop_total:,.2f} in shop sales. Promote upcoming events on social channels.',
            'tone': 'warning',
        })

    # 5. Form revenue observation
    if form_total > 0 and form_total < (totals * 0.15):
        pct = (form_total / totals) * 100
        insights.append({
            'icon': '📝',
            'title': 'Forms are a small slice',
            'body': f'Form purchases contributed only {pct:.0f}% of revenue. Consider bundling forms with events or advertising them more.',
            'tone': 'info',
        })

    return insights



@login_required
def admin_revenue_report(request):
    """
    Detailed revenue report:
    - Totals by source (shop, bookings, forms)
    - Per-bank-account breakdown
    - Top selling sources
    - Smart insights (mock AI)
    - Export to Excel
    """
    if not request.user.has_perm('business.view_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    tx_qs = Transaction.objects.filter(
        category__in=['shop_sales', 'booking_revenue', 'form_revenue']
    )
    if date_from:
        tx_qs = tx_qs.filter(date__gte=date_from)
    if date_to:
        tx_qs = tx_qs.filter(date__lte=date_to)

    # Totals
    totals = tx_qs.aggregate(total=Sum('amount'))['total'] or 0
    shop_total = tx_qs.filter(category='shop_sales').aggregate(total=Sum('amount'))['total'] or 0
    booking_total = tx_qs.filter(category='booking_revenue').aggregate(total=Sum('amount'))['total'] or 0
    form_total = tx_qs.filter(category='form_revenue').aggregate(total=Sum('amount'))['total'] or 0

    # Per-account breakdown
    per_account = (
        tx_qs.values(
            'account__id', 'account__name',
            'account__bank_name', 'account__account_number'
        )
        .annotate(
            shop=Sum('amount', filter=Q(category='shop_sales')),
            bookings=Sum('amount', filter=Q(category='booking_revenue')),
            forms=Sum('amount', filter=Q(category='form_revenue')),
            total=Sum('amount'),
            count=Count('id'),
        )
        .order_by('-total')
    )

    # Top sources
    booking_sales = (
        tx_qs.filter(category='booking_revenue')
        .values('description')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')[:10]
    )
    shop_sales = (
        tx_qs.filter(category='shop_sales')
        .values('description')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')[:10]
    )
    form_sales = (
        tx_qs.filter(category='form_revenue')
        .values('description')
        .annotate(count=Count('id'), total=Sum('amount'))
        .order_by('-total')[:10]
    )

    # Recent entries
    recent = tx_qs.select_related('account').order_by('-date')[:20]

    # Build insights
    all_sources = list(shop_sales) + list(booking_sales) + list(form_sales)
    insights = _generate_revenue_insights(
        totals=totals,
        shop_total=shop_total,
        booking_total=booking_total,
        form_total=form_total,
        per_account=list(per_account),
        all_sources=all_sources,
    )

    return render(request, 'business/admin/revenue_report.html', {
        'totals': totals,
        'shop_total': shop_total,
        'booking_total': booking_total,
        'form_total': form_total,
        'per_account': per_account,
        'booking_sales': booking_sales,
        'shop_sales': shop_sales,
        'form_sales': form_sales,
        'recent': recent,
        'insights': insights,
        'date_from': date_from,
        'date_to': date_to,
    })



@login_required
def admin_revenue_export(request):
    if not request.user.has_perm('business.view_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:admin_revenue_report')

    from core.importers.spec import ColumnSpec, ImportSpec
    from core.importers.excel_io import build_export_xlsx

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    tx_qs = Transaction.objects.filter(
        category__in=['shop_sales', 'booking_revenue', 'form_revenue']
    ).select_related('account').order_by('-date')

    if date_from:
        tx_qs = tx_qs.filter(date__gte=date_from)
    if date_to:
        tx_qs = tx_qs.filter(date__lte=date_to)

    spec = ImportSpec()
    spec.key = 'revenue_export'
    spec.label = 'Revenue Export'
    spec.columns = [
        ColumnSpec('date', 'Date'),
        ColumnSpec('category', 'Category'),
        ColumnSpec('description', 'Description'),
        ColumnSpec('amount', 'Amount (₦)'),
        ColumnSpec('account', 'Account'),
        ColumnSpec('recorded_by', 'Recorded By'),
    ]

    def row(t):
        return {
            'date': t.date.strftime('%Y-%m-%d %H:%M'),
            'category': t.get_category_display(),
            'description': t.description,
            'amount': float(t.amount),
            'account': t.account.name if t.account else '',
            'recorded_by': t.created_by.get_full_name() if t.created_by else '',
        }

    spec.export_queryset = lambda: tx_qs
    spec.row_from_instance = row

    return build_export_xlsx(spec)


# ============================================================
# EXPENSE SYSTEM
# ============================================================

@login_required
def admin_expense_report(request):
    """
    Expense report: all expenses grouped by category and account.
    """
    if not request.user.has_perm('business.view_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')

    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')

    expense_categories = [c[0] for c in Transaction.EXPENSE_CATEGORIES]
    qs = Transaction.objects.filter(category__in=expense_categories).select_related('account')
    if date_from:
        qs = qs.filter(date__gte=date_from)
    if date_to:
        qs = qs.filter(date__lte=date_to)

    total = qs.aggregate(total=Sum('amount'))['total'] or 0

    # Per category
    per_category = (
        qs.values('category')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )
    # Translate category codes to human labels
    category_labels = dict(Transaction.CATEGORY_CHOICES)
    for c in per_category:
        c['label'] = category_labels.get(c['category'], c['category'])

    # Per account
    per_account = (
        qs.values('account__name', 'account__bank_name')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-total')
    )

    recent = qs.order_by('-date')[:30]

    return render(request, 'business/admin/expense_report.html', {
        'total': total,
        'per_category': per_category,
        'per_account': per_account,
        'recent': recent,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
def admin_expense_create(request):
    """
    Dedicated form to record an expense.
    Locks the category field to expense-only choices.
    """
    if not request.user.has_perm('business.add_transaction'):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')

    if request.method == 'POST':
        form = TransactionForm(request.POST, request.FILES, expense_only=True)
        if form.is_valid():
            transaction = form.save(commit=False)
            transaction.created_by = request.user
            transaction.save()
            messages.success(
                request,
                f"✅ Expense recorded: {transaction.get_category_display()} — "
                f"₦{transaction.amount:,.2f} from {transaction.account.name}."
            )
            return redirect('business:admin_expense_report')
    else:
        form = TransactionForm(expense_only=True)

    return render(request, 'business/admin/expense_form.html', {
        'form': form,
        'title': 'Record Expense',
        'button_text': 'Record Expense',
    })


# ============================================================
# QR CODE SYSTEM (unified — bookings, shop orders, claims, forms)
# ============================================================

def _get_collectible(code):
    """
    Find any collectible item matching this code across all four models.
    Returns (kind, obj) or (None, None).
    """
    code = (code or '').strip()
    if not code:
        return None, None

    # Booking (by qr_token)
    b = Booking.objects.filter(qr_token=code).select_related('listing').first()
    if b:
        return 'booking', b

    # ShopOrder (by collection_code)
    o = ShopOrder.objects.filter(collection_code=code).select_related('item', 'collection_center').first()
    if o:
        return 'shop_order', o

    # FreeClaim (by claim_code)
    c = FreeClaim.objects.filter(claim_code=code).select_related('item', 'collection_center').first()
    if c:
        return 'free_claim', c

    # FormPurchase (by access_code)
    p = FormPurchase.objects.filter(access_code=code).select_related('form').first()
    if p:
        return 'form_purchase', p

    return None, None


def _normalize_collectible(kind, obj):
    """Return a flat dict with unified fields for the QR display template."""
    if kind == 'booking':
        return {
            'kind': 'booking',
            'icon': '🎟️',
            'type_label': 'Booking',
            'title': obj.listing.title,
            'attendee': obj.booker_name,
            'email': obj.booker_email,
            'phone': obj.booker_phone,
            'quantity': obj.quantity,
            'amount': obj.total_amount,
            'status': obj.status,
            'status_display': obj.get_status_display(),
            'code': obj.qr_token,
            'code_short': obj.qr_token[:12] + '…',
            'created_at': obj.created_at,
            'when_line': obj.listing.date_time.strftime('%a, %b %d, %Y · %I:%M %p') if obj.listing.date_time else '',
            'where_line': obj.listing.venue or '',
            'collected_at': obj.checked_in_at,
            'collected_label': 'Checked in',
            'is_ready': obj.status == 'paid',
            'is_collected': obj.status == 'checked_in',
            'is_pending': obj.status == 'pending',
            'is_cancelled': obj.status == 'cancelled',
        }

    if kind == 'shop_order':
        return {
            'kind': 'shop_order',
            'icon': '🛍️',
            'type_label': 'Shop Order',
            'title': obj.item.name,
            'attendee': obj.buyer_name,
            'email': obj.buyer_email,
            'phone': obj.buyer_phone,
            'quantity': obj.quantity,
            'amount': obj.total_amount,
            'status': obj.status,
            'status_display': obj.get_status_display(),
            'code': obj.collection_code,
            'code_short': obj.collection_code,
            'created_at': obj.created_at,
            'when_line': '',
            'where_line': obj.collection_center.name if obj.collection_center else '',
            'collected_at': obj.collected_at,
            'collected_label': 'Collected',
            'is_ready': obj.status == 'paid',
            'is_collected': obj.status == 'collected',
            'is_pending': obj.status == 'pending',
            'is_cancelled': obj.status == 'cancelled',
        }

    if kind == 'free_claim':
        return {
            'kind': 'free_claim',
            'icon': '🎁',
            'type_label': 'Free Claim',
            'title': obj.item.name,
            'attendee': obj.claimant_name,
            'email': obj.claimant_email,
            'phone': obj.claimant_phone,
            'quantity': 1,
            'amount': 0,
            'status': obj.status,
            'status_display': obj.get_status_display(),
            'code': obj.claim_code,
            'code_short': obj.claim_code,
            'created_at': obj.created_at,
            'when_line': '',
            'where_line': obj.collection_center.name if obj.collection_center else '',
            'collected_at': obj.claimed_at,
            'collected_label': 'Claimed',
            # Free claims are "ready" as soon as they're submitted
            'is_ready': obj.status == 'pending',
            'is_collected': obj.status == 'claimed',
            'is_pending': False,
            'is_cancelled': obj.status == 'expired',
        }

    if kind == 'form_purchase':
        return {
            'kind': 'form_purchase',
            'icon': '📄',
            'type_label': 'Form Purchase',
            'title': obj.form.title,
            'attendee': obj.buyer_name,
            'email': obj.buyer_email,
            'phone': obj.buyer_phone,
            'quantity': 1,
            'amount': obj.amount_paid,
            'status': obj.status,
            'status_display': obj.get_status_display(),
            'code': obj.access_code,
            'code_short': obj.access_code,
            'created_at': obj.created_at,
            'when_line': '',
            'where_line': '',
            'collected_at': None,
            'collected_label': 'Verified',
            'is_ready': obj.status == 'paid',
            'is_collected': obj.status == 'verified',
            'is_pending': obj.status == 'pending',
            'is_cancelled': obj.status == 'cancelled',
        }

    return None


# ---------- PUBLIC QR DISPLAY ----------

def qr_display(request, code):
    """
    Public QR display for any collectible item.
    The code itself is the secret — same security model as guest lookup.
    """
    kind, obj = _get_collectible(code)
    if not obj:
        raise Http404("No record found for this code.")

    ctx = _normalize_collectible(kind, obj)
    return render(request, 'business/public/qr_display.html', ctx)


# ---------- ADMIN SCANNER ----------

@login_required
def admin_qr_scanner(request):
    """Camera-based QR scanner for staff."""
    if not (request.user.has_perm('business.change_booking')
            or request.user.has_perm('business.view_booking')
            or request.user.is_superuser):
        messages.error(request, "Permission denied.")
        return redirect('business:dashboard')

    recently_checked_in = (
        Booking.objects
        .filter(status='checked_in', checked_in_at__isnull=False)
        .select_related('listing')
        .order_by('-checked_in_at')[:5]
    )

    return render(request, 'business/admin/qr_scanner.html', {
        'recently_checked_in': recently_checked_in,
        'total_checked_in_today': Booking.objects.filter(
            status='checked_in',
            checked_in_at__date=timezone.now().date(),
        ).count(),
    })


@login_required
def admin_qr_lookup(request, code):
    """JSON lookup: given a scanned code, return unified item info."""
    if not (request.user.has_perm('business.view_booking')
            or request.user.has_perm('business.change_booking')
            or request.user.is_superuser):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    kind, obj = _get_collectible(code)
    if not obj:
        return JsonResponse({
            'ok': False,
            'error': 'No NAMETS record found for this code.',
        }, status=404)

    ctx = _normalize_collectible(kind, obj)

    return JsonResponse({
        'ok': True,
        'item': {
            'pk': obj.pk,
            'kind': ctx['kind'],
            'icon': ctx['icon'],
            'type_label': ctx['type_label'],
            'title': ctx['title'],
            'attendee': ctx['attendee'],
            'email': ctx['email'],
            'phone': ctx['phone'],
            'quantity': ctx['quantity'],
            'amount': str(ctx['amount']),
            'status': ctx['status'],
            'status_display': ctx['status_display'],
            'code': ctx['code'],
            'code_short': ctx['code_short'],
            'when_line': ctx['when_line'],
            'where_line': ctx['where_line'],
            'collected_label': ctx['collected_label'],
            'collected_at': ctx['collected_at'].isoformat() if ctx['collected_at'] else None,
            'is_ready': ctx['is_ready'],
            'is_collected': ctx['is_collected'],
            'is_pending': ctx['is_pending'],
            'is_cancelled': ctx['is_cancelled'],
        }
    })


@login_required
@require_POST
def admin_qr_check_in(request, kind, pk):
    """
    JSON check-in: mark a scanned item as collected/claimed/verified/checked-in.
    kind = 'booking' | 'shop_order' | 'free_claim' | 'form_purchase'
    """

    if not (request.user.has_perm('business.change_booking')
            or request.user.is_superuser):
        return JsonResponse({'ok': False, 'error': 'Permission denied'}, status=403)

    # ---------- BOOKING ----------
    if kind == 'booking':
        obj = get_object_or_404(Booking.objects.select_related('listing'), pk=pk)
        if obj.status == 'checked_in':
            return JsonResponse({'ok': False, 'error': 'Already checked in.',
                                 'kind': 'booking'}, status=400)
        if obj.status == 'pending':
            return JsonResponse({'ok': False, 'error': 'Not paid yet — cannot check in.',
                                 'kind': 'booking'}, status=400)
        if obj.status == 'cancelled':
            return JsonResponse({'ok': False, 'error': 'Cancelled booking.',
                                 'kind': 'booking'}, status=400)
        obj.check_in()
        return JsonResponse({
            'ok': True,
            'kind': 'booking',
            'message': f'Checked in {obj.booker_name} for "{obj.listing.title}".',
        })

    # ---------- SHOP ORDER ----------
    if kind == 'shop_order':
        obj = get_object_or_404(ShopOrder.objects.select_related('item'), pk=pk)
        if obj.status == 'collected':
            return JsonResponse({'ok': False, 'error': 'Already collected.',
                                 'kind': 'shop_order'}, status=400)
        if obj.status == 'pending':
            return JsonResponse({'ok': False, 'error': 'Not paid yet — cannot collect.',
                                 'kind': 'shop_order'}, status=400)
        if obj.status == 'cancelled':
            return JsonResponse({'ok': False, 'error': 'Cancelled order.',
                                 'kind': 'shop_order'}, status=400)
        obj.mark_collected()
        return JsonResponse({
            'ok': True,
            'kind': 'shop_order',
            'message': f'Collected: {obj.item.name} × {obj.quantity} for {obj.buyer_name}.',
        })

    # ---------- FREE CLAIM ----------
    if kind == 'free_claim':
        obj = get_object_or_404(FreeClaim.objects.select_related('item'), pk=pk)
        if obj.status == 'claimed':
            return JsonResponse({'ok': False, 'error': 'Already claimed.',
                                 'kind': 'free_claim'}, status=400)
        if obj.status == 'expired':
            return JsonResponse({'ok': False, 'error': 'This claim has expired.',
                                 'kind': 'free_claim'}, status=400)
        obj.mark_claimed()
        return JsonResponse({
            'ok': True,
            'kind': 'free_claim',
            'message': f'Claimed: {obj.item.name} by {obj.claimant_name}.',
        })

    # ---------- FORM PURCHASE ----------
    if kind == 'form_purchase':
        obj = get_object_or_404(FormPurchase.objects.select_related('form'), pk=pk)
        if obj.status == 'verified':
            return JsonResponse({'ok': False, 'error': 'Already verified.',
                                 'kind': 'form_purchase'}, status=400)
        if obj.status == 'pending':
            return JsonResponse({'ok': False, 'error': 'Not paid yet — cannot verify.',
                                 'kind': 'form_purchase'}, status=400)
        if obj.status == 'cancelled':
            return JsonResponse({'ok': False, 'error': 'Cancelled purchase.',
                                 'kind': 'form_purchase'}, status=400)
        obj.status = 'verified'
        obj.save(update_fields=['status'])
        return JsonResponse({
            'ok': True,
            'kind': 'form_purchase',
            'message': f'Verified: {obj.form.title} for {obj.buyer_name}.',
        })

    return JsonResponse({'ok': False, 'error': 'Unknown item type.'}, status=400)



