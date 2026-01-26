from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.db.models import Prefetch
from django.db import transaction
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse
from decimal import Decimal
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import uuid, time
from django.conf import settings
from .models import Order, OrderItem, ReturnRequest
from cart.models import Cart
from userpanel.models import Address
from .invoice_utils import generate_invoice_pdf
from django.db.models import Q
from coupon.models import Coupon, UserCoupon



@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def checkout(request):
    """Handle checkout process with address selection and payment method"""
    cart = Cart.objects.filter(user=request.user).first()
    if not cart or not cart.items.exists():
        messages.error(request, 'Your cart is empty.')
        return redirect('view_cart')

    addresses = Address.objects.filter(user_id=request.user, is_deleted=False).order_by('-default_address', '-created_at')
    coupon = request.session.get('coupon', {})
    coupon_id = coupon.get('coupon_id')
    discount_amount = Decimal(coupon.get('discount_amount', 0))
    coupon_code = None
    if coupon:
        
        coupon_code = Coupon.objects.get(id=coupon_id)
        total_price_after_coupon_discount = cart.total_price - discount_amount if discount_amount > 0 else cart.total_price
        total_amount = cart.total_price - discount_amount
    else:
        total_price_after_coupon_discount = cart.total_price
    
    
        total_amount = cart.total_price
    
    
    if request.method == 'POST':
        address_id = request.POST.get('address_id')
        payment_method = request.POST.get('payment_method')

        if not address_id or not payment_method:
            messages.error(request, "Please select both address and payment method.")
            return redirect('checkout')
        
        try:
            address = Address.objects.get(id=address_id, user_id=request.user)
        except Address.DoesNotExist:
            messages.error(request, "Selected address not found.")
            return redirect('checkout')
        
        with transaction.atomic():
            # Validate cart items
            for item in cart.items.all():
                if item.variant.is_deleted == True:
                    messages.error(request, f"{item.variant.product.name} - {item.variant} is unavailable right now")
                    return redirect('view_cart')
                elif item.quantity > item.variant.quantity:
                    messages.error(request, f"Not enough stock for {item.variant.product.name} - {item.variant}")
                    return redirect('view_cart')
            
            subtotal = sum(item.price * item.quantity for item in cart.items.all())
            
            # COD limit check
            if payment_method == 'COD' and subtotal > 10000:
                messages.error(request, 'COD not available on orders above ₹10,000.')
                return redirect('checkout')
            
            # Wallet payment validation (static for now)
            if payment_method == 'WP':
                messages.info(request, 'Wallet payment is currently under maintenance. Please choose another payment method.')
                return redirect('checkout')
            
            # Razorpay validation (static for now)
            if payment_method == 'RP':
                messages.info(request, 'Online payment is currently under maintenance. Please choose Cash on Delivery.')
                return redirect('checkout')
            print(subtotal, 'subbbbbbbbbbbbbbbbb')
            # Create order
            order = Order.objects.create(
                user=request.user,
                order_number=uuid.uuid4().hex[:12].upper(),
                coupon=coupon_code,
                discount=discount_amount,
                payment_method=payment_method,
                payment_status=False if payment_method == 'COD' else True,
                subtotal=subtotal,
                total_amount=total_amount,
                shipping_address=address,
                shipping_cost=cart.delivery_charge or 0,
            )
            
            # Create order items
            for item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    product_variant=item.variant,
                    quantity=item.quantity,
                    price=item.price,
                    item_payment_status='Unpaid' if payment_method == 'COD' else 'Paid',
                    original_price=item.variant.actual_price,
                )
                # Reduce stock
                item.variant.quantity -= item.quantity
                item.variant.save()
                
                
            if coupon_code:
                    UserCoupon.objects.create(
                        user=request.user,
                        coupon=coupon_code,
                        order=order,
                    )   
            
            # Clear cart
            cart.delete()
            
            if 'coupon' in request.session:
                    del request.session['coupon']
                    request.session.modified = True

            
            messages.success(request, f"Order placed successfully. Your order number is {order.order_number}")
            return redirect('order_success', order_id=order.id)

    # Calculate total discount for display
    total_discount = cart.get_total_actual_price() - cart.total_price if hasattr(cart, 'get_total_actual_price') else 0
    
    data = {
        'cart': cart,
        'addresses': addresses,
        'total_amount': total_amount,
        'total_discount': total_discount,
        'payment_methods': Order.PAYMENT_METHOD_CHOICES,
        'coupon_code': coupon_code,
        'discount_amount': discount_amount,
        'total_price_after_coupon_discount': total_price_after_coupon_discount,
    }
    
   
    return render(request, 'checkout.html', data)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def order_success(request, order_id):
    """Display order success page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})


# @login_required
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
# def my_orders(request):
#     """Display user's orders with filtering and pagination"""
#     orders = Order.objects.filter(user=request.user)
#     search_query = request.GET.get('search', '')
#     status_filter = request.GET.get('status', '')

