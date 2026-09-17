from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.forms import inlineformset_factory
from django import forms
from .models import Gallery, GalleryImage



def gallery_list(request):
    galleries = Gallery.objects.all()
    return render(request, 'gallery/list.html', {'galleries': galleries})

def gallery_detail(request, pk):
    gallery = get_object_or_404(Gallery, pk=pk)
    return render(request, 'gallery/detail.html', {'gallery': gallery})


# ============================================================
# ADMIN/EXCO VIEWS
# ============================================================

@login_required
def admin_gallery_list(request):
    """EXCO dashboard — full list with search, pagination."""
    if not request.user.has_perm('gallery.view_gallery'):
        messages.error(request, "You don't have permission to view galleries.")
        return redirect('dashboards:dashboard')

    query = request.GET.get('q', '')
    galleries = Gallery.objects.all().order_by('-date', '-created_at')

    if query:
        galleries = galleries.filter(
            Q(title__icontains=query) |
            Q(description__icontains=query)
        )

    paginator = Paginator(galleries, 12)
    page = request.GET.get('page')
    galleries_page = paginator.get_page(page)

    return render(request, 'gallery/admin/gallery_list.html', {
        'galleries': galleries_page,
        'page_obj': galleries_page,
        'is_paginated': galleries_page.has_other_pages(),
        'query': query,
    })


@login_required
def admin_gallery_create(request):
    """Create a new gallery with images."""
    if not request.user.has_perm('gallery.add_gallery'):
        messages.error(request, "You don't have permission to create galleries.")
        return redirect('gallery:admin_gallery_list')

    GalleryImageFormSet = inlineformset_factory(
        Gallery,
        GalleryImage,
        fields=['image', 'caption', 'order'],
        extra=3,
        max_num=20,
        can_delete=True,
        widgets={
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Image caption'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'type': 'number', 'min': 0}),
        }
    )

    if request.method == 'POST':
        form = GalleryForm(request.POST, request.FILES)
        formset = GalleryImageFormSet(request.POST, request.FILES, instance=Gallery())

        if form.is_valid() and formset.is_valid():
            gallery = form.save()
            formset.instance = gallery
            formset.save()
            messages.success(request, f"✅ Gallery '{gallery.title}' created successfully!")
            return redirect('gallery:admin_gallery_list')
    else:
        form = GalleryForm()
        formset = GalleryImageFormSet(instance=Gallery())

    return render(request, 'gallery/admin/gallery_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Create Gallery',
        'button_text': 'Create Gallery',
    })


@login_required
def admin_gallery_edit(request, pk):
    """Edit an existing gallery and its images."""
    gallery = get_object_or_404(Gallery, pk=pk)

    if not request.user.has_perm('gallery.change_gallery'):
        messages.error(request, "You don't have permission to edit this gallery.")
        return redirect('gallery:admin_gallery_list')

    GalleryImageFormSet = inlineformset_factory(
        Gallery,
        GalleryImage,
        fields=['image', 'caption', 'order'],
        extra=3,
        max_num=20,
        can_delete=True,
        widgets={
            'image': forms.FileInput(attrs={'class': 'form-control'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Image caption'}),
            'order': forms.NumberInput(attrs={'class': 'form-control', 'type': 'number', 'min': 0}),
        }
    )

    if request.method == 'POST':
        form = GalleryForm(request.POST, request.FILES, instance=gallery)
        formset = GalleryImageFormSet(request.POST, request.FILES, instance=gallery)

        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f"✅ Gallery '{gallery.title}' updated successfully!")
            return redirect('gallery:admin_gallery_list')
    else:
        form = GalleryForm(instance=gallery)
        formset = GalleryImageFormSet(instance=gallery)

    return render(request, 'gallery/admin/gallery_form.html', {
        'form': form,
        'formset': formset,
        'gallery': gallery,
        'title': 'Edit Gallery',
        'button_text': 'Update Gallery',
    })


@login_required
def admin_gallery_delete(request, pk):
    """Delete a gallery with confirmation."""
    gallery = get_object_or_404(Gallery, pk=pk)

    if not request.user.has_perm('gallery.delete_gallery'):
        messages.error(request, "You don't have permission to delete this gallery.")
        return redirect('gallery:admin_gallery_list')

    if request.method == 'POST':
        title = gallery.title
        gallery.delete()
        messages.success(request, f"🗑️ Gallery '{title}' deleted successfully!")
        return redirect('gallery:admin_gallery_list')

    return render(request, 'gallery/admin/gallery_confirm_delete.html', {
        'gallery': gallery,
    })


# ============================================================
# FORM
# ============================================================

from django import forms
from .models import Gallery


class GalleryForm(forms.ModelForm):
    class Meta:
        model = Gallery
        fields = ['title', 'description', 'date', 'cover_image']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter gallery title...'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Describe this gallery...'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'cover_image': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['title'].required = True
        self.fields['date'].required = True