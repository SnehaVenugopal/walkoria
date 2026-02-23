from django.shortcuts import render, get_object_or_404
from django.views.decorators.cache import cache_control
from django.template.loader import render_to_string
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Min, Max, Q, Avg, Count
from django.core.serializers.json import DjangoJSONEncoder
import json
from django.db.models import Prefetch
from django.utils import timezone
from product.models import Product, ProductVariant, ProductImage
from category.models import Category
from brand.models import Brand
from reviews.models import ProductReview
from wallet.models import Offer



# Create your views here.

def custom_404(request, exception):
    """Custom 404 error page"""
    return render(request, '404.html', status=404)


def get_best_offer(product):
    """Get the best offer percentage and type for a product (product or category offer)."""
    now = timezone.now()
    
    # Check product-specific offers
    product_offer = Offer.objects.filter(
        product=product,
        offer_type='Product',
        start_date__lte=now,
        end_date__gte=now,
        is_active=True
    ).order_by('-discount_percentage').first()
    
    # Check category offers
    category_offer = Offer.objects.filter(
        category=product.category,
        offer_type='Category',
        start_date__lte=now,
        end_date__gte=now,
        is_active=True
    ).order_by('-discount_percentage').first()
    
    product_discount = product_offer.discount_percentage if product_offer else 0
    category_discount = category_offer.discount_percentage if category_offer else 0
    
    if product_discount >= category_discount and product_discount > 0:
        return product_discount, 'Product Offer'
    elif category_discount > 0:
        return category_discount, 'Category Offer'
    return 0, None


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def home(request):
    latest_products = Product.objects.filter(is_deleted=False).order_by('-created_at')[:4]
    featured_products = Product.objects.filter(is_deleted=False, variants__sale_price__isnull=False).distinct()[:4]
    trending_products = Product.objects.filter(is_deleted=False).order_by('-total_quantity')[:4]
   
    
    # get review, offer percentage, and offer price
    for product_list in [latest_products, featured_products, trending_products]:
        for product in product_list:
            product.avg_rating = ProductReview.objects.filter(product=product).aggregate(Avg('rating'))['rating__avg'] or 0
            product.review_count = ProductReview.objects.filter(product=product).count()
            product.offer_percentage, product.offer_type = get_best_offer(product)
            # Calculate offer price from sale_price
            variant = product.variants.first()
            if variant and product.offer_percentage > 0:
                discount = (variant.sale_price * product.offer_percentage) / 100
                product.offer_price = round(variant.sale_price - discount, 2)
            else:
                product.offer_price = None
    data = {
        'latest_products': latest_products,
        'featured_products': featured_products,
        'trending_products': trending_products,
    }
    
    return render(request, 'home_page.html', data)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def product_detail(request, product_id):
    product = get_object_or_404(
        Product.objects
        .select_related('brand', 'category')
        .prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.filter(is_deleted=False)),
            Prefetch('images', queryset=ProductImage.objects.filter(is_deleted=False))
        )
        .filter(is_deleted=False),
        id=product_id
    )

    related_products_qs = Product.objects.filter(is_deleted=False).exclude(id=product.id)[:4]
    related_products = list(related_products_qs)
    for rp in related_products:
        rp.offer_percentage, rp.offer_type = get_best_offer(rp)
        rv = rp.variants.filter(is_deleted=False).first()
        if rv and rp.offer_percentage > 0:
            discount = (rv.sale_price * rp.offer_percentage) / 100
            rp.offer_price = round(rv.sale_price - discount, 2)
        else:
            rp.offer_price = None
    variants = product.variants.filter(is_deleted=False)

    # Get offer info
    offer_percentage, offer_type = get_best_offer(product)

    available_variants = []
    for variant in variants:
        variant_images = [img.image for img in variant.images.filter(is_deleted=False)]
        if not variant_images:  # If no variant images, use product images
            variant_images = [img.image for img in product.images.filter(is_deleted=False)]
        
        # Calculate offer price for each variant
        if offer_percentage > 0:
            discount = (variant.sale_price * offer_percentage) / 100
            variant_offer_price = str(round(variant.sale_price - discount, 2))
        else:
            variant_offer_price = None
            
        available_variants.append({
            'id': variant.id,
            'size': variant.size,
            'color': variant.color,
            'sale_price': str(variant.sale_price),
            'actual_price': str(variant.actual_price),
            'offer_price': variant_offer_price,
            'quantity': variant.quantity,
            'images': variant_images
        })
    

    # get review
    reviews = ProductReview.objects.filter(product=product).order_by('-created_at')
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    review_count = reviews.count()
    for rp in related_products:
        rp_reviews = ProductReview.objects.filter(product=rp)
        rp.avg_rating = rp_reviews.aggregate(Avg('rating'))['rating__avg'] or 0
        rp.review_count = rp_reviews.count()
    
    data = {
        'product': product,
        'related_products': related_products,
        'available_variants': json.dumps(available_variants, cls=DjangoJSONEncoder),
        'reviews': reviews,
        'avg_rating': avg_rating,
        'review_count': review_count,
        'offer_percentage': offer_percentage,
        'offer_type': offer_type,
    }
    
    return render(request, 'product_detail.html', data)


