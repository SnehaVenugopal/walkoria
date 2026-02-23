from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.contrib.auth import update_session_auth_hash
from .forms import ProfileUpdateForm, ChangePasswordForm, AddressForm
from .models import Wishlist, Address
from product.models import ProductVariant
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
# from django.db.models import Prefetch
# from django.db import transaction
from django.contrib import messages
# from django.http import JsonResponse, HttpResponse
# from django.views.decorators.csrf import csrf_exempt
# from django.urls import reverse
import cloudinary.uploader
from decimal import Decimal
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import uuid, time
from django.conf import settings
# from orders.models import Order, OrderItem, ReturnRequest
from cart.models import Cart
from userpanel.models import Address
from homepage.views import get_best_offer
# from .invoice_utils import generate_invoice_pdf


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def user_profile(request):
    # Split name into first_name and last_name for display
    if request.user.name:
        name_parts = request.user.name.split(' ', 1)
        request.user.first_name = name_parts[0]
        request.user.last_name = name_parts[1] if len(name_parts) > 1 else ''
    
    return render(request, 'profile.html')



@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def update_profile(request):
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            user = form.save(commit=False)
            user.name = f"{form.cleaned_data['first_name']} {form.cleaned_data['last_name']}"

            # Handle profile image upload
            if 'profile_image' in request.FILES:
                image = request.FILES['profile_image']
                cloudinary_response = cloudinary.uploader.upload(
                    image,
                    folder=f"user_profiles/{user.id}",
                    public_id=f"profile_{user.id}",
                    overwrite=True,
                    format="webp",
                    quality=85
                )
                user.profile_image = cloudinary_response['secure_url']

            user.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        initial_data = {}
        if request.user.name:
            name_parts = request.user.name.split(' ', 1)
            initial_data['first_name'] = name_parts[0]
            initial_data['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
        form = ProfileUpdateForm(instance=request.user, initial=initial_data)

    return render(request, 'update_profile.html', {'form': form})





@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def change_password(request):
    if request.method == 'POST':
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            user = request.user
            user.password = make_password(form.cleaned_data['new_password'])
            user.save()
            
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            
            messages.success(request, 'Your password has been successfully changed.')
            return redirect('profile')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, error)
    else:
        form = ChangePasswordForm(request.user)
    
    return render(request, 'change_password.html', {'form': form})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def manage_address(request):
    addresses = Address.objects.filter(user_id=request.user, is_deleted=False).order_by('-default_address', '-created_at')
    return render(request, 'manage_address.html', {'addresses': addresses})



@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_address(request):
    # Check address count before processing the form
    address_count = Address.objects.filter(user_id=request.user, is_deleted=False).count()
    
    if address_count >= 4:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'You can only have a maximum of 4 addresses. Please delete an existing address to add a new one.'
            }, status=400)
        
        messages.error(request, 'You can only have a maximum of 4 addresses. Please delete an existing address to add a new one.')
        return redirect('manage_address')

    if request.method == 'POST':
        # IMPORTANT: Pass user parameter to the form
        form = AddressForm(request.POST, user=request.user)
        if form.is_valid():
            address = form.save(commit=False)
            address.user_id = request.user
            
            # If this is set as default, remove default from other addresses
            if address.default_address:
                Address.objects.filter(user_id=request.user).update(default_address=False)
            
            address.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Address added successfully!',
                    'address_id': address.id,
                    'address_name': address.full_name,
                    'is_default': address.default_address
                })
            
            messages.success(request, 'Address added successfully!')
            
            # Check if redirecting from checkout
            next_url = request.POST.get('next')
            if next_url and next_url == 'checkout':
                return redirect('checkout')
            return redirect('manage_address')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                errors = {}
                for field, field_errors in form.errors.items():
                    errors[field] = field_errors[0]  # Get first error for each field
                
                return JsonResponse({
                    'success': False,
                    'message': 'Please correct the errors below.',
                    'errors': errors
                })
            
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        # Pass user parameter when creating empty form too
        form = AddressForm(user=request.user)
    
    context = {
        'form': form,
        'address_count': address_count,
        'max_addresses': 4  # Pass to template to show user their limit
    }
    return render(request, 'add_address.html', context)


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user_id=request.user, is_deleted=False)
    
    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            updated_address = form.save(commit=False)
            
            # If this is set as default, remove default from other addresses
            if updated_address.default_address and not address.default_address:
                Address.objects.filter(user_id=request.user).update(default_address=False)
            
            updated_address.save()
            messages.success(request, 'Address updated successfully!')
            return redirect('manage_address')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
    else:
        form = AddressForm(instance=address)
    
    return render(request, 'edit_address.html', {'form': form, 'address': address})


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def delete_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user_id=request.user, is_deleted=False)
    address.is_deleted = True
    address.save()
    messages.success(request, 'Address deleted successfully!')
    return redirect('manage_address')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def set_default_address(request, address_id):
    address = get_object_or_404(Address, id=address_id, user_id=request.user, is_deleted=False)
    
    # Remove default from all other addresses
    Address.objects.filter(user_id=request.user).update(default_address=False)
    
    # Set this address as default
    address.default_address = True
    address.save()
    
    messages.success(request, 'Default address updated successfully!')
    return redirect('manage_address')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def wishlist(request):
    wishlist_items = list(
        Wishlist.objects.filter(
            user=request.user
        ).select_related(
            'variant__product', 'variant__product__brand', 'variant__product__category'
        ).prefetch_related(
            'variant__images',
        ).order_by('-added_at')
    )

    # Annotate each wishlist item with offer data
    for item in wishlist_items:
        product = item.variant.product
        offer_pct, _ = get_best_offer(product)
        item.offer_percentage = offer_pct
        if offer_pct and offer_pct > 0:
            from decimal import Decimal
            discount = item.variant.sale_price * Decimal(str(offer_pct)) / 100
            item.offer_price = round(item.variant.sale_price - discount, 2)
        else:
            item.offer_price = None

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(wishlist_items, 6)
    try:
        wishlist_items = paginator.page(page)
    except PageNotAnInteger:
        wishlist_items = paginator.page(1)
    except EmptyPage:
        wishlist_items = paginator.page(paginator.num_pages)

    return render(request, 'wishlist.html', {'wishlist_items': wishlist_items})


