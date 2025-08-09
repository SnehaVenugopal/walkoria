# urls.py
from django.urls import path
from . import views


urlpatterns = [
    path('login/', views.login_view, name='login'),  # This name must match
    path('signup/', views.signup_view, name='signup'),
    path('verify-otp/', views.verify_otp_view, name='verify_otp'),
    # path('', views.home_view, name='home'),
    path('resend-otp/', views.verify_otp_view, name='resend_otp'),
    # path('',views.landing_page,name='landing_page'),
    path('forgot-password/', views.forgot_password, name='forgot_pass'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('forgot_pass_otp/', views.forgot_pass_verify_otp, name='forgot_pass_otp'),
    path('logout/', views.logout_account, name='logout_account'),
    path('resend/', views.resend_otp_view, name='resend'),
    
]



