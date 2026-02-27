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
import uuid, time, logging
from django.conf import settings
from .models import Order, OrderItem, ReturnRequest
from cart.models import Cart
from userpanel.models import Address
from .invoice_utils import generate_invoice_pdf
from django.db.models import Q
from coupon.models import Coupon, UserCoupon
from wallet.models import Wallet, WalletTransaction
import json
import requests
import base64
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from .models import Order, OrderItem

logger = logging.getLogger(__name__)
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def checkout(request):
    try:
        """Handle checkout process with address selection and payment method"""
        cart = Cart.objects.filter(user=request.user).first()
        if not cart or not cart.items.exists():
            messages.error(request, 'Your cart is empty.')
            return redirect('view_cart')

        addresses = Address.objects.filter(user_id=request.user, is_deleted=False).order_by('-default_address', '-created_at')
        coupon = request.session.get('coupon', {})
        coupon_id = coupon.get('coupon_id')
        discount_amount = Decimal(str(coupon.get('discount_amount', 0) or 0))
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
                # Validate cart items - check for out of stock and unavailable products
                out_of_stock_items = []
                for item in cart.items.all():
                    if item.variant.is_deleted == True:
                        messages.error(request, f"{item.variant.product.name} - {item.variant} is unavailable right now")
                        return redirect('view_cart')
                    elif item.variant.quantity == 0:
                        out_of_stock_items.append(f"{item.variant.product.name} (Size: {item.variant.size})")
                    elif item.quantity > item.variant.quantity:
                        messages.error(request, f"Not enough stock for {item.variant.product.name} - {item.variant}. Only {item.variant.quantity} available.")
                        return redirect('view_cart')
                
                # If there are out of stock items, show error and redirect to cart
                if out_of_stock_items:
                    if len(out_of_stock_items) == 1:
                        messages.error(request, f"{out_of_stock_items[0]} is out of stock. Please remove it from your cart to proceed.")
                    else:
                        items_str = ", ".join(out_of_stock_items)
                        messages.error(request, f"The following items are out of stock: {items_str}. Please remove them from your cart to proceed.")
                    return redirect('view_cart')
                
                subtotal = sum(item.price * item.quantity for item in cart.items.all())
                
                # COD limit check (based on total payable amount after discounts)
                if payment_method == 'COD' and total_amount > 1000:
                    messages.error(request, 'Cash on Delivery is not available for orders above ₹1,000. Please choose an online payment method.')
                    return redirect('checkout')
                
                # Wallet payment validation
                if payment_method == 'WP':
                        # Get or create wallet for the user
                        wallet, created = Wallet.objects.get_or_create(user=request.user)
                        
                        if not wallet.is_active:
                            messages.error(request, 'Your wallet is inactive. Please contact customer care.')
                            return redirect('checkout')
                        if wallet.balance < total_amount:
                            messages.error(request, 'Insufficient balance in your wallet. Please choose a different payment method.')
                            return redirect('checkout')
                        
                # Razorpay validation (static for now)
                if payment_method == 'RP':
                    pass

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
                        
                if payment_method == 'WP':

                    with transaction.atomic():
                        # Get wallet (should exist due to validation above)
                        wallet, created = Wallet.objects.get_or_create(user=request.user)
                        wallet.refresh_from_db()
                        wallet.balance = wallet.balance - Decimal(str(total_amount))
                        wallet.save()
                        WalletTransaction.objects.create(
                                wallet=wallet,
                                transaction_type="Dr",
                                amount=Decimal(str(total_amount)),
                                status="Completed",
                                description=f"Payment for Order #{order.order_number}",
                                order=order,
                                transaction_id="TXN-" + str(int(time.time())) + uuid.uuid4().hex[:4].upper(),
                            )
                        order.items.update(item_payment_status='Paid')
                        order.payment_status = True
                        order.save()
                        

                # Check if this is the user's first order and give referral rewards
                # MOVED TO ADMIN/VIEWS.PY (Rewards given on Delivery)
                # from referral.models import Referral, ReferralOffer
                # from referral.views import give_referral_rewards
                # from django.utils import timezone
                # from django.db.models import Q
                
                # # Check if this is the first successful order by this user
                # previous_orders = Order.objects.filter(user=request.user, payment_status=True).exclude(id=order.id).count()
                
                # if previous_orders == 0:  # This is the first successful order
                #     # Check if user was referred
                #     try:
                #         referral = Referral.objects.get(referred_user=request.user, is_used=True)
                        
                #         # Check if rewards haven't been given yet
                #         if not referral.reward_given_to_referred or not referral.reward_given_to_referrer:
                #             # Get active offer
                #             active_offer = ReferralOffer.objects.filter(
                #                 is_active=True,
                #                 valid_from__lte=timezone.now()
                #             ).filter(
                #                 Q(valid_until__gte=timezone.now()) | Q(valid_until__isnull=True)
                #             ).first()
                            
                #             if active_offer:
                #                 # Give rewards to both users
                #                 # give_referral_rewards(referral, active_offer)
                #                 # logger.info(f"Referral rewards given for user {request.user.id} after first purchase")
                #                 pass
                #     except Referral.DoesNotExist:
                #         # User wasn't referred, do nothing
                #         pass

                
                messages.success(request, f"Order placed successfully. Your order number is {order.order_number}")
                return redirect('order_success', order_id=order.id)

        # Calculate detailed totals for display (similar to cart view)
        total_actual_price = sum(item.variant.actual_price * item.quantity for item in cart.items.all())
        total_sale_price_before_offer = sum(item.variant.sale_price * item.quantity for item in cart.items.all())
        total_normal_discount = total_actual_price - total_sale_price_before_offer
        total_offer_discount = sum(item.get_offer_discount() for item in cart.items.all())
        
        # Subtotal = sale price minus offer discounts (mirrors cart "Subtotal" row)
        subtotal_after_offers = sum(item.get_final_price() for item in cart.items.all())
        
        # Calculate total discount for display (Normal + Offer + Coupon)
        total_discount = total_normal_discount + total_offer_discount + discount_amount
        
        data = {
            'cart': cart,
            'addresses': addresses,
            'total_amount': total_amount,
            'total_discount': total_discount,
            'subtotal_after_offers': subtotal_after_offers,
            'total_actual_price': total_actual_price,
            'total_sale_price_before_offer': total_sale_price_before_offer,
            'total_normal_discount': total_normal_discount,
            'total_offer_discount': total_offer_discount,
            'payment_methods': Order.PAYMENT_METHOD_CHOICES,
            'coupon_code': coupon_code,
            'discount_amount': discount_amount,
            'total_price_after_coupon_discount': total_price_after_coupon_discount,
        }
        
        return render(request, 'checkout.html', data)
    
    except Wallet.DoesNotExist:
        logger.error(f"Wallet not found for user: {request.user.user_id}")
        messages.error(request, 'Wallet not found. Please contact customer support.')
        return redirect('checkout')
    except ValueError as e:
        logger.error(f"ValueError in wallet payment processing: {e}")
        messages.error(request, f"An error occurred while processing your wallet payment.")
        return redirect('checkout')
    # except Exception as e:
    #     logger.error(f"Error in checkout view: {e}")
    #     messages.error(request, "An unexpected error occurred during checkout. Please try again or contact support.")
    #     return redirect('view_cart')

    
    


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def order_success(request, order_id):
    """Display order success page"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def order_failure(request, order_id):
    """Display order failure page when payment fails"""
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_failure.html', {'order': order})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def retry_payment(request, order_id):
    """Retry payment for a failed order"""
    print(f"=== RETRY PAYMENT ===")
    print(f"Order ID: {order_id}")
    
    order = get_object_or_404(Order, id=order_id, user=request.user)
    print(f"Order found: {order.order_number}")
    print(f"Payment status: {order.payment_status}")
    
    # Only allow retry if payment is not completed
    if order.payment_status:
        print("Order already paid, redirecting to order_detail")
        messages.info(request, 'This order has already been paid.')
        return redirect('order_detail', order_id=order.id)
    
    # Render a retry payment page that initiates payment
    from django.conf import settings
    from wallet.utils import razorpay_client
    
    try:
        # Create a new Razorpay order for retry
        razorpay_order_data = {
            'amount': int(order.total_amount * 100),  # Razorpay expects amount in paise
            'currency': 'INR',
            'receipt': f'retry_{order.order_number}',
            'payment_capture': 1
        }
        print(f"Creating Razorpay order with data: {razorpay_order_data}")
        razorpay_order = razorpay_client.order.create(razorpay_order_data)
        print(f"Razorpay order created: {razorpay_order['id']}")
        
        # Update the order with new razorpay_order_id
        order.razorpay_order_id = razorpay_order['id']
        order.save()
        
        context = {
            'order': order,
            'razorpay_order_id': razorpay_order['id'],
            'razorpay_key_id': settings.RAZORPAY_KEY_ID,
            'amount': int(order.total_amount * 100),
            'user_name': request.user.name,
            'user_email': request.user.email,
            'user_phone': request.user.mobile_no or '',
        }
        print(f"Rendering retry_payment.html with context")
        print(f"========================")
        return render(request, 'retry_payment.html', context)
    except Exception as e:
        print(f"ERROR in retry_payment: {e}")
        import traceback
        traceback.print_exc()
        logger.error(f"Error creating Razorpay order for retry: {e}")
        messages.error(request, 'Failed to initiate payment retry. Please try again.')
        return redirect('order_failure', order_id=order.id)


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
    cancellation_reasons = OrderItem.CANCELLATION_REASON_CHOICES
    return render(request, 'order_detail.html', {
        'order': order,
        'cancellation_reasons': cancellation_reasons
    })


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
@transaction.atomic
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

        # Use the exact refund calculation that correctly handles the snapshotted item price
        # and proportional coupon allocation.
        db_item = OrderItem.objects.get(id=order_item.id)
        effective_item_price = db_item.price * db_item.quantity
        
        refund_amount = order_item.get_refund_amount()
        
        # After updating subtotal
        # Note: order.subtotal stores the sum of item.price * quantity.
        # We should deduct the effective value from subtotal.
        order.subtotal -= effective_item_price
        
        # Recalculate delivery charge handling:
        if order.subtotal <= 0:  
            order.shipping_cost = 0  
            order.total_amount = 0  
        else:
            # If subtotal is still positive, we just reduce the total_amount by the refunded CASH amount
            order.total_amount -= refund_amount
            
            # Recalculate shipping if needed (e.g. if it drops below free shipping threshold)
            # For now, let's keep shipping simple or valid as per user business logic.
            # If the user wants to adjust shipping on partial cancellation, that's complex.
            # Assuming shipping cost remains unless order is fully cancelled (which subtotal<=0 covers).
            if order.total_amount < 0:
                order.total_amount = 0

        order.save()

        # Handle wallet refund for paid orders
        # Check if item/order was paid BEFORE changing status
        # We check both item status and overall order payment status to be safe
        # ALSO: If it's an online payment and status is Processing/Shipped/etc, we assume it's paid.
        is_online_payment = order.payment_method in ['RP', 'WP', 'PP']
        
        # Taking a safer approach: If it's Online Payment, assume Paid unless explicitly Failed/Pending.
        # Since we are cancelling a VALID order item (not a failed one), it must be paid.
        was_paid = (
            order_item.item_payment_status == 'Paid' or 
            order.payment_status or 
            (is_online_payment)
        )
        
        print(f"DEBUG REFUND: Item {order_item.id}, Was Paid: {was_paid}, Refund Amount: {refund_amount}")

        # Credit wallet for all paid orders (RP, WP, PP, or COD if delivered/paid)
        if was_paid:
            if refund_amount > 0:
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
                wallet.refresh_from_db()
                refund_decimal = Decimal(str(refund_amount))
                wallet.balance = wallet.balance + refund_decimal
                wallet.save()
                WalletTransaction.objects.create(
                    wallet=wallet,
                    transaction_type="Cr",
                    amount=refund_decimal,
                    status="Completed",
                    description=f"Refund for cancelled product - Order #{order.order_number}",
                    order=order,
                    transaction_id="RF" + str(int(time.time()))[-5:] + uuid.uuid4().hex[:4].upper(),
                )
                order_item.item_payment_status = 'Refunded'
                messages.success(request, f'Product cancelled successfully. ₹{refund_amount:.2f} has been credited to your wallet.')
            else:
                order_item.item_payment_status = 'Refunded'
                messages.warning(request, f'Product cancelled. Refund amount calculated as ₹0.00.')
        elif order.payment_method == 'COD':
            order_item.item_payment_status = 'Cancelled'
            messages.success(request, 'Product has been cancelled successfully.')
        else:
            order_item.item_payment_status = 'Cancelled' 
            messages.success(request, 'Product has been cancelled successfully.')
        
        order_item.save()
       
    
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
        inv_label = order_item.invoice_number or f"ORD-{order_item.order.order_number}-{order_item.id}"
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="invoice_{inv_label}.pdf"'
        return response
    except Exception as e:
        messages.error(request, "Error generating invoice. Please try again.")
        return redirect('order_detail', order_id=order_item.order.id)
    
    
    
    
@login_required
@csrf_exempt
def create_razorpay_order(request):
    """Create a Razorpay order and return order details to frontend"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            address_id = data.get('address_id')
            
            cart = Cart.objects.filter(user=request.user).first()
            if not cart or not cart.items.exists():
                return JsonResponse({'error': 'Cart is empty'}, status=400)
            
            try:
                address = Address.objects.get(id=address_id, user_id=request.user)
            except Address.DoesNotExist:
                return JsonResponse({'error': 'Address not found'}, status=400)
            
            # Validate cart items - check for out of stock and unavailable products
            out_of_stock_items = []
            for item in cart.items.all():
                if item.variant.is_deleted:
                    return JsonResponse({'error': f'{item.variant.product.name} is unavailable'}, status=400)
                if item.variant.quantity == 0:
                    out_of_stock_items.append(f"{item.variant.product.name} (Size: {item.variant.size})")
                elif item.quantity > item.variant.quantity:
                    return JsonResponse({'error': f'Not enough stock for {item.variant.product.name}. Only {item.variant.quantity} available.'}, status=400)
            
            # If there are out of stock items, return error
            if out_of_stock_items:
                if len(out_of_stock_items) == 1:
                    return JsonResponse({'error': f'{out_of_stock_items[0]} is out of stock. Please remove it from your cart.'}, status=400)
                else:
                    items_str = ", ".join(out_of_stock_items)
                    return JsonResponse({'error': f'The following items are out of stock: {items_str}. Please remove them from your cart.'}, status=400)
            
            # Get coupon details from session
            coupon = request.session.get('coupon', {})
            coupon_id = coupon.get('coupon_id')
            discount_amount = Decimal(str(coupon.get('discount_amount', 0) or 0))
            coupon_code = None
            if coupon_id:
                coupon_code = Coupon.objects.get(id=coupon_id)
            
            subtotal = sum(item.price * item.quantity for item in cart.items.all())
            total_amount = cart.total_price - discount_amount if discount_amount > 0 else cart.total_price
            
            # Import razorpay client
            from wallet.utils import razorpay_client
            
            # Create Razorpay order
            razorpay_order_data = {
                'amount': int(total_amount * 100),  # Razorpay expects amount in paise
                'currency': 'INR',
                'payment_capture': 1  # Auto capture
            }
            
            razorpay_order = razorpay_client.order.create(razorpay_order_data)
            
            with transaction.atomic():
                # Create the order
                order = Order.objects.create(
                    user=request.user,
                    order_number=uuid.uuid4().hex[:12].upper(),
                    coupon=coupon_code,
                    discount=discount_amount,
                    payment_method='RP',
                    payment_status=False,
                    subtotal=subtotal,
                    total_amount=total_amount,
                    shipping_address=address,
                    shipping_cost=cart.delivery_charge or 0,
                    razorpay_order_id=razorpay_order['id'],
                )
                
                # Create order items and reduce stock
                for item in cart.items.all():
                    OrderItem.objects.create(
                        order=order,
                        product_variant=item.variant,
                        quantity=item.quantity,
                        price=item.price,
                        item_payment_status='Pending',
                        original_price=item.variant.actual_price,
                    )
                    item.variant.quantity -= item.quantity
                    item.variant.save()
                
                # Handle coupon usage
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
            
            return JsonResponse({
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount': int(total_amount * 100),
                'currency': 'INR',
                'order_id': order.id,
            })
            
        except Exception as e:
            logger.error(f"Error creating Razorpay order: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

@csrf_exempt
def verify_razorpay_payment(request):
    """Verify Razorpay payment signature and update order status"""
    if request.method in ['POST', 'GET']:
        try:
            import razorpay
            from wallet.utils import razorpay_client
            
            # Get data from both POST and GET (Razorpay may use either for callbacks)
            razorpay_order_id = request.POST.get('razorpay_order_id') or request.GET.get('razorpay_order_id')
            razorpay_payment_id = request.POST.get('razorpay_payment_id') or request.GET.get('razorpay_payment_id')
            razorpay_signature = request.POST.get('razorpay_signature') or request.GET.get('razorpay_signature')
            
            # Get order_id from query params (we pass this in callback_url)
            local_order_id = request.GET.get('order_id')
            
            # Check for Razorpay error parameters (sent on failure)
            error_code = request.POST.get('error[code]') or request.GET.get('error[code]')
            error_description = request.POST.get('error[description]') or request.GET.get('error[description]')
            
            # Log incoming data for debugging (using print for console output)
            print(f"=== RAZORPAY VERIFICATION ===")
            print(f"Method: {request.method}")
            print(f"razorpay_order_id: {razorpay_order_id}")
            print(f"razorpay_payment_id: {razorpay_payment_id}")
            print(f"razorpay_signature: {razorpay_signature}")
            print(f"local_order_id: {local_order_id}")
            print(f"error_code: {error_code}")
            print(f"error_description: {error_description}")
            print(f"POST data: {dict(request.POST)}")
            print(f"GET data: {dict(request.GET)}")
            print(f"Full path: {request.get_full_path()}")
            print(f"=============================")
            
            logger.info(f"Razorpay verification - order_id: {razorpay_order_id}, local_order_id: {local_order_id}, payment_id: {razorpay_payment_id}, error: {error_code}")
            
            # Check if this is an error callback from Razorpay
            if error_code or error_description:
                logger.warning(f"Payment failed with error: {error_code} - {error_description}")
                # Try to find order by razorpay_order_id first, then by local_order_id
                order = None
                if razorpay_order_id:
                    try:
                        order = Order.objects.get(razorpay_order_id=razorpay_order_id)
                    except Order.DoesNotExist:
                        pass
                if not order and local_order_id:
                    try:
                        order = Order.objects.get(id=local_order_id)
                    except Order.DoesNotExist:
                        pass
                
                if order:
                    order.items.update(status='Payment_Failed', item_payment_status='Failed')
                    return redirect('order_failure', order_id=order.id)
                return redirect('my_orders')
            
            # Check if this is a failed payment callback (missing payment_id or signature)
            if not razorpay_payment_id or not razorpay_signature:
                logger.warning(f"Payment failed or cancelled - missing payment_id or signature for order: {razorpay_order_id}")
                # Try to find order by razorpay_order_id first, then by local_order_id
                order = None
                if razorpay_order_id:
                    try:
                        order = Order.objects.get(razorpay_order_id=razorpay_order_id)
                    except Order.DoesNotExist:
                        pass
                if not order and local_order_id:
                    try:
                        order = Order.objects.get(id=local_order_id)
                    except Order.DoesNotExist:
                        pass
                
                if order:
                    order.items.update(status='Payment_Failed', item_payment_status='Failed')
                    return redirect('order_failure', order_id=order.id)
                return redirect('my_orders')
            
            # Find the order by razorpay_order_id
            order = get_object_or_404(Order, razorpay_order_id=razorpay_order_id)
            
            # Verify payment signature
            params = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            
            try:
                razorpay_client.utility.verify_payment_signature(params)
                logger.info(f"Signature verified successfully for order {order.order_number}")
            except razorpay.errors.SignatureVerificationError as sig_error:
                logger.error(f"Signature verification failed: {sig_error}")
                order.items.update(status='Payment_Failed', item_payment_status='Failed')
                return redirect('order_failure', order_id=order.id)
            
            # Payment verified successfully
            with transaction.atomic():
                order.payment_status = True
                order.razorpay_payment_id = razorpay_payment_id
                order.razorpay_signature = razorpay_signature
                order.save()
                
                order.items.update(status='Processing', item_payment_status='Paid')
            
            logger.info(f"Order {order.order_number} payment verified and updated successfully")
            
            # Redirect to success page
            return redirect('order_success', order_id=order.id)
            
        except Exception as e:
            logger.error(f"Error verifying Razorpay payment: {e}")
            # Try to get order_id from POST or GET data
            razorpay_order_id = request.POST.get('razorpay_order_id') or request.GET.get('razorpay_order_id')
            try:
                if razorpay_order_id:
                    order = Order.objects.get(razorpay_order_id=razorpay_order_id)
                    return redirect('order_failure', order_id=order.id)
                else:
                    return redirect('my_orders')
            except Order.DoesNotExist:
                return redirect('my_orders')
    
    return redirect('checkout')