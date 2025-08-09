# urls.py
from django.urls import path
from . import views


urlpatterns = [
        # path('login/', views.login_view, name='login'),  # This name must match
        path('', views.login_to_account, name='login_to_account'),
        path('dashboard/', views.dashboard_view, name='admin_dashboard'),
        path('customers/', views.customers_view, name='customers'),
        path('customer_status/',views.customer_status,name='customer_status')
        
    ]
