from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.exceptions import ValidationError
from django.views.decorators.cache import cache_control
from django.contrib.auth.decorators import login_required
from django.utils import timezone
import json, logging
from utils.decorators import admin_required
from .models import Coupon, UserCoupon


logger = logging.getLogger(__name__)

@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def coupon_list(request):
    first_name = request.user.name.title()
    try:
        coupons = Coupon.objects.filter(is_deleted=False).order_by('-created_at')
    except Exception as e:
        logger.error(f"Error in coupon_list: {e}")
        coupons = []

    data = {
        'first_name': first_name,
        'coupons': coupons,
    }
    return render(request, 'coupon_management.html', data)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_coupon(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code').strip().upper()
            discount_type = data.get('discount_type')
            discount_value = data.get('discount_value') or 0
            min_cart_value = data.get('min_cart_value') or 0
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            max_usage = data.get('max_usage') or 1
            max_usage_per_user = data.get('max_usage_per_user') or 1
            description = data.get('description', '').strip()
            active = data.get('active', True)

            if Coupon.objects.filter(code__exact=code).exists():
                raise ValidationError("A coupon with this code already exists.")
            if not code or not code.isalnum():
                raise ValidationError("Coupon code is required and contains only letters and numbers.")
            if not discount_value or not str(discount_value).isdigit():
                raise ValidationError("Invalid discount value.")

            if discount_type == 'percent' and not (0 < int(discount_value) <= 100):
                raise ValidationError("Discount value must be between 1 and 100 for a percentage discount.")
            elif discount_type == 'fixed' and int(discount_value) < 1:
                raise ValidationError("Discount value must be greater than 0.")

            if int(min_cart_value) <= 0:
                raise ValidationError("Minimum Cart Value is required and must be a positive digit.")
            if int(max_usage) <= 0:
                raise ValidationError("Maximum Usage is required and must be a positive digit.")
            if int(max_usage_per_user) <= 0:
                raise ValidationError("Maximum Usage per user is required and must be a positive digit.")
            if not start_date:
                raise ValidationError("Start date is required.")
            if not end_date:
                raise ValidationError("End date is required.")

            coupon = Coupon(
                code=code,
                discount_type=discount_type,
                discount_value=discount_value,
                min_cart_value=min_cart_value,
                start_date=start_date,
                end_date=end_date,
                max_usage=max_usage,
                max_usage_per_user=max_usage_per_user,
                description=description,
                active=active
            )
            coupon.full_clean()
            coupon.save()

            return JsonResponse({
                'success': True, 'message': 'Coupon added successfully',
                'coupon': {
                    'id': coupon.id,
                    'code': coupon.code,
                    'discount_type': coupon.discount_type,
                    'discount_value': str(coupon.discount_value),
                    'active': coupon.active
                }
            })
        except ValidationError as e:
            logger.error(f"Validation error in add_coupon: {e}")
            return JsonResponse({'success': False, 'message': e.messages[0]}, status=400)
        except Exception as e:
            logger.error(f"Error in add_coupon: {e}")
            return JsonResponse({'success': False, 'message': 'An error occurred while adding the coupon.'}, status=500)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_coupon(request, coupon_id):
    coupon = get_object_or_404(Coupon, id=coupon_id)

    if request.method == 'GET':
        return JsonResponse({
            'success': True,
            'coupon': {
                'id': coupon.id,
                'code': coupon.code,
                'discount_type': coupon.discount_type,
                'discount_value': str(coupon.discount_value),
                'min_cart_value': str(coupon.min_cart_value) if coupon.min_cart_value else None,
                'start_date': coupon.start_date.isoformat() if coupon.start_date else None,
                'end_date': coupon.end_date.isoformat() if coupon.end_date else None,
                'max_usage': coupon.max_usage,
                'max_usage_per_user': coupon.max_usage_per_user,
                'description': coupon.description,
                'active': coupon.active
            }
        })
    elif request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code', '').strip().upper()

            coupon.code = code
            coupon.discount_type = data.get('discount_type')
            coupon.discount_value = data.get('discount_value')
            coupon.min_cart_value = data.get('min_cart_value')
            coupon.start_date = data.get('start_date')
            coupon.end_date = data.get('end_date')
            coupon.max_usage = data.get('max_usage', 1)
            coupon.max_usage_per_user = data.get('max_usage_per_user', 1)
            coupon.description = data.get('description', '').strip()
            active = data.get('active')

            if active is not None:
                coupon.active = active in [True, 'true', 'True', 1, '1']

            if not coupon.discount_value or not str(coupon.discount_value).isdigit():
                raise ValidationError("Invalid discount value.")

            if coupon.discount_type == 'percent' and not (0 < float(coupon.discount_value) <= 100):
                raise ValidationError("Discount value must be between 1 and 100 for a percentage discount.")
            elif coupon.discount_type == 'fixed' and float(coupon.discount_value) < 1:
                raise ValidationError("Discount value must be greater than 0.")

            if float(coupon.min_cart_value) <= 0:
                raise ValidationError("Minimum Cart Value is required and must be a positive digit.")
            if float(coupon.max_usage) <= 0:
                raise ValidationError("Maximum Usage is required and must be a positive digit.")
            if float(coupon.max_usage_per_user) <= 0:
                raise ValidationError("Maximum Usage per user is required and must be a positive digit.")
            if not coupon.end_date:
                raise ValidationError("End date is required.")

            coupon.full_clean()
            coupon.save()
            return JsonResponse({
                'success': True,
                'message': 'Coupon updated successfully',
                'coupon': {
                    'id': coupon.id,
                    'code': coupon.code,
                    'discount_type': coupon.discount_type,
                    'discount_value': str(coupon.discount_value),
                    'active': coupon.active
                }
            })
        except ValidationError as e:
            logger.error(f"Validation error in edit_coupon: {e}")
            return JsonResponse({'success': False, 'message': e.messages[0]}, status=400)
        except Exception as e:
            logger.error(f"Error in edit_coupon: {e}")
            return JsonResponse({'success': False, 'message': 'An error occurred while updating the coupon.'}, status=500)
    else:
        return JsonResponse({'success': False, 'message': 'Invalid request method'}, status=405)
    
    
@login_required
@admin_required
def delete_coupon(request, coupon_id):
    if request.method != 'POST':
        return JsonResponse(
            {'success': False, 'message': 'Invalid request method'},
            status=405
        )

    try:
        coupon = get_object_or_404(Coupon, id=coupon_id)

        # If already deleted
        if coupon.is_deleted:
            return JsonResponse({
                'success': False,
                'message': 'Coupon is already deleted'
            }, status=400)

        # Soft delete (ALWAYS)
        coupon.is_deleted = True
        coupon.active = False
        coupon.deleted_at = timezone.now()
        coupon.save()

        # Check usage (for message only)
        used = UserCoupon.objects.filter(coupon=coupon).exists()

        return JsonResponse({
            'success': True,
            'message': (
                'Coupon deactivated (already used by customers)'
                if used else
                'Coupon deleted successfully'
            )
        })

    except Exception as e:
        logger.error(f"Error in delete_coupon: {e}")
        return JsonResponse(
            {'success': False, 'message': 'An error occurred while deleting the coupon.'},
            status=500
        )


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def toggle_coupon_status(request, coupon_id):
    if request.method == 'POST':
        try:
            coupon = get_object_or_404(Coupon, id=coupon_id)
            coupon.active = not coupon.active
            coupon.save()
            return JsonResponse({
                'success': True,
                'message': f'Coupon {"activated" if coupon.active else "deactivated"} successfully',
                'active': coupon.active
            })
        except Exception as e:
            logger.error(f"Error in toggle_coupon_status: {e}")
            return JsonResponse({'success': False, 'message': 'An error occurred while toggling the coupon status.'}, status=500)

