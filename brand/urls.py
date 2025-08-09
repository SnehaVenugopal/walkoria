from django.urls import path
from . import views

urlpatterns = [
    path('', views.brand_list, name='brand'),
    path('add/', views.add_brand, name='add_brand'),
    path('edit/<int:brand_id>/', views.edit_brand, name='edit_brand'),
    path('delete/<int:brand_id>/', views.delete_brand, name='delete_brand'),
    path('toggle/<int:brand_id>/', views.toggle_brand_status, name='toggle_brand_status'),
]