@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def get_variant_details(request):
    product_id = request.GET.get('product_id')
    size = request.GET.get('size')
    color = request.GET.get('color')
    
    try:
        variant = ProductVariant.objects.get(product_id=product_id, size=size, color=color)
        data = {
            'id': variant.id,
            'sale_price': str(variant.sale_price),
            'actual_price': str(variant.actual_price),
            'quantity': variant.quantity,
            'found': True,
        }
    except ProductVariant.DoesNotExist:
        data = {'found': False}
    
    return JsonResponse(data)



@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def product_listing(request):
    categories = Category.objects.filter(is_deleted=False, is_listed=True)
    brands = Brand.objects.filter(is_deleted=False, is_listed=True)
    price_range = Product.objects.filter(is_deleted=False).aggregate(
        min_price=Min('variants__sale_price', filter=Q(variants__is_deleted=False)),
        max_price=Max('variants__sale_price', filter=Q(variants__is_deleted=False))
    )
    # 🔹 Changed: prefetch only non-deleted variants
    all_products = Product.objects.filter(is_deleted=False) \
        .prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.filter(is_deleted=False)),
            'images'
        ).order_by('-created_at')
    
    # get review + offer info
    for product in all_products:
        product.avg_rating = ProductReview.objects.filter(product=product).aggregate(Avg('rating'))['rating__avg'] or 0
        product.review_count = ProductReview.objects.filter(product=product).count()
        product.offer_percentage, product.offer_type = get_best_offer(product)
        rv = product.variants.filter(is_deleted=False).first()
        if rv and product.offer_percentage > 0:
            discount = (rv.sale_price * product.offer_percentage) / 100
            product.offer_price = round(rv.sale_price - discount, 2)
        else:
            product.offer_price = None
    
    # Pagination
    paginator = Paginator(all_products, 12)
    page_number = request.GET.get('page', 1)
    products = paginator.get_page(page_number)

    data = {
        'categories': categories,
        'brands': brands,
        'min_price': price_range['min_price'],
        'max_price': price_range['max_price'],
        'products': products,
    }
    
    return render(request, 'product_listing.html', data)


def filter_products(request):
    search_query = request.GET.get('search', '').strip()
    sort_by = request.GET.get('sort', 'newest')
    category_ids = request.GET.get('categories', '').split(',')
    brand_ids = request.GET.get('brands', '').split(',')
    ratings = request.GET.get('ratings', '').split(',')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    page = request.GET.get('page', 1)
   # 🔹 Changed: prefetch only non-deleted variants
    products = Product.objects.filter(is_deleted=False).prefetch_related(
        Prefetch('variants', queryset=ProductVariant.objects.filter(is_deleted=False)),
        'images',
        'reviews'
    )

    if search_query:
        products = products.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(brand__name__icontains=search_query) |
            Q(category__name__icontains=search_query)
        )

    if category_ids and category_ids[0]:
        products = products.filter(category_id__in=category_ids)

    if brand_ids and brand_ids[0]:
        products = products.filter(brand_id__in=brand_ids)

    if ratings and ratings[0]:
        products = products.filter(rating__gte=min(ratings))

    if min_price and max_price:
        products = products.filter(
            variants__sale_price__gte=min_price,
            variants__sale_price__lte=max_price,
            variants__is_deleted=False
        )
    if sort_by == 'newest':
        products = products.order_by('-created_at')
    elif sort_by == 'name_asc':
        products = products.order_by('name')
    elif sort_by == 'name_desc':
        products = products.order_by('-name')
    elif sort_by == 'price_asc':
        products = products.order_by('variants__sale_price')
    elif sort_by == 'price_desc':
        products = products.order_by('-variants__sale_price')
    elif sort_by == 'rating':
        products = products.annotate(avg_rating=Avg('reviews__rating')).order_by('-avg_rating')
    products = products.distinct()

    # get review + offer info
    products = products.annotate(avg_rating=Avg('reviews__rating'), review_count=Count('reviews'))
    products_list = list(products)
    for product in products_list:
        product.offer_percentage, product.offer_type = get_best_offer(product)
        rv = product.variants.filter(is_deleted=False).first()
        if rv and product.offer_percentage > 0:
            discount = (rv.sale_price * product.offer_percentage) / 100
            product.offer_price = round(rv.sale_price - discount, 2)
        else:
            product.offer_price = None

    # Pagination
    paginator = Paginator(products_list, 12)
    page_obj = paginator.get_page(page)
    html = render_to_string('product_grid.html', {'products': page_obj}, request=request)

    return JsonResponse({
        'success': True,
        'html': html,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
    })
