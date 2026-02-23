from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.http import JsonResponse
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.contrib import messages
from django.utils import timezone
from decimal import Decimal
import json
from .models import Cart, CartItem
from .forms import AddToCartForm, UpdateCartItemForm, CartValidationForm
from product.models import Product, ProductVariant
from userpanel.models import Wishlist
from django.db.models import Prefetch
from coupon.models import Coupon, UserCoupon
from homepage.views import get_best_offer
import logging


logger = logging.getLogger(__name__)


def _annotate_offers(products):
    """Annotate a product queryset/list with offer_percentage and offer_price."""
    result = list(products)
    for product in result:
        product.offer_percentage, product.offer_type = get_best_offer(product)
        variant = product.variants.first()
        if variant and product.offer_percentage > 0:
            discount = (variant.sale_price * product.offer_percentage) / 100
            product.offer_price = round(variant.sale_price - discount, 2)
        else:
            product.offer_price = None
    return result

@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_cart(request):
    cart, _  = Cart.objects.get_or_create(user=request.user)
    cart_items = cart.items.all().select_related(
            'product', 'variant', 'product__category'
        ).prefetch_related(
            Prefetch('product__images'),
            Prefetch('variant__images')
        )
    
    # Calculate totals
    total_actual_price = sum(item.variant.actual_price * item.quantity for item in cart_items)
    total_sale_price = sum(item.variant.sale_price * item.quantity for item in cart_items)
    total_normal_discount = total_actual_price - total_sale_price
    total_offer_discount = sum(item.get_offer_discount() for item in cart_items)
    has_any_offer = total_offer_discount > 0
    
    # Calculate final total after all discounts
    total_after_discounts = total_sale_price - total_offer_discount
    
    # Apply delivery charge
    delivery_charge = 0 if total_after_discounts > 4999 else 99
    final_total = total_after_discounts + delivery_charge
    
    # Update cart
    cart.total_price = final_total
    cart.delivery_charge = delivery_charge
    cart.save()

    # Get coupon if any — and RECALCULATE discount based on current cart total
    coupon = request.session.get('coupon', {})
    coupon_id = coupon.get('coupon_id')
    discount_amount = Decimal('0')
    coupon_code = None

    if coupon and coupon_id:
        try:
            coupon_code = Coupon.objects.get(id=coupon_id, is_deleted=False, active=True)

            # Auto-remove if cart total dropped below min_cart_value
            if final_total < coupon_code.min_cart_value:
                del request.session['coupon']
                request.session.modified = True
                messages.warning(
                    request,
                    f'Coupon "{coupon_code.code}" removed: your cart total is now below '
                    f'the minimum required ₹{coupon_code.min_cart_value}.'
                )
                coupon_code = None
            else:
                # Recalculate discount on the current effective price (strip delivery charge for %)
                effective_price = Decimal(str(final_total - delivery_charge))  # product total only

                if coupon_code.discount_type == 'fixed':
                    new_discount = Decimal(str(coupon_code.discount_value))
                else:
                    new_discount = (effective_price * Decimal(str(coupon_code.discount_value))) / Decimal('100')

                # Safety: never let coupon exceed the payable amount
                max_allowed = effective_price - Decimal('1')
                if new_discount > max_allowed:
                    new_discount = max_allowed

                discount_amount = new_discount.quantize(Decimal('0.01'))

                # Persist updated amount back to session so checkout sees correct value
                request.session['coupon']['discount_amount'] = float(discount_amount)
                request.session.modified = True

        except Coupon.DoesNotExist:
            logger.warning(f"Coupon with ID {coupon_id} not found or inactive.")
            messages.error(request, 'The coupon you applied earlier is no longer available. It has been removed from your cart.')
            del request.session['coupon']
            return redirect('view_cart')

    # Final total after coupon
    total_after_coupon = final_total - discount_amount if discount_amount > 0 else final_total


    # Check if any cart item quantity exceeds available stock or product is blocked
    cart_exceeds_stock = False
    blocked_items = []
    # Add remaining stock info and line totals to each cart item
    for item in cart_items:
        item.remaining_stock = item.variant.quantity - item.quantity
        item.total_sale_price = item.variant.sale_price * item.quantity
        item.total_actual_price = item.variant.actual_price * item.quantity
        item.total_final_price = item.get_final_price()
        item.offer_details = item.get_offer_details()
        item.has_offer = item.offer_details is not None
        
    for item in cart_items:
        # Check if product or category is blocked/unlisted
        if not item.product.is_listed or item.product.is_deleted:
            blocked_items.append(item.product.name)
            continue
        if not item.product.category.is_listed or item.product.category.is_deleted:
            blocked_items.append(f"{item.product.name} (category unavailable)")
            continue
            
        # Check quantity is exceeds
        if item.quantity > item.variant.quantity:
            cart_exceeds_stock = True
            break

    # Remove blocked items from cart
    if blocked_items:
        for item in cart_items:
            if (not item.product.is_listed or item.product.is_deleted or 
                not item.product.category.is_listed or item.product.category.is_deleted):
                item.delete()
        
        messages.warning(request, f'The following items were removed from your cart as they are no longer available: {", ".join(blocked_items)}')
        return redirect('view_cart')

