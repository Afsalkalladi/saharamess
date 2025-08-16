from django.urls import path
from . import views

app_name = 'scanner'

urlpatterns = [
    # Main scanner interface (token-based access)
    path('', views.scanner_page, name='scanner_page'),
    
    # Staff access management
    path('access/', views.staff_access_generator, name='access_generator'),
    path('access/revoke/', views.revoke_token, name='revoke_token'),
    path('access/list/', views.list_tokens, name='list_tokens'),
    
    # Scanner status and health
    path('status/', views.scanner_status, name='scanner_status'),
    
    # PWA support
    path('offline/', views.offline_page, name='offline_page'),
    path('sw.js', views.service_worker, name='service_worker'),
    path('manifest.json', views.manifest_json, name='manifest_json'),
    
    # Help and support
    path('help/', views.scanner_help, name='scanner_help'),
    path('access-denied/', views.access_denied, name='access_denied'),
]