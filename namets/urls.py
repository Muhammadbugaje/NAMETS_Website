"""
URL configuration for namets project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from communications.views_admin import send_custom_message

urlpatterns = [
    path('', include('core.urls')),
    path('communications/', include('communications.urls')),
    path('events/', include('events.urls')),
    path('academics/', include('academics.urls')),
    path('lostfound/', include('lostfound.urls')),
    path('community/', include('community.urls')),
    path('gallery/', include('gallery.urls')),
    path('api/communications/', include('communications.api_urls')),
    path('api/events/', include('events.api_urls')),
    path('api/', include('api.urls')),
    path('admin/communications/send-custom-message/', send_custom_message, name='admin_send_custom_message'),
    path('admin/', admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)