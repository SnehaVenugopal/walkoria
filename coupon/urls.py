from django.urls import path
from . import views


urlpatterns = [
    path('', views.coupon_list, name='coupon'),
    path('add/', views.add_coupon, name='add_coupon'),
    path('edit/<int:coupon_id>/', views.edit_coupon, name='edit_coupon'),
    path('delete/<int:coupon_id>/', views.delete_coupon, name='delete_coupon'),
    path('toggle-status/<int:coupon_id>/', views.toggle_coupon_status, name='toggle_coupon_status'),
]

