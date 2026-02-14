"""
URL configuration for allocate project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
# from django.urls import path, include
from django.urls import path, include, re_path
from django.conf import settings
# from data.views import about
from django.conf.urls.static import static


urlpatterns = [
    path('admin/', admin.site.urls),
    path('ap/', include('data.urls')),  # API must come FIRST
    # path('', about, name='about'),
    path('tender/', include('tender.urls')),  # API must come FIRST
    
    # ONLY if you need SPA routing, and ONLY at the very end
    # re_path(r'^(?!ap/).*$', about),  # ← Negative lookahead: exclude 'ap/'
]
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
