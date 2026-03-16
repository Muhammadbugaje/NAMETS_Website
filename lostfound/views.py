from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import Item

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