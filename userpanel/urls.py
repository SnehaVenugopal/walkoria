from django.urls import path
from . import views

urlpatterns = [
    # Profile URLs
    path('profile/', views.user_profile, name='profile'),
    path('update-profile/', views.update_profile, name='update_profile'),
    path('cancel/', views.cancel_profile_update, name='cancel_profile_update'),
    
    # Password URLs
    path('change-password/', views.change_password, name='change_password'),
    
    # Address Management URLs
    path('manage-address/', views.manage_address, name='manage_address'),
    path('add-address/', views.add_address, name='add_address'),
    path('edit-address/<int:address_id>/', views.edit_address, name='edit_address'),
    path('delete-address/<int:address_id>/', views.delete_address, name='delete_address'),
    path('set-default-address/<int:address_id>/', views.set_default_address, name='set_default_address'),
    
    # Orders URLs
    
    
    # Wishlist URLs
    path('wishlist/', views.wishlist, name='wishlist'),
    path('toggle-wishlist/<int:product_id>/<str:product_size>/', views.toggle_wishlist, name='toggle_wishlist'),
    path('is-wishlisted/<int:product_id>/', views.is_wishlisted, name='is_wishlisted'),
    path('get-variant-id/<int:product_id>/<str:product_size>/', views.get_variant_id, name='get_variant_id'),
    
    # Placeholder URLs for future implementation
    path('wallet/', views.wallet, name='wallet'),
    path('refer-earn/', views.refer_earn, name='refer_earn'),
    
]
