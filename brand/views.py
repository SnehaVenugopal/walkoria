from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.views.decorators.cache import cache_control
import json
from .models import Brand
from utils.decorators import admin_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger


# Create your views here.

@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def brand_list(request):
    # Get search query
    search_query = request.GET.get('search', '')
    
    # Filter brands based on search query and is_deleted=False
    if search_query:
        brands = Brand.objects.filter(name__icontains=search_query, is_deleted=False)
    else:
        brands = Brand.objects.filter(is_deleted=False)
    
    # Order by created_at in descending order (latest first)
    brands = brands.order_by('-created_at')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(brands, 8)  # 8 items per page to match your other views
    
    try:
        brands_page = paginator.page(page)
    except PageNotAnInteger:
        brands_page = paginator.page(1)
    except EmptyPage:
        brands_page = paginator.page(paginator.num_pages)
    
    # Get user name for display
    name = request.user.name.title() if hasattr(request.user, 'name') and request.user.name else request.user.name.title() if request.user.name else request.user.email
    
    context = {
        'brands': brands_page,
        'name': name,
        'search_query': search_query,
        'page_obj': brands_page,  # For pagination template
        'is_paginated': paginator.num_pages > 1,
        'total_brands': paginator.count
    }
    
    return render(request, 'brand.html', context)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_brand(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            is_listed = data.get('is_listed', True)

            if Brand.objects.filter(name__iexact=name, is_deleted=False).exists():
                raise ValidationError("A brand with this exact name already exists.")

            brand = Brand(name=name, is_listed=is_listed)
            brand.full_clean()
            brand.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Brand added successfully',
                'brand': {
                    'id': brand.id,
                    'name': brand.name,
                    'is_listed': brand.is_listed
                }
            })
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': e.messages[0]
            }, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_brand(request, brand_id):
    brand = get_object_or_404(Brand, id=brand_id, is_deleted=False)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '').strip()
            is_listed = data.get('is_listed', True)

            if Brand.objects.filter(name__exact=name, is_deleted=False).exists():
                raise ValidationError("A brand with this exact name already exists.")
            
            brand.name = name
            brand.is_listed = is_listed
            brand.full_clean()
            brand.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Brand updated successfully',
                'brand': {
                    'id': brand.id,
                    'name': brand.name,
                    'is_listed': brand.is_listed
                }
            })
        except ValidationError as e:
            return JsonResponse({
                'success': False,
                'message': e.messages[0]
            }, status=400)
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)




@login_required
@admin_required
def delete_brand(request, brand_id):
    if request.method == 'POST':
        try:
            brand = get_object_or_404(Brand, id=brand_id, is_deleted=False)
            brand.soft_delete()
            return JsonResponse({'success': True, 'message': 'Brand deleted successfully'})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def toggle_brand_status(request, brand_id):
    if request.method == 'POST':
        try:
            brand = get_object_or_404(Brand, id=brand_id, is_deleted=False)
            brand.is_listed = not brand.is_listed
            brand.save()
            return JsonResponse({
                'success': True,
                'message': f'Brand {"listed" if brand.is_listed else "unlisted"} successfully',
                'is_listed': brand.is_listed
            })
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)}, status=500)


