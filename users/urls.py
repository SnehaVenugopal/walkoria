# urls.py
from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.login_view, name='login'),  # This name must match
    path('signup/', views.signup_view, name='signup'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    
    path('resend-otp/', views.verify_otp_view, name='resend_otp'),
    
    path('auth/forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('auth/reset-password/', views.reset_password_view, name='reset_password'),
    path('auth/resend-reset-otp/', views.resend_reset_otp_view, name='resend_reset_otp'),
    path('create/auth/verify-reset-otp/', views.verify_reset_otp_view, name='verify_reset_otp'),  # Added missing URL pattern
    path('logout/', views.logout_account, name='logout_account'),
    path('resend/', views.resend_otp_view, name='resend'),
    
]