@login_required
def toggle_wishlist(request, product_id, product_size):
    try:
        existing_wishlist = Wishlist.objects.filter(
            user=request.user,
            variant__product_id=product_id,
            variant__size=product_size
        ).first()
        
        if existing_wishlist:
            existing_wishlist.delete()
            return JsonResponse({"success": True, "message": "Product removed from wishlist."})

        variants = ProductVariant.objects.filter(
            product_id=product_id, 
            size=product_size, 
            is_deleted=False
        )
        
        if not variants.exists():
            return JsonResponse({"success": False, "message": "Product variant not found."}, status=404)
            
        if variants.count() == 1:
            variant = variants.first()
        else:
            color = request.POST.get('color')
            if not color:
                return JsonResponse({"success": False, "message": "Please select a color before adding to wishlist."}, status=400)
            
            variant = variants.filter(color=color).first()
            if not variant:
                return JsonResponse({"success": False, "message": "Product variant not found with specified color."}, status=404)

        Wishlist.objects.create(user=request.user, variant=variant)
        return JsonResponse({"success": True, "message": "Product added to wishlist."})
        
    except Exception as e:
        return JsonResponse({"success": False, "message": "An error occurred while processing your request."}, status=500)


@login_required
def is_wishlisted(request, product_id):
    size = request.GET.get('size')
    color = request.GET.get('color')
    
    # Build the query for specific variant
    query = Wishlist.objects.filter(
        user=request.user, 
        variant__product_id=product_id
    )
    
    # Filter by size and color if provided
    if size:
        query = query.filter(variant__size=size)
    if color:
        query = query.filter(variant__color=color)
    
    is_in_wishlist = query.exists()
    return JsonResponse({"is_wishlisted": is_in_wishlist})


@login_required
def get_variant_id(request, product_id, product_size):
    """Get the variant ID for a product and size combination"""
    try:
        variant = ProductVariant.objects.filter(
            product_id=product_id,
            size=product_size,
            is_deleted=False
        ).first()
        
        if variant:
            return JsonResponse({
                "success": True, 
                "variant_id": variant.id,
                "stock": variant.quantity
            })
        else:
            return JsonResponse({
                "success": False, 
                "message": "Variant not found"
            }, status=404)
    except Exception as e:
        return JsonResponse({
            "success": False, 
            "message": str(e)
        }, status=500)


# Placeholder views for future implementation
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def wallet(request):
    return render(request, 'wallet.html')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def refer_earn(request):
    return render(request, 'refer_earn.html')


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def cancel_profile_update(request):
    messages.info(request, 'Profile update cancelled.')
    return redirect('profile')
