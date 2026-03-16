from django.shortcuts import render, get_object_or_404
from .models import Gallery

def gallery_list(request):
    galleries = Gallery.objects.all()
    return render(request, 'gallery/list.html', {'galleries': galleries})

def gallery_detail(request, pk):
    gallery = get_object_or_404(Gallery, pk=pk)
    return render(request, 'gallery/detail.html', {'gallery': gallery})
