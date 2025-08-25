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
from .forms import AddToCartForm, UpdateCartItemForm, CouponForm, CartValidationForm
from product.models import Product, ProductVariant
from userpanel.models import Wishlist
from django.db.models import Prefetch

# try:
#     from coupon.models import Coupon, UserCoupon
#     COUPON_AVAILABLE = True
# except ImportError:
#     COUPON_AVAILABLE = False


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def view_cart(request):
    cart, created = Cart.objects.get_or_create(user=request.user)
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
    
    # Calculate final total after all discounts
    total_after_discounts = total_sale_price - total_offer_discount
    
    # Apply delivery charge
    delivery_charge = 0 if total_after_discounts > 4999 else 99
    final_total = total_after_discounts + delivery_charge
    
    # Update cart
    cart.total_price = final_total
    cart.delivery_charge = delivery_charge
    cart.save()

    # Get coupon if any
    coupon = request.session.get('coupon', {})
    coupon_id = coupon.get('coupon_id')
    discount_amount = Decimal(coupon.get('discount_amount', '0'))
    coupon_code = None
    
    if coupon and COUPON_AVAILABLE:
        try:
            coupon_code = Coupon.objects.get(id=coupon_id, is_deleted=False, active=True)
        except Coupon.DoesNotExist:
            messages.error(request, 'The coupon you applied earlier is no longer available. It has been removed from your cart.')
            del request.session['coupon']
            return redirect('view_cart')

    # Final total after coupon
    total_after_coupon = final_total - discount_amount if discount_amount > 0 else final_total

    # Check if any cart item quantity exceeds available stock or product is blocked
    cart_exceeds_stock = False
    blocked_items = []
    
    for item in cart_items:
        # Check if product or category is blocked/unlisted
        if not item.product.is_listed or item.product.is_deleted:
            blocked_items.append(item.product.name)
            continue
        if not item.product.category.is_listed or item.product.category.is_deleted:
            blocked_items.append(f"{item.product.name} (category unavailable)")
            continue
            
        # Check stock
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

    cart_count = cart.items.count()
    data = {
        'cart': cart,
        'cart_items': cart_items,
        'total_actual_price': total_actual_price,
        'total_normal_discount': total_normal_discount,
        'total_offer_discount': total_offer_discount,
        'delivery_charge': delivery_charge,
        'coupon_code': coupon_code,
        'discount_amount': discount_amount,
        'total_after_coupon': total_after_coupon,
        'latest_products': Product.objects.filter(is_deleted=False, is_listed=True).order_by('-created_at')[:5],
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

            # Get coupon if any
            coupon = request.session.get('coupon', {})
            discount_amount = Decimal(coupon.get('discount_amount', '0'))
            total_after_coupon = final_total - discount_amount if discount_amount > 0 else final_total

            # Get item specific totals
            item_sale_total = cart_item.variant.sale_price * cart_item.quantity
            item_offer_discount = cart_item.get_offer_discount()
            item_final_price = cart_item.get_final_price()
            
            return JsonResponse({
                'success': True,
                'total_actual_price': float(total_actual_price),
                'total_normal_discount': float(total_normal_discount),
                'total_offer_discount': float(total_offer_discount),
                'total_after_discounts': float(total_after_discounts),
                'delivery_charge': delivery_charge,
                'total_after_coupon': float(total_after_coupon),
                'item_sale_total': float(item_sale_total),
                'item_offer_discount': float(item_offer_discount),
                'item_final_price': float(item_final_price),
                'items_count': cart.items.count(),
                'is_free_delivery': total_after_discounts > 4999,
                'max_stock': cart_item.variant.quantity
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
            return JsonResponse({
                'success': True, 
                'cart_total': float(cart.total_price),
                'items_count': cart.items.count()
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
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def available_coupons(request):
    if request.method == 'GET' and COUPON_AVAILABLE:
        try:
            coupons = Coupon.objects.filter(active=True, is_deleted=False)
            coupon_list = [{'code': coupon.code, 'description': coupon.description} for coupon in coupons]
            return JsonResponse({'coupons': coupon_list})
        except:
            return JsonResponse({'coupons': []})
    return JsonResponse({'coupons': []})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def apply_coupon(request, coupon_code):
    if request.method == 'POST' and COUPON_AVAILABLE:
        try:
            # Use form for validation
            form = CouponForm({'coupon_code': coupon_code})
            if not form.is_valid():
                return JsonResponse({'success': False, 'message': 'Invalid coupon code format'})
            
            coupon_code = form.cleaned_data['coupon_code']
            
            try:
                coupon = Coupon.objects.get(code=coupon_code)
            except ObjectDoesNotExist:
                return JsonResponse({'success': False, 'message': 'Invalid coupon, please enter a valid coupon code'})
            
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
                    discount = min(discount, float(coupon.max_discount))
            
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
        
        except Exception as e:
            return JsonResponse({'success': False, 'message': f"An unexpected error occurred: {str(e)}"})
    
    return JsonResponse({'success': False, 'message': 'Coupon system not available'})


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
            return JsonResponse({'success': False, 'message': 'Cart not found'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': f'An error occurred: {str(e)}'})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)


def get_cart_count(request):
    """Helper function to get cart count for navigation"""
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            return cart.items.count()
        except Cart.DoesNotExist:
            return 0
    return 0
