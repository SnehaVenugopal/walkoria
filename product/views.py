from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Min, Sum, Prefetch
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.views.decorators.cache import cache_control
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import cloudinary, cloudinary.uploader
import re, json
from django.db import transaction, IntegrityError
from .models import Product, ProductVariant, ProductImage
from brand.models import Brand
from category.models import Category
from utils.decorators import admin_required
from django.db.models import Prefetch

# Create your views here.


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def products_view(request):
    name = request.user.name.title()
    products = Product.objects.filter(is_deleted=False).prefetch_related(Prefetch('variants', queryset=ProductVariant.objects.filter(is_deleted=False)),'images')
    variants = ProductVariant.objects.filter(is_deleted=False)
    categories = Category.objects.filter(is_deleted=False)
    search_query = request.GET.get('search', '')
    category_id = request.GET.get('category', '')
    if search_query:
        products = products.filter(Q(name__istartswith=search_query))
    if category_id:
        products = products.filter(category_id=category_id)
    products = products.annotate(min_sale_price=Min('variants__sale_price'))

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(products, 5)
    try:
        products_page = paginator.page(page)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)
    data = {
        'name': name,
        'products': products_page,
        'variants': variants,
        'categories': categories,
        'search_query': search_query,
        'selected_category': category_id
    }
    return render(request, 'admin_product.html', data)


@login_required
@require_POST
def toggle_product_status(request, product_id):
    try:
        with transaction.atomic():
            product = get_object_or_404(Product, id=product_id)
            try:
                data = json.loads(request.body or '{}')
            except Exception:
                data = {}
            # Client sends is_listed True/False
            is_listed = bool(data.get('is_listed', True))

            if is_listed:
                # List -> not deleted
                product.is_deleted = False
                product.deleted_at = None
                product.save(update_fields=['is_deleted','deleted_at','updated_at'])
                message = 'Product listed successfully'
            else:
                # Unlist -> soft delete product + variants, set quantity to 0
                product.is_deleted = True
                product.deleted_at = timezone.now()
                product.save(update_fields=['is_deleted','deleted_at','updated_at'])
                ProductVariant.objects.filter(product=product).update(
                    is_deleted=True,
                    deleted_at=timezone.now(),
                    quantity=0
                )
                message = 'Product unlisted successfully'

            return JsonResponse({'success': True, 'message': message, 'is_listed': is_listed})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@require_POST
