from django.urls import path
from . import views


urlpatterns = [
    path('checkout/', views.checkout, name='checkout'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('my-orders/', views.my_orders, name='my_orders'),
    path('order-detail/<int:order_id>/', views.order_detail, name='order_detail'),
    path('cancel-product/<int:item_id>/', views.cancel_product, name='cancel_product'),
    path('return-product/<int:item_id>/', views.return_product, name='return_product'),
    path('download-invoice/<int:item_id>/', views.download_invoice, name='download_invoice'),
    path('paypal-checkout/<int:order_id>/', views.paypal_checkout, name='paypal_checkout'),
    path('paypal/create/', views.create_paypal_payment, name='create_paypal_payment'),
    path('paypal/capture/', views.capture_paypal_payment, name='capture_paypal_payment'),
    
    
    
    path('razorpay/create/', views.create_razorpay_order, name='create_razorpay_order'),
    path('razorpay/verify/', views.verify_razorpay_payment, name='verify_razorpay_payment'),
]

