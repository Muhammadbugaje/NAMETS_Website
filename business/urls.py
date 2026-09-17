# business/urls.py

from django.urls import path
from . import views

app_name = 'business'

urlpatterns = [
    # ============================================================
    # 1. PUBLIC VIEWS (Guest-Facing)
    # ============================================================
    
    # --- Shop ---
    path('shop/', views.shop_catalog, name='shop_catalog'),
    path('shop/<int:item_id>/', views.shop_item_detail, name='shop_item_detail'),
    path('shop/checkout/<int:order_id>/', views.shop_checkout, name='shop_checkout'),
    
    # --- Free Claims ---
    path('free-claims/', views.free_claims_catalog, name='free_claims_catalog'),
    path('free-claims/<int:item_id>/claim/', views.free_claim_submit, name='free_claim_submit'),
    path('free-claims/success/<str:claim_code>/', views.free_claim_success, name='free_claim_success'),
    
    # --- Bookings ---
    path('bookings/', views.bookings_catalog, name='bookings_catalog'),
    path('bookings/<int:booking_id>/', views.booking_detail, name='booking_detail'),
    path('bookings/checkout/<int:booking_id>/', views.booking_checkout, name='booking_checkout'),
    
    # --- Sellable Forms ---
    path('forms/', views.sellable_forms_catalog, name='sellable_forms_catalog'),
    path('forms/<int:form_id>/purchase/', views.sellable_form_purchase, name='sellable_form_purchase'),
    path('forms/checkout/<int:purchase_id>/', views.form_checkout, name='form_checkout'),
    
    # --- Public Donations ---
    path('donations/', views.public_donations, name='public_donations'),
    
    # --- Guest Lookup ---
    path('lookup/', views.guest_lookup, name='guest_lookup'),
    path('cancel/<str:item_type>/<int:item_id>/', views.public_cancel_item, name='public_cancel_item'),
    
    # ============================================================
    # 2. PAYMENT VIEWS
    # ============================================================
    
    path('webhook/paystack/', views.paystack_webhook, name='paystack_webhook'),
    path('payment/callback/', views.paystack_callback, name='paystack_callback'),
    
    
    # ============================================================
    # 3. DASHBOARD (EXCO)
    # ============================================================
    
    path('dashboard/', views.dashboard, name='dashboard'),
    
    
    # ============================================================
    # 4. ADMIN/EXCO VIEWS
    # ============================================================
    
    # ---------- Collection Centers ----------
    path('admin/collection-centers/', views.admin_collection_center_list, name='admin_collection_center_list'),
    path('admin/collection-centers/create/', views.admin_collection_center_create, name='admin_collection_center_create'),
    path('admin/collection-centers/<int:pk>/edit/', views.admin_collection_center_edit, name='admin_collection_center_edit'),
    path('admin/collection-centers/<int:pk>/delete/', views.admin_collection_center_delete, name='admin_collection_center_delete'),
    
    # ---------- Bank Accounts ----------
    path('admin/bank-accounts/', views.admin_bank_account_list, name='admin_bank_account_list'),
    path('admin/bank-accounts/create/', views.admin_bank_account_create, name='admin_bank_account_create'),
    path('admin/bank-accounts/<int:pk>/edit/', views.admin_bank_account_edit, name='admin_bank_account_edit'),
    path('admin/bank-accounts/<int:pk>/delete/', views.admin_bank_account_delete, name='admin_bank_account_delete'),
    
    # ---------- Transactions ----------
    path('admin/transactions/', views.admin_transaction_list, name='admin_transaction_list'),
    path('admin/transactions/create/', views.admin_transaction_create, name='admin_transaction_create'),
    path('admin/transactions/<int:pk>/edit/', views.admin_transaction_edit, name='admin_transaction_edit'),
    path('admin/transactions/<int:pk>/delete/', views.admin_transaction_delete, name='admin_transaction_delete'),
    path('admin/transactions/<int:pk>/correct/', views.admin_transaction_correct, name='admin_transaction_correct'),
    path('admin/transactions/export/', views.admin_transaction_export, name='admin_transaction_export'),
    
    # ---------- Equipment ----------
    path('admin/equipment/', views.admin_equipment_list, name='admin_equipment_list'),
    path('admin/equipment/create/', views.admin_equipment_create, name='admin_equipment_create'),
    path('admin/equipment/<int:pk>/edit/', views.admin_equipment_edit, name='admin_equipment_edit'),
    path('admin/equipment/<int:pk>/delete/', views.admin_equipment_delete, name='admin_equipment_delete'),
    path('admin/equipment/export/', views.admin_equipment_export, name='admin_equipment_export'),
    
    # ---------- Equipment Borrows ----------
    path('admin/equipment-borrows/', views.admin_equipment_borrow_list, name='admin_equipment_borrow_list'),
    path('admin/equipment-borrows/create/', views.admin_equipment_borrow_create, name='admin_equipment_borrow_create'),
    path('admin/equipment-borrows/<int:pk>/edit/', views.admin_equipment_borrow_edit, name='admin_equipment_borrow_edit'),
    path('admin/equipment-borrows/<int:pk>/delete/', views.admin_equipment_borrow_delete, name='admin_equipment_borrow_delete'),
    path('admin/equipment-borrows/<int:pk>/return/', views.admin_equipment_borrow_mark_returned, name='admin_equipment_borrow_mark_returned'),
    
    # ---------- Shop Items ----------
    path('admin/shop/', views.admin_shop_list, name='admin_shop_list'),
    path('admin/shop/create/', views.admin_shop_create, name='admin_shop_create'),
    path('admin/shop/<int:pk>/edit/', views.admin_shop_edit, name='admin_shop_edit'),
    path('admin/shop/<int:pk>/delete/', views.admin_shop_delete, name='admin_shop_delete'),
    path('admin/shop/export/', views.admin_shop_export, name='admin_shop_export'),
    
    # ---------- Shop Orders ----------
    path('admin/shop-orders/', views.admin_shop_order_list, name='admin_shop_order_list'),
    path('admin/shop-orders/<int:pk>/edit/', views.admin_shop_order_edit, name='admin_shop_order_edit'),
    path('admin/shop-orders/<int:pk>/delete/', views.admin_shop_order_delete, name='admin_shop_order_delete'),
    
    # ---------- Sellable Forms ----------
    path('admin/sellable-forms/', views.admin_sellable_form_list, name='admin_sellable_form_list'),
    path('admin/sellable-forms/create/', views.admin_sellable_form_create, name='admin_sellable_form_create'),
    path('admin/sellable-forms/<int:pk>/edit/', views.admin_sellable_form_edit, name='admin_sellable_form_edit'),
    path('admin/sellable-forms/<int:pk>/delete/', views.admin_sellable_form_delete, name='admin_sellable_form_delete'),
    
    # ---------- Form Purchases ----------
    path('admin/form-purchases/', views.admin_form_purchase_list, name='admin_form_purchase_list'),
    path('admin/form-purchases/<int:pk>/edit/', views.admin_form_purchase_edit, name='admin_form_purchase_edit'),
    path('admin/form-purchases/<int:pk>/delete/', views.admin_form_purchase_delete, name='admin_form_purchase_delete'),
    path('admin/form-purchases/<int:pk>/mark-paid/', views.admin_form_purchase_mark_paid, name='admin_form_purchase_mark_paid'),
    path('admin/form-purchases/<int:pk>/mark-verified/', views.admin_form_purchase_mark_verified, name='admin_form_purchase_mark_verified'),
    
    # ---------- Booking Listings ----------
    path('admin/booking-listings/', views.admin_booking_listing_list, name='admin_booking_listing_list'),
    path('admin/booking-listings/create/', views.admin_booking_listing_create, name='admin_booking_listing_create'),
    path('admin/booking-listings/<int:pk>/edit/', views.admin_booking_listing_edit, name='admin_booking_listing_edit'),
    path('admin/booking-listings/<int:pk>/delete/', views.admin_booking_listing_delete, name='admin_booking_listing_delete'),
    
    # ---------- Bookings ----------
    path('admin/bookings/', views.admin_booking_list, name='admin_booking_list'),
    path('admin/bookings/<int:pk>/edit/', views.admin_booking_edit, name='admin_booking_edit'),
    path('admin/bookings/<int:pk>/delete/', views.admin_booking_delete, name='admin_booking_delete'),
    path('admin/bookings/<int:pk>/check-in/', views.admin_booking_check_in, name='admin_booking_check_in'),
    
    # ---------- Free Claims ----------
    path('admin/free-claims/', views.admin_free_claim_list, name='admin_free_claim_list'),
    path('admin/free-claims/<int:pk>/edit/', views.admin_free_claim_edit, name='admin_free_claim_edit'),
    path('admin/free-claims/<int:pk>/delete/', views.admin_free_claim_delete, name='admin_free_claim_delete'),
    path('admin/free-claims/<int:pk>/claim/', views.admin_free_claim_mark_claimed, name='admin_free_claim_mark_claimed'),
    # ============================================================
    # 0. LANDING PAGE (Business Hub)
    # ============================================================
    path('', views.public_business_landing, name='public_landing'),
    
    path('admin/revenue/', views.admin_revenue_report, name='admin_revenue_report'),
    path('admin/revenue/export/', views.admin_revenue_export, name='admin_revenue_export'),
    
    # ---------- Expenses ----------
    path('admin/expenses/', views.admin_expense_report, name='admin_expense_report'),
    path('admin/expenses/create/', views.admin_expense_create, name='admin_expense_create'),    
    
    # ============================================================
    # 5. QR CODE SYSTEM (bookings, shop, claims, forms)
    # ============================================================

    # Public QR display (single route handles all four types)
    path('qr/<str:code>/', views.qr_display, name='qr_display'),

    # Admin scanner
    path('admin/qr-scanner/', views.admin_qr_scanner, name='admin_qr_scanner'),
    path('admin/qr-scanner/lookup/<str:code>/', views.admin_qr_lookup, name='admin_qr_lookup'),
    path('admin/qr-scanner/check-in/<str:kind>/<int:pk>/', views.admin_qr_check_in, name='admin_qr_check_in'),    
    
    
]