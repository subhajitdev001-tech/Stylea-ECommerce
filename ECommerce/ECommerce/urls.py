"""
URL configuration for ECommerce project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import path

# Customizing the text
admin.site.site_header = "S T Y L É A"  # Top navigation bar title
admin.site.site_title = "Admin Dashboard"          # Browser tab title
admin.site.index_title = "Welcome to the S T Y L É A Portal"    # Main dashboard header

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('project.urls')),
]

if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()