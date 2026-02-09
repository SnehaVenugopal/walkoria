from django.urls import path
from . import views

app_name = 'referral'

urlpatterns = [
    path('my-referrals/', views.my_referrals, name='my_referrals'),
    path('apply-code/', views.apply_referral_code, name='apply_code'),
]
