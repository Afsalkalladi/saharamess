from django.urls import path
from . import views

app_name = 'admin_panel'

urlpatterns = [
    # Authentication
    path('login/', views.admin_login, name='admin_login'),
    path('logout/', views.admin_logout, name='admin_logout'),
    
    # Dashboard
    path('', views.admin_dashboard, name='admin_dashboard'),
    
    # Students Management
    path('students/', views.students_list, name='students_list'),
    path('students/<uuid:student_id>/approve/', views.approve_student, name='approve_student'),
    path('students/<uuid:student_id>/deny/', views.deny_student, name='deny_student'),
    
    # Payments Management
    path('payments/', views.payments_list, name='payments_list'),
    path('payments/<uuid:payment_id>/verify/', views.verify_payment, name='verify_payment'),
    path('payments/<uuid:payment_id>/deny/', views.deny_payment, name='deny_payment'),
    
    # Reports
    path('reports/', views.reports, name='reports'),
    path('export/', views.export_data, name='export_data'),
    
    # Settings
    path('settings/', views.settings_page, name='settings'),
]