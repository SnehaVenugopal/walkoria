from django.urls import path
from . import views


urlpatterns = [
    path('', views.wallet_view, name='wallet'),
    path('offer-management/', views.offer_management, name='offer_management'),
    path('edit-offer/<int:offer_id>/', views.edit_offer, name='edit_offer'),
    path('add-offer/', views.add_offer, name='add_offer'),
    path('search-items/', views.search_items, name='search_items'),
    path('delete-offer/<int:offer_id>/', views.delete_offer, name='delete_offer'),
    path('add-money/', views.add_money, name='add_money'),
    path('verify-wallet-payment/', views.verify_wallet_payment, name='verify_wallet_payment'),
]