def delete_variant(request, id):
    try:
        variant = get_object_or_404(ProductVariant, id=id)
        variant.is_deleted = True
        variant.deleted_at = timezone.now()
        variant.save()
        
        # Check if all variants of the product are deleted
        product = variant.product
        active_variants = product.variants.filter(is_deleted=False).exists()
        if not active_variants:
            product.is_deleted = True
            product.deleted_at = timezone.now()
            product.save()

        return JsonResponse({'success': True, 'message': 'Variant deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)




@transaction.atomic
@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_product(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        description = request.POST.get('description', '').strip()
        variants = json.loads(request.POST.get('variants', '[]'))

        errors = {}

        if Product.objects.filter(name=name).exists():
            errors['name'] = 'Product with this name already exists.'

        # if not name or re.search(r'[^a-zA-Z0-9\s]', name):
        #     errors['name'] = 'Product name should contain only text and numbers.'
        if not name:
            errors['name'] = 'Product name is required.'

        if not category_id:
            errors['category'] = 'Please select a category.'

        if not brand_id:
            errors['brand'] = 'Please select a brand.'

        if len(description) < 20:
            errors['description'] = f'{20 - len(description)} more characters needed.'

        if not variants:
            errors['variants'] = 'At least one variant is required.'

        for i, variant in enumerate(variants):
            variant_name = f"Variant {i+1}"
            if not variant.get('color', '').strip():
                errors[f'color{i+1}'] = 'Color is required.'
            if not variant.get('size'):
                errors[f'size{i+1}'] = 'Size is required.'
            if variant.get('quantity') is None:
                errors[f'quantity{i+1}'] = 'Quantity is required.'
            else:
                try:
                    quantity = int(variant['quantity'])
                    if quantity <= 0 or quantity > 1000:
                        errors[f'quantity{i+1}'] = 'Quantity should be between 1 and 1000.'
                except ValueError:
                    errors[f'quantity{i+1}'] = 'Quantity should be a valid number and cannot be empty.'
            
            if variant.get('actual_price') is None:
                errors[f'actual_price{i+1}'] = 'Actual price is required.'
            else:
                try:
                    actual_price = float(variant['actual_price'])
                    if actual_price <= 0:
                        errors[f'actual_price{i+1}'] = 'Actual price must be a positive number.'
                except ValueError:
                    errors[f'actual_price{i+1}'] = 'Please enter a valid price.'

                try:
                    sale_price = float(variant['sale_price'])
                    if sale_price <= 0:
                        errors[f'sale_price{i+1}'] = 'Sale price must be a positive number.'
                    if sale_price >= float(variant['actual_price']):
                        errors[f'sale_price{i+1}'] = 'Sale price must be less than actual price.'
                except ValueError:
                    errors[f'sale_price{i+1}'] = 'Please enter a valid sale price.'

            variant_images = request.FILES.getlist(f'variant_image{i + 1}[]')
            print('imgggggggggggg', variant_images)
            if len(variant_images) < 3:
                errors[f'variant_image{i+1}'] = 'Please upload at least 3 images for each variant.'

        if errors:
            print('errrrrr', errors)
            return JsonResponse({'success': False, 'errors': errors})

        try:
            with transaction.atomic():
                product = Product(
                    name=name,
                    category_id=category_id,
                    brand_id=brand_id,
                    description=description,
                    total_quantity=0,
                    is_deleted=False
                )
                product.save()

                total_quantity = 0
                for i, variant in enumerate(variants):
                    quantity = int(variant['quantity'])
                    total_quantity += quantity
                    product_variant = ProductVariant(
                        product=product,
                        color=variant['color'].strip(),
                        size=variant['size'],
                        quantity=quantity,
                        actual_price=float(variant['actual_price']),
                        sale_price=float(variant['sale_price']) if variant.get('sale_price') else None
                    )
                    product_variant.save()

                    variant_images = request.FILES.getlist(f'variant_image{i + 1}[]')
                    for index, image in enumerate(variant_images):
                        cloudinary_response = cloudinary.uploader.upload(
                            image,
                            folder=f"product_images/{product.id}/variant_{i + 1}",
                            public_id=f"{product.id:03d}_{i + 1:02d}_{index + 1:03d}",
                            overwrite=True,
                            format="webp",
                            quality=85
                        )
                        cloudinary_url = cloudinary_response['secure_url']
                        ProductImage.objects.create(
                            image=cloudinary_url, 
                            product=product,
                            variant=product_variant
                        )
                product.total_quantity = total_quantity
                product.save()
                
            return JsonResponse({'success': True, 'message': 'Product added successfully!'})
        except IntegrityError as e:
            print('err2222222222', e)
            return JsonResponse({'success': False, 'message': 'A database integrity error occurred. Please try again.'})
        except Exception as e:
            print('err33333333333333333', e)
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

    name = request.user.name.title()
    categories = Category.objects.filter(is_deleted=False, is_listed=True)
    brands = Brand.objects.filter(is_deleted=False, is_listed=True)
    data = {
        'name': name,
        'categories': categories,
        'brands': brands
    }
    return render(request, 'add_product.html', data)


def cancel_add_product(request):
    messages.error(request, 'Cancelled')
    return redirect('product')


@admin_required
@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_product(request, product_id):
    product = get_object_or_404(
    Product.objects.select_related('brand', 'category').prefetch_related(
            Prefetch(
                'variants',
                queryset=ProductVariant.objects.filter(is_deleted=False).prefetch_related(
                    Prefetch('images', queryset=ProductImage.objects.filter(is_deleted=False))
                )
            ),
            Prefetch(
                'images',
                queryset=ProductImage.objects.filter(is_deleted=False, variant__isnull=True)
            )
        ),
        id=product_id
    )
    categories = Category.objects.filter(is_deleted=False, is_listed=True)
    brands = Brand.objects.filter(is_deleted=False, is_listed=True)
    sizes = ProductVariant.STATUS_CHOICES

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        category_id = request.POST.get('category')
        brand_id = request.POST.get('brand')
        description = request.POST.get('description', '').strip()
        variants = json.loads(request.POST.get('variants', '[]'))
        deleted_images = json.loads(request.POST.get('deleted_images', '[]'))

        errors = {}

        if not name or re.search(r'[^a-zA-Z0-9\s]', name):
            errors['name'] = 'Product name should contain only text and numbers.'
        if not name:
            errors['name'] = 'Product name is required.'

        if not category_id:
            errors['category'] = 'Please select a category.'

        if not brand_id:
            errors['brand'] = 'Please select a brand.'

        if len(description) < 20:
            errors['description'] = f'{20 - len(description)} more characters needed.'

        if not variants:
            errors['variants'] = 'At least one variant is required.'

        for i, variant in enumerate(variants):
            if not variant.get('color', '').strip():
                errors[f'color{i+1}'] = 'Color is required.'
            if not variant.get('size'):
                errors[f'size{i+1}'] = 'Size is required.'
            if variant.get('quantity') is None:
                errors[f'quantity{i+1}'] = 'Quantity is required.'
            else:
                try:
                    quantity = int(variant['quantity'])
                    if quantity > 1000:
                        errors[f'quantity{i+1}'] = "Can't add Quantity more than 1000."
                except ValueError:
                    errors[f'quantity{i+1}'] = 'Quantity should be a valid number.'
            
            if variant.get('actual_price') is None:
                errors[f'actual_price{i+1}'] = 'Actual price is required.'
            else:
                try:
                    actual_price = float(variant['actual_price'])
                    if actual_price <= 0:
                        errors[f'actual_price{i+1}'] = 'Actual price must be a positive number.'
                except ValueError:
                    errors[f'actual_price{i+1}'] = 'Please enter a valid price.'

            if variant.get('sale_price'):
                try:
                    sale_price = float(variant['sale_price'])
                    if sale_price <= 0:
                        errors[f'sale_price{i+1}'] = 'Sale price must be a positive number.'
                    if sale_price >= float(variant['actual_price']):
                        errors[f'sale_price{i+1}'] = 'Sale price must be less than actual price.'
                except ValueError:
                    errors[f'sale_price{i+1}'] = 'Please enter a valid sale price.'

        if errors:
            print("fdfgh",errors)
            return JsonResponse({'success': False, 'errors': errors})

        try:
            with transaction.atomic():
                product.name = name
                product.category_id = category_id
                product.brand_id = brand_id
                product.description = description
                product.save()

                # Update or create variants
                existing_variants = list(product.variants.all())
                for i, variant_data in enumerate(variants):
                    if i < len(existing_variants):
                        variant = existing_variants[i]
                        variant.color = variant_data['color']
                        variant.size = variant_data['size']
                        variant.quantity = variant_data['quantity']
                        variant.actual_price = variant_data['actual_price']
                        variant.sale_price = variant_data['sale_price'] or None
                        variant.save()
                    else:
                        ProductVariant.objects.create(
                            product=product,
                            color=variant_data['color'],
                            size=variant_data['size'],
                            quantity=variant_data['quantity'],
                            actual_price=variant_data['actual_price'],
                            sale_price=variant_data['sale_price'] or None
                        )

                # Remove extra variants
                if len(variants) < len(existing_variants):
                    for variant in existing_variants[len(variants):]:
                        variant.delete()
                # Delete images
                for image_id in deleted_images:
                    image = ProductImage.objects.get(id=image_id)
                    print(image.image, 'jjjjjjjjjjjjjj')
                    cloudinary.uploader.destroy(image.image)
                    image.delete()

                # Process new images
                for i, variant_data in enumerate(variants):
                    variant_images = request.FILES.getlist(f'variant_image{i + 1}[]')
                    variant = product.variants.get(color=variant_data['color'], size=variant_data['size'])
                    for index, image in enumerate(variant_images):
                        cloudinary_response = cloudinary.uploader.upload(
                            image,
                            folder=f"product_images/{product.id}/variant_{i + 1}",
                            public_id=f"{product.id:03d}_{i + 1:02d}_{variant.images.count() + index + 1:03d}",
                            overwrite=True,
                            format="webp",
                            quality=85
                        )
                        cloudinary_url = cloudinary_response['secure_url']
                        ProductImage.objects.create(
                            image=cloudinary_url,
                            product=product,
                            variant=variant
                        )

                product.total_quantity = product.variants.aggregate(total=Sum('quantity'))['total'] or 0
                product.save()

            return JsonResponse({'success': True, 'message': 'Product updated successfully!'})
        except Exception as e:
            print('222222222', e)
            return JsonResponse({'success': False, 'message': f'Error: {str(e)}'})

    name = request.user.name.title()
    data = {
        'name': name,
        'product': product,
        'categories': categories,
        'brands': brands,
        'sizes': [size[0] for size in sizes],
    }
    return render(request, 'edit_product.html', data)