#get total cart items count
    cart_count = cart.items.count()
    data = {
        'cart': cart,
        'cart_items': cart_items,
        'total_actual_price': total_actual_price,
        'total_sale_price': total_sale_price,
        'total_normal_discount': total_normal_discount,
        'total_offer_discount': total_offer_discount,
        'has_any_offer': has_any_offer,
        'delivery_charge': delivery_charge,
        'coupon_code': coupon_code,
        'discount_amount': discount_amount,
        'total_after_coupon': total_after_coupon,
        'latest_products': _annotate_offers(
            Product.objects.filter(is_deleted=False, is_listed=True).order_by('-created_at')[:6]
        ),
        'max_quantity': 5,
        'cart_exceeds_stock': cart_exceeds_stock,
        'cart_count': cart_count,
    }
    return render(request, 'cart.html', data)



@login_required
def update_cart_item(request, item_id):
    if request.method == 'POST' and request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        try:
            cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
            data = json.loads(request.body)
            print('reachedddddddddddd')
            # Use form for validation
            form = UpdateCartItemForm(data, cart_item=cart_item)
            if not form.is_valid():
                return JsonResponse({
                    'success': False,
                    'message': list(form.errors.values())[0][0]
                })
            
            quantity = form.cleaned_data['quantity']
            
            # Check if product/category is still available
            if not cart_item.product.is_listed or cart_item.product.is_deleted:
                cart_item.delete()
                return JsonResponse({
                    'success': False,
                    'message': 'This product is no longer available and has been removed from your cart'
                })
            
            if not cart_item.product.category.is_listed or cart_item.product.category.is_deleted:
                cart_item.delete()
                return JsonResponse({
                    'success': False,
                    'message': 'This product category is no longer available and has been removed from your cart'
                })
            
            # Update quantity
            cart_item.quantity = quantity
            cart_item.save()
            
            # Get cart totals
            cart = cart_item.cart
            cart_items = cart.items.all()
            
            # Calculate totals
            total_actual_price = sum(item.variant.actual_price * item.quantity for item in cart_items)
            total_sale_price = sum(item.variant.sale_price * item.quantity for item in cart_items)
            total_normal_discount = total_actual_price - total_sale_price
            total_offer_discount = sum(item.get_offer_discount() for item in cart_items)
            
            # Calculate final total after all discounts
            total_after_discounts = total_sale_price - total_offer_discount
            
            # Apply delivery charge
            delivery_charge = 0 if total_after_discounts > 4999 else 99
            final_total = total_after_discounts + delivery_charge
            
            # Update cart
            cart.total_price = final_total
            cart.delivery_charge = delivery_charge
            cart.save()

            # Recalculate coupon discount based on the NEW cart total
            coupon_session = request.session.get('coupon', {})
            coupon_id = coupon_session.get('coupon_id')
            discount_amount = Decimal('0')
            if coupon_session and coupon_id:
                try:
                    applied_coupon = Coupon.objects.get(id=coupon_id, is_deleted=False, active=True)
                    if final_total >= applied_coupon.min_cart_value:
                        effective_price = Decimal(str(final_total - delivery_charge))
                        if applied_coupon.discount_type == 'fixed':
                            discount_amount = Decimal(str(applied_coupon.discount_value))
                        else:
                            discount_amount = (effective_price * Decimal(str(applied_coupon.discount_value))) / Decimal('100')
                        max_allowed = effective_price - Decimal('1')
                        if discount_amount > max_allowed:
                            discount_amount = max_allowed
                        discount_amount = discount_amount.quantize(Decimal('0.01'))
                        # Keep session in sync
                        request.session['coupon']['discount_amount'] = float(discount_amount)
                        request.session.modified = True
                    else:
                        # Cart dropped below min — clear coupon
                        del request.session['coupon']
                        request.session.modified = True
                except Coupon.DoesNotExist:
                    pass
            total_after_coupon = final_total - discount_amount if discount_amount > 0 else final_total

            # Get item specific totals
            item_sale_total = cart_item.variant.sale_price * cart_item.quantity
            item_actual_total = cart_item.variant.actual_price * cart_item.quantity
            item_offer_discount = cart_item.get_offer_discount()
            item_final_price = cart_item.get_final_price()
            item_has_offer = item_offer_discount > 0
            
            return JsonResponse({
                'success': True,
                'total_actual_price': float(total_actual_price),
                'total_sale_price': float(total_sale_price),
                'total_normal_discount': float(total_normal_discount),
                'total_offer_discount': float(total_offer_discount),
                'has_any_offer': total_offer_discount > 0,
                'total_after_discounts': float(total_after_discounts),
                'delivery_charge': delivery_charge,
                'total_after_coupon': float(total_after_coupon),
                'coupon_discount_amount': float(discount_amount),
                'item_sale_total': float(item_sale_total),
                'item_actual_total': float(item_actual_total),
                'item_offer_discount': float(item_offer_discount),
                'item_final_price': float(item_final_price),
                'item_has_offer': item_has_offer,
                'items_count': cart.items.count(),
                'is_free_delivery': total_after_discounts > 4999,
                'max_stock': cart_item.variant.quantity,
                'remaining_stock': cart_item.variant.quantity - quantity
            })
            
        except CartItem.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Cart item not found'})
        except (ValueError, json.JSONDecodeError):
            return JsonResponse({'success': False, 'message': 'Invalid data format'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request'})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def remove_from_cart(request, item_id):
    if request.method == 'POST':
        cart_item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
        cart_item.delete()
        
        # Remove coupon if cart becomes empty
        cart = Cart.objects.get(user=request.user)
        if not cart.items.exists():
            coupon_data = request.session.get('coupon')
            if coupon_data:
                del request.session['coupon']
                request.session.modified = True
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # Recalculate totals
            cart.refresh_from_db()
            cart_items = cart.items.all()
            
            total_actual_price = sum(item.variant.actual_price * item.quantity for item in cart_items)
            total_sale_price = sum(item.variant.sale_price * item.quantity for item in cart_items)
            total_normal_discount = total_actual_price - total_sale_price
            total_offer_discount = sum(item.get_offer_discount() for item in cart_items)
            
            total_after_discounts = total_sale_price - total_offer_discount
            
            delivery_charge = 0 if total_after_discounts > 4999 else 99
            final_total = total_after_discounts + delivery_charge
            
            cart.total_price = final_total
            cart.delivery_charge = delivery_charge
            cart.save()

            # Recalculate coupon discount based on the NEW cart total
            coupon_session = request.session.get('coupon', {})
            coupon_id_r = coupon_session.get('coupon_id')
            discount_amount = Decimal('0')
            if coupon_session and coupon_id_r:
                try:
                    applied_coupon = Coupon.objects.get(id=coupon_id_r, is_deleted=False, active=True)
                    if final_total >= applied_coupon.min_cart_value:
                        effective_price = Decimal(str(final_total - delivery_charge))
                        if applied_coupon.discount_type == 'fixed':
                            discount_amount = Decimal(str(applied_coupon.discount_value))
                        else:
                            discount_amount = (effective_price * Decimal(str(applied_coupon.discount_value))) / Decimal('100')
                        max_allowed = effective_price - Decimal('1')
                        if discount_amount > max_allowed:
                            discount_amount = max_allowed
                        discount_amount = discount_amount.quantize(Decimal('0.01'))
                        request.session['coupon']['discount_amount'] = float(discount_amount)
                        request.session.modified = True
                    else:
                        del request.session['coupon']
                        request.session.modified = True
                except Coupon.DoesNotExist:
                    pass
            total_after_coupon = final_total - discount_amount if discount_amount > 0 else final_total

            return JsonResponse({
                'success': True,
                'cart_total': float(cart.total_price),
                'items_count': cart.items.count(),
                'total_actual_price': float(total_actual_price),
                'total_sale_price': float(total_sale_price),
                'total_normal_discount': float(total_normal_discount),
                'total_offer_discount': float(total_offer_discount),
                'has_any_offer': total_offer_discount > 0,
                'total_after_discounts': float(total_after_discounts),
                'delivery_charge': delivery_charge,
                'total_after_coupon': float(total_after_coupon),
                'coupon_discount_amount': float(discount_amount),
                'is_free_delivery': total_after_discounts > 4999,
            })
    
    return redirect('view_cart')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_to_cart(request, product_id):
    if request.method == 'POST':
        product = get_object_or_404(Product, id=product_id)
        # Check if product and category are available
        if not product.is_listed or product.is_deleted:
            messages.error(request, 'This product is not available')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Product not available'})
            return redirect('product_detail', product_id=product_id)
        
        if not product.category.is_listed or product.category.is_deleted:
            messages.error(request, 'This product category is not available')
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': 'Product category not available'})
            return redirect('product_detail', product_id=product_id)
        
        variant_id = request.POST.get('variant')
        quantity = int(request.POST.get('quantity', 1))
        
        # Use form for validation
        form_data = {
            'product_id': product_id,
            'variant_id': variant_id,
            'quantity': quantity
        }
        form = AddToCartForm(form_data)
        
        if not form.is_valid():
            error_message = list(form.errors.values())[0][0]
            messages.error(request, error_message)
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': error_message})
            return redirect('product_detail', product_id=product_id)
        
        cart, created = Cart.objects.get_or_create(user=request.user)
        variant = get_object_or_404(ProductVariant, id=variant_id)
        
        try:
            # Check if variant exists and has stock
            if variant.quantity < 1:
                messages.error(request, 'This product is out of stock')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': 'Out of stock'})
                return redirect('product_detail', product_id=product_id)
            
            cart_item, created = CartItem.objects.get_or_create(
                cart=cart,
                product=product,
                variant=variant,
                defaults={
                    'quantity': 0,
                    'price': variant.sale_price,
                    'discount': 0
                }
            )
            
            # Check if adding quantity exceeds stock
            new_quantity = cart_item.quantity + quantity
            if new_quantity > variant.quantity:
                messages.error(request, f'Only {variant.quantity} items available in stock')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': f'Only {variant.quantity} items available in stock'})
                return redirect('product_detail', product_id=product_id)
            
            # Check if adding quantity exceeds maximum limit
            if new_quantity > 5:
                messages.error(request, 'Maximum quantity limit is 5')
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'message': 'Maximum quantity limit is 5'})
                return redirect('product_detail', product_id=product_id)
            
            cart_item.quantity = new_quantity
            cart_item.save()
            
            # try:
            #     wishlist_item = Wishlist.objects.get(user=request.user, product=product)
            #     wishlist_item.delete()
            # except Wishlist.DoesNotExist:
            #     pass
            
            messages.success(request, 'Product added to cart successfully')
            
        except ValidationError as e:
            messages.error(request, str(e))
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Product added to cart successfully',
                'cart_total': float(cart.total_price),
                'cart_count': cart.items.count()
            })
    
    return redirect('view_cart')

