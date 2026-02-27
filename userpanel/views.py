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
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import cache_control
from django.contrib import messages
import cloudinary.uploader
from decimal import Decimal
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import uuid, time, random, json
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from cart.models import Cart
from userpanel.models import Address
from homepage.views import get_best_offer


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
        # ⚠️ Snapshot the ORIGINAL email BEFORE form validation, because
        # Django ModelForm._post_clean() mutates the instance (request.user)
        # in place during is_valid(), so request.user.email is overwritten
        # before we can compare. We read from DB to be 100% safe.
        from users.models import CustomUser
        original_email = CustomUser.objects.get(pk=request.user.pk).email.strip().lower()

        form = ProfileUpdateForm(request.POST, request.FILES,
                                 instance=request.user, user=request.user)
        if form.is_valid():
            new_email = form.cleaned_data.get('email', '').strip().lower()

            # If email is being changed, require OTP verification — do NOT save yet
            if new_email != original_email:
                request.session['pending_profile'] = {
                    'first_name': form.cleaned_data.get('first_name', ''),
                    'last_name':  form.cleaned_data.get('last_name', ''),
                    'new_email':  new_email,
                    'mobile_no':  str(form.cleaned_data.get('mobile_no', '')),
                }
                request.session.modified = True
                # Restore the original email on the in-memory instance so it
                # doesn't accidentally get saved by something else
                request.user.email = original_email
                return JsonResponse({'email_change': True, 'new_email': new_email})

            # No email change → save directly (manually, not via form.save())
            user = request.user
            user.name      = ' '.join(filter(None, [form.cleaned_data['first_name'], form.cleaned_data.get('last_name', '')]))
            user.email     = original_email          # keep original, immune to mutation
            user.mobile_no = form.cleaned_data.get('mobile_no', user.mobile_no)

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
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'redirect': '/userpanel/profile/'})
            return redirect('profile')
        else:
            errors_list = []
            for field, errs in form.errors.items():
                for error in errs:
                    errors_list.append(f"{field.replace('_', ' ').title()}: {error}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': errors_list})
            for msg in errors_list:
                messages.error(request, msg)
    else:
        initial_data = {}
        if request.user.name:
            name_parts = request.user.name.split(' ', 1)
            initial_data['first_name'] = name_parts[0]
            initial_data['last_name']  = name_parts[1] if len(name_parts) > 1 else ''
        form = ProfileUpdateForm(instance=request.user, initial=initial_data,
                                 user=request.user)

    return render(request, 'update_profile.html', {'form': form})


@login_required
def send_email_otp(request):
    """AJAX: generate and email an OTP for new-email verification."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)

    pending = request.session.get('pending_profile')
    if not pending:
        return JsonResponse({'success': False, 'message': 'Session expired. Please try again.'}, status=400)

    new_email = pending.get('new_email', '')
    if not new_email:
        return JsonResponse({'success': False, 'message': 'No new email found in session.'}, status=400)

    # Check email not already taken by another user
    from users.models import CustomUser
    if CustomUser.objects.filter(email=new_email).exclude(pk=request.user.pk).exists():
        return JsonResponse({'success': False, 'message': 'This email is already registered with another account.'}, status=400)

    otp = str(random.randint(100000, 999999))
    request.session['email_change_otp'] = otp
    request.session['email_change_otp_created_at'] = timezone.now().isoformat()
    request.session.modified = True

    print('\n' + '='*50)
    print(f'📧 EMAIL CHANGE OTP: {otp} -> {new_email}')
    print('='*50 + '\n')

    name = request.user.name or 'User'
    subject = 'Walkoria - Verify Your New Email'
    plain_message = f'Hi {name},\n\nYour OTP for email change is: {otp}. It expires in 1 minute.\n\nThank you!'
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
            <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px; padding: 24px; background-color: #f9f9f9;">
                <h2 style="color: #ff429d; text-align: center;">Email Verification</h2>
                <p style="font-size: 16px;">Dear {name.title()},</p>
                <p style="font-size: 16px;">
                    Your OTP to verify your new email address is:<br>
                    <strong style="font-size: 28px; color: #ff429d; letter-spacing: 6px;">{otp}</strong><br>
                    This code will expire in <strong>1 minute</strong>.
                </p>
                <p style="font-size: 14px; color: #888;">If you didn't request this, please ignore this email.</p>
                <p style="font-size: 16px;">Best regards,<br>Walkoria Team</p>
            </div>
        </body>
    </html>
    """
    try:
        send_mail(subject, plain_message, settings.DEFAULT_FROM_EMAIL, [new_email],
                  fail_silently=False, html_message=html_message)
    except Exception as e:
        print(f'Email send error: {e}')
        return JsonResponse({'success': False, 'message': 'Failed to send OTP. Please try again.'}, status=500)

    return JsonResponse({'success': True, 'message': f'OTP sent to {new_email}'})


@login_required
def verify_email_otp(request):
    """AJAX: verify the OTP and apply pending profile changes."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)

    try:
        data = json.loads(request.body)
        user_otp = data.get('otp', '').strip()
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid request body.'}, status=400)

    otp_in_session = request.session.get('email_change_otp')
    created_at = request.session.get('email_change_otp_created_at')
    pending = request.session.get('pending_profile')

    if not otp_in_session or not created_at or not pending:
        return JsonResponse({'success': False, 'message': 'Session expired. Please try again.'}, status=400)

    # Check expiry (1 minute)
    try:
        created_dt = timezone.datetime.fromisoformat(created_at)
    except Exception:
        return JsonResponse({'success': False, 'message': 'Invalid session data.'}, status=400)

    expiry_dt = created_dt + timezone.timedelta(minutes=1)
    if timezone.now() > expiry_dt:
        return JsonResponse({'success': False, 'reason': 'expired', 'message': 'OTP has expired. Please resend a new OTP.'}, status=400)

    if user_otp != otp_in_session:
        return JsonResponse({'success': False, 'message': 'Invalid OTP. Please check and try again.'})

    # OTP is correct – apply profile changes
    user = request.user
    user.email = pending['new_email']
    user.name = ' '.join(filter(None, [pending['first_name'], pending.get('last_name', '')]))
    user.mobile_no = pending.get('mobile_no', user.mobile_no)
    user.save()

    # Clear session keys
    for key in ('email_change_otp', 'email_change_otp_created_at', 'pending_profile'):
        request.session.pop(key, None)

    return JsonResponse({'success': True, 'message': 'Email verified and profile updated successfully!', 'redirect': '/userpanel/profile/'})





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