#     if search_query:
#         orders = orders.filter(order_number__icontains=search_query)

#     order_items_query = OrderItem.objects.all()
#     if status_filter:
#         order_items_query = order_items_query.filter(status=status_filter)
    
#     orders = orders.prefetch_related(
#         Prefetch('items', queryset=order_items_query, to_attr='filtered_items')
#     ).order_by('-created_at')
    
#     if status_filter:
#         orders = [order for order in orders if order.filtered_items]

#     # Pagination
#     page = request.GET.get('page', 1)
#     paginator = Paginator(orders, 5)
#     try:
#         orders = paginator.page(page)
#     except PageNotAnInteger:
#         orders = paginator.page(1)
#     except EmptyPage:
#         orders = paginator.page(paginator.num_pages)
    
#     status_choices = OrderItem.STATUS_CHOICES
#     data = {
#         'orders': orders,
#         'status_choices': status_choices,
#         'search_query': search_query,
#         'status_filter': status_filter,
#     }
#     print("hhhhhhhhhhhhhhh",data)
#     return render(request, 'my_orders.html', data)
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def my_orders(request):
    """Display user's orders with filtering and pagination"""
    orders_queryset = Order.objects.filter(user=request.user)
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')

    # Apply search filter
    if search_query:
        orders_queryset = orders_queryset.filter(
            Q(order_number__icontains=search_query) |
            Q(items__product_variant__product__name__icontains=search_query)
        ).distinct()

    if status_filter:
        # Filter orders that have at least one item with the specified status
        orders_queryset = orders_queryset.filter(items__status=status_filter).distinct()
        
        # Create prefetch for filtered items only
        order_items_query = OrderItem.objects.select_related(
            'product_variant__product'
        ).prefetch_related(
            'product_variant__product__images'
        ).filter(status=status_filter)
        
        orders_queryset = orders_queryset.prefetch_related(
            Prefetch('items', queryset=order_items_query, to_attr='filtered_items')
        ).select_related('shipping_address').order_by('-created_at')
    else:
        # No status filter - get all items
        order_items_query = OrderItem.objects.select_related(
            'product_variant__product'
        ).prefetch_related(
            'product_variant__product__images'
        )
        
        orders_queryset = orders_queryset.prefetch_related(
            Prefetch('items', queryset=order_items_query)
        ).select_related('shipping_address').order_by('-created_at')

    paginator = Paginator(orders_queryset, 5)
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)
    
    status_choices = OrderItem.STATUS_CHOICES
    context = {
        'orders': page_obj,  # Pass page object directly instead of object_list
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
        'status_choices': status_choices,
        'search_query': search_query,
        'status_filter': status_filter,
        'total_orders': paginator.count,  # Use paginator count for total
    }

    return render(request, 'my_orders.html', context)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def order_detail(request, order_id):
    """Display detailed order information"""
    order = get_object_or_404(
        Order.objects.select_related('shipping_address').prefetch_related('items__product_variant__product__images'),
        id=order_id,
        user=request.user
    )
    print(dir(order), order.subtotal, order.total_amount)
    return render(request, 'order_detail.html', {'order': order})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def cancel_product(request, item_id):
    """Handle product cancellation with refund logic"""
    try:
        order_item = OrderItem.objects.get(id=item_id, order__user=request.user)
        order = order_item.order
    except OrderItem.DoesNotExist:
        messages.error(request, 'Order item not found.')
        return redirect('my_orders')
    
    # Check if item can be cancelled
    if order_item.status in ['Delivered', 'Cancelled', 'Returned']:
        messages.error(request, 'This item cannot be cancelled.')
        return redirect('order_detail', order_id=order.id)
    
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason')
        custom_reason = request.POST.get('custom_reason')
        
        if reason == 'custom':
            order_item.custom_cancellation_reason = custom_reason
        else:
            order_item.cancellation_reason = reason

        # Update order status
        order_item.is_cancelled = True
        order_item.status = 'Cancelled'
        order_item.save()
        
        # Restore stock
        product_variant = order_item.product_variant
        product_variant.quantity += order_item.quantity
        product_variant.save()

        # Calculate refund amount
        total_item_price = order_item.price * order_item.quantity
        proportion = total_item_price / (order.total_amount + order.discount) if (order.total_amount + order.discount) > 0 else 0
        allocated_discount = order.discount * proportion
        refund_amount = total_item_price - allocated_discount
        # After updating subtotal
        order.subtotal -= refund_amount
        
        # Recalculate delivery charge:
        if order.subtotal <= 0:  
            order.shipping_cost = 0  
            order.total_amount = 0  
        else:
            order.shipping_cost = 99  # or your dynamic logic
            order.total_amount = order.subtotal + order.shipping_cost - order.discount

        order.save()

        # Handle refund for paid orders (wallet refund would go here)
        if order.payment_method in ['RP', 'WP'] and order_item.item_payment_status == 'Paid':
            # For now, just mark as refunded - actual wallet refund would be implemented here
            order_item.item_payment_status = 'Refunded'
            
        elif order.payment_method == 'COD':
            
            order_item.item_payment_status = 'Cancelled'
        else:
            order_item.item_payment_status = 'Processing'
        
        order_item.save()
        
        messages.success(request, 'Product has been cancelled successfully.')
       
    
    cancellation_reasons = OrderItem.CANCELLATION_REASON_CHOICES
    return render(request, 'cancellation_reason.html', {
        'order_item': order_item,
        'cancellation_reasons': cancellation_reasons
    })


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def return_product(request, item_id):
    """Handle product return request"""
    order_item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    
    # Check if item can be returned
    if order_item.status != 'Delivered':
        messages.error(request, 'Only delivered items can be returned.')
        return redirect('order_detail', order_id=order_item.order.id)
    
    if request.method == 'POST':
        reason = request.POST.get('cancellation_reason')
        custom_reason = request.POST.get('custom_reason')
        
        if reason == 'custom':
            order_item.custom_cancellation_reason = custom_reason
        else:
            order_item.cancellation_reason = reason
        
        order_item.status = 'Return_Requested'
        order_item.save()
        
        # Create a return request
        ReturnRequest.objects.create(order=order_item)
        
        messages.success(request, 'Product return request has been submitted successfully.')
        # return JsonResponse({'status': 'success', 'message': 'Product return request has been submitted successfully.'})
    
    cancellation_reasons = OrderItem.CANCELLATION_REASON_CHOICES
    return render(request, 'cancellation_reason.html', {
        'order_item': order_item,
        'cancellation_reasons': cancellation_reasons
    })


@login_required
def download_invoice(request, item_id):
    """Generate and download invoice PDF"""
    order_item = get_object_or_404(OrderItem, id=item_id, order__user=request.user)
    
    # if order_item.status != 'Delivered':
    #     messages.error(request, "Invoice not available for this item")
    #     return redirect('order_detail', order_id=order_item.order.id)
    
    if not order_item.invoice_number:
        order_item.save()  # This will trigger invoice number generation
    address =Address.objects.get(id=order_item.order.shipping_address_id)
    try:
        pdf = generate_invoice_pdf(order_item, address)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{order_item.invoice_number}.pdf"'
        return response
    except Exception as e:
        messages.error(request, "Error generating invoice. Please try again.")
        return redirect('order_detail', order_id=order_item.order.id)
