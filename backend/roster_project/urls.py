"""URL configuration for roster_project."""

import os
from django.contrib import admin
from django.urls import path, re_path, include
from django.views.static import serve
from django.http import HttpResponse, FileResponse
from django.conf import settings

DIST_DIR = os.path.join(settings.BASE_DIR, '..', 'frontend', 'dist')

def serve_spa(request):
    index_file = os.path.join(DIST_DIR, 'index.html')
    if os.path.exists(index_file):
        return FileResponse(open(index_file, 'rb'), content_type='text/html')
    return HttpResponse("<h1>Smart Roster API is running</h1><p>Visit <a href='/api/'>/api/</a> or run <code>npm run dev</code> in frontend.</p>")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('roster.urls')),
    re_path(r'^assets/(?P<path>.*)$', serve, {'document_root': os.path.join(DIST_DIR, 'assets')}),
    re_path(r'^(?!api|admin|assets).*$', serve_spa),
]