@login_required
def available_coupons(request):
    try:
        if request.method == 'GET':
            now = timezone.now()
            coupons = Coupon.objects.filter(
                active=True, 
                is_deleted=False,
                start_date__lte=now,
                end_date__gte=now
            )
            coupon_list = []
            for coupon in coupons:
                # Check if user has already used this coupon
                user_usage = UserCoupon.objects.filter(user=request.user, coupon=coupon).count()
                if user_usage < coupon.max_usage_per_user:
                    # Check if total usage limit not reached
                    total_usage = UserCoupon.objects.filter(coupon=coupon).count()
                    if total_usage < coupon.max_usage:
                        coupon_list.append({
                            'code': coupon.code,
                            'description': coupon.description,
                            'discount_type': coupon.discount_type,
                            'discount_value': coupon.discount_value,
                            'min_cart_value': float(coupon.min_cart_value) if coupon.min_cart_value else None,
                            'max_discount': float(coupon.max_discount) if coupon.max_discount else None,
                        })
            return JsonResponse({'coupons': coupon_list})
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    except Exception as e:
        logger.error(f"Error in available_coupons: {e}")
        return JsonResponse({'success': False, 'message': 'An unexpected error occurred'})




@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def apply_coupon(request, coupon_code):
    if request.method == 'POST':
        try:
            coupon = Coupon.objects.get(code=coupon_code)
            cart = Cart.objects.get(user=request.user)
            
            if UserCoupon.objects.filter(user=request.user, coupon=coupon).exists():
                return JsonResponse({'success': False, 'message': 'You have already used this coupon'})
            if UserCoupon.objects.filter(coupon=coupon).count() >= coupon.max_usage:
                return JsonResponse({'success': False, 'message': 'Coupon usage limit reached'})
            if coupon.end_date < timezone.now():
                return JsonResponse({'success': False, 'message': 'Coupon has expired'})
            if not coupon.active:
                return JsonResponse({'success': False, 'message': 'Coupon is inactive'})
            if cart.total_price < coupon.min_cart_value:
                return JsonResponse({'success': False, 'message': f'Minimum cart value of ₹{coupon.min_cart_value} required to apply this coupon.'})
            
            if cart.total_price < 5000:
                effective_price = cart.total_price - 99
            else:
                effective_price = cart.total_price
            if coupon.discount_type == 'fixed':
                discount = float(coupon.discount_value)
            else:
                discount = float(effective_price * coupon.discount_value // 100)
                if coupon.max_discount:
                    discount = max(discount, float(coupon.max_discount))
            
            if discount > effective_price - 1:
                return JsonResponse({'success': False, 'message': 'Coupon discount exceeds cart total'})
            request.session['coupon'] = {
                'coupon_id': coupon.id,
                'discount_amount': discount,
            }
            return JsonResponse({
                'success': True,
                'message': 'Coupon applied successfully!',
                'discount_amount': str(discount),
                'new_total': cart.total_price - Decimal(discount),
                'coupon_code': coupon.code
            })
        
        except ObjectDoesNotExist:
            logger.error(f"Invalid coupon code: {coupon_code}")
            return JsonResponse({'success': False, 'message': 'Invalid coupon, please enter a valid coupon code'})
        except Exception as e:
            logger.error(f"Error in apply_coupon: {e}")
            return JsonResponse({'success': False, 'message': "An unexpected error occurred"})
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def remove_coupon(request):
    if request.method == 'POST':
        try:
            cart = Cart.objects.get(user=request.user)
            coupon_data = request.session.get('coupon')
            
            if coupon_data:
                del request.session['coupon']
                request.session.modified = True
                
                return JsonResponse({'success': True, 'message': 'Coupon removed successfully', 'new_total': float(cart.total_price)})
            else:
                return JsonResponse({'success': False, 'message': 'No coupon applied to remove'})
        
        except Cart.DoesNotExist:
            logger.error(f"Cart not found for user: {request.user.id}")
            return JsonResponse({'success': False, 'message': 'Cart not found'})
        except Exception as e:
            logger.error(f"Error in remove_coupon: {e}")
            return JsonResponse({'success': False, 'message': 'An error occurred while removing the coupon'})
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)





