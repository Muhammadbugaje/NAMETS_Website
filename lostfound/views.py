
from django.db.models import Q
from .models import Item

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.utils import timezone
from django.forms import ModelForm



# Create your views here.

def item_list(request):
    # Get filter parameters
    filter_type = request.GET.get('filter', 'lost')       # status tab (lost, found, claimed) to filter
    query = request.GET.get('q', '')                      # search text to filter title/description
    category = request.GET.get('category', '')            # selected category to filter

    # Base queryset based on status tab
    if filter_type == 'found':
        items = Item.objects.filter(status='found', is_active=True)
    elif filter_type == 'claimed':
        items = Item.objects.filter(status='claimed', is_active=True)
    else:
        items = Item.objects.filter(status='lost', is_active=True)
        filter_type = 'lost'  # just incase but its the only option left, we default to lost

    # Apply search filter (if any)
    if query:
        items = items.filter(
            Q(title__icontains=query) | Q(description__icontains=query)
        )

    # Apply category filter (if any)
    if category:
        items = items.filter(category=category)

    items = items.order_by('-reported_at')

    # Get distinct categories currently in use (for dropdown)
    used_categories = Item.objects.filter(is_active=True).values_list('category', flat=True).distinct().order_by('-reported_at')
    category_choices = [('', 'All Categories')] + list(Item.CATEGORY_CHOICES)

    return render(request, 'lostfound/item_list.html', {
        'items': items,
        'filter': filter_type,
        'query': query,
        'selected_category': category,
        'category_choices': category_choices,
    })

def item_detail(request, pk):
    item = get_object_or_404(Item, pk=pk, is_active=True)
    return render(request, 'lostfound/item_detail.html', {'item': item})



# ============================================================
# ADMIN/EXCO VIEWS
# ============================================================

@login_required
def admin_item_list(request):
    """EXCO dashboard — full list with search, filters, pagination."""
    if not request.user.has_perm('lostfound.view_item'):
        messages.error(request, "You don't have permission to view lost & found items.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    category_filter = request.GET.get('category', '')

    items = Item.objects.all().order_by('-reported_at')

    if query:
        items = items.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query) |
            Q(claimed_by_name__icontains=query)
        )

    if status_filter:
        items = items.filter(status=status_filter)

    if category_filter:
        items = items.filter(category=category_filter)

    paginator = Paginator(items, 20)
    page = request.GET.get('page')
    items_page = paginator.get_page(page)

    categories = Item.CATEGORY_CHOICES
    statuses = Item.STATUS_CHOICES

    return render(request, 'lostfound/admin/item_list.html', {
        'items': items_page,
        'page_obj': items_page,
        'is_paginated': items_page.has_other_pages(),
        'query': query,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'categories': categories,
        'statuses': statuses,
    })


@login_required
def admin_item_create(request):
    """Create a new lost/found item."""
    if not request.user.has_perm('lostfound.add_item'):
        messages.error(request, "You don't have permission to create items.")
        return redirect('lostfound:admin_item_list')

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES)
        if form.is_valid():
            item = form.save()
            messages.success(request, f"✅ Item '{item.title}' created successfully!")
            return redirect('lostfound:admin_item_list')
    else:
        form = ItemForm()

    return render(request, 'lostfound/admin/item_form.html', {
        'form': form,
        'title': 'Create Lost/Found Item',
        'button_text': 'Create Item',
    })


@login_required
def admin_item_edit(request, pk):
    """Edit an existing lost/found item."""
    item = get_object_or_404(Item, pk=pk)

    if not request.user.has_perm('lostfound.change_item'):
        messages.error(request, "You don't have permission to edit this item.")
        return redirect('lostfound:admin_item_list')

    if request.method == 'POST':
        form = ItemForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            form.save()
            messages.success(request, f"✅ Item '{item.title}' updated successfully!")
            return redirect('lostfound:admin_item_list')
    else:
        form = ItemForm(instance=item)

    return render(request, 'lostfound/admin/item_form.html', {
        'form': form,
        'item': item,
        'title': 'Edit Lost/Found Item',
        'button_text': 'Update Item',
    })


@login_required
def admin_item_delete(request, pk):
    """Delete an item with confirmation."""
    item = get_object_or_404(Item, pk=pk)

    if not request.user.has_perm('lostfound.delete_item'):
        messages.error(request, "You don't have permission to delete this item.")
        return redirect('lostfound:admin_item_list')

    if request.method == 'POST':
        title = item.title
        item.delete()
        messages.success(request, f"🗑️ Item '{title}' deleted successfully!")
        return redirect('lostfound:admin_item_list')

    return render(request, 'lostfound/admin/item_confirm_delete.html', {
        'item': item,
    })


@login_required
def admin_item_mark_claimed(request, pk):
    """Mark an item as claimed (quick action)."""
    item = get_object_or_404(Item, pk=pk)

    if not request.user.has_perm('lostfound.change_item'):
        messages.error(request, "You don't have permission to update this item.")
        return redirect('lostfound:admin_item_list')

    if item.status == 'found':
        item.status = 'claimed'
        item.claimed_at = timezone.now()
        item.save()
        messages.success(request, f"✅ '{item.title}' marked as claimed!")
    else:
        messages.warning(request, f"Item must be 'Found' before it can be claimed.")

    return redirect('lostfound:admin_item_list')


# ============================================================
# FORM
# ============================================================

from django import forms


class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = [
            'title', 'description', 'image', 'status',
            'category', 'is_active',
            'claimed_by_name', 'claimed_by_contact'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter item title...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe the item in detail...'
            }),
            'image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'claimed_by_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Who claimed it?"
            }),
            'claimed_by_contact': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': "Phone or email..."
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        claimed_by_name = cleaned_data.get('claimed_by_name')
        claimed_by_contact = cleaned_data.get('claimed_by_contact')

        if status == 'claimed':
            if not claimed_by_name:
                self.add_error('claimed_by_name', "Required when status is 'Claimed'.")
            if not claimed_by_contact:
                self.add_error('claimed_by_contact', "Required when status is 'Claimed'.")

        return cleaned_data



