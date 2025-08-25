from django.urls import path
from . import views

urlpatterns = [
    path('', views.products_view, name='product'),
     path('product/toggle/<int:product_id>/', views.toggle_product_status, name='toggle_product_status'),
    path('delete-variant/<int:id>/', views.delete_variant, name='delete-variant'),
    path('add/', views.add_product, name='add_product'),
    path('cancel-add/', views.cancel_add_product, name='cancel_add_product'),
    path('edit/<int:product_id>/', views.edit_product, name='edit_product'),
]

