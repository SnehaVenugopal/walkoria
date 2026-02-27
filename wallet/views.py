from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import cache_control
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
import random, uuid, time, json, logging
from product.models import Product
from category.models import Category
from django.conf import settings
from utils.decorators import admin_required
from .models import Wallet, WalletTransaction, Offer, WalletTopup
from django.views.decorators.csrf import csrf_exempt


logger = logging.getLogger(__name__)

@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def wallet_view(request):
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
        
        # Search
        search_query = request.GET.get('search', '').strip()
        if search_query:
            transactions = transactions.filter(transaction_id__icontains=search_query)

        # Pagination
        page = request.GET.get('page', 1)
        paginator = Paginator(transactions, 5)
        try:
            transactions = paginator.page(page)
        except PageNotAnInteger:
            transactions = paginator.page(1)
        except EmptyPage:
            transactions = paginator.page(paginator.num_pages)

        data = {
            'wallet': wallet,
            'transactions': transactions,
            'search_query': search_query,
        }
    except Exception as e:
        logger.error(f"Error in wallet_view for user {request.user.id}: {e}")
        messages.error(request, "An error occurred while loading your wallet. Please try again later.")
        data = {
            'wallet': None,
            'transactions': [],
            'search_query': '',
        }
    return render(request, 'wallet.html', data)



@login_required
def add_money(request):
    """Create Razorpay order for adding money to wallet"""
    if request.method == 'POST':
        try:
            from .utils import razorpay_client
            data = json.loads(request.body)
            amount = int(data.get('amount', 0))
            
            if amount < 100:
                return JsonResponse({'error': 'Amount must be at least ₹100'}, status=400)
            if amount > 20000:
                return JsonResponse({'error': 'Amount cannot exceed ₹20,000'}, status=400)
            
            # Create Razorpay order
            razorpay_order = razorpay_client.order.create({
                'amount': amount * 100,  # Razorpay expects paise
                'currency': 'INR',
                'payment_capture': 1
            })
            
            # Store in database (like orders flow)
            WalletTopup.objects.create(
                user=request.user,
                razorpay_order_id=razorpay_order['id'],
                amount=amount,
                status='Pending'
            )
            
            return JsonResponse({
                'razorpay_order_id': razorpay_order['id'],
                'razorpay_key_id': settings.RAZORPAY_KEY_ID,
                'amount': amount * 100,
                'currency': 'INR'
            })
        except Exception as e:
            logger.error(f"Error creating Razorpay order for wallet: {e}")
            return JsonResponse({'error': 'Failed to create payment order'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@csrf_exempt
def verify_wallet_payment(request):
    """Verify Razorpay payment and add money to wallet"""
    if request.method == 'POST':
        try:
            import razorpay
            from .utils import razorpay_client
            from django.db import transaction
            
            # Get data from POST (Razorpay callback sends form data)
            razorpay_order_id = request.POST.get('razorpay_order_id')
            razorpay_payment_id = request.POST.get('razorpay_payment_id')
            razorpay_signature = request.POST.get('razorpay_signature')
            
            # Find the topup by razorpay_order_id from database
            topup = get_object_or_404(WalletTopup, razorpay_order_id=razorpay_order_id)
            
            # Already processed
            if topup.status == 'Completed':
                redirect_url = reverse('wallet')
                return HttpResponse(f'''
                    <html><body>
                    <script>
                        if (window.opener) {{
                            window.opener.location.href = "{redirect_url}";
                            window.close();
                        }} else {{
                            window.location.href = "{redirect_url}";
                        }}
                    </script>
                    <p>Already processed. Redirecting...</p>
                    </body></html>
                ''')
            
            # Verify signature
            params = {
                'razorpay_order_id': razorpay_order_id,
                'razorpay_payment_id': razorpay_payment_id,
                'razorpay_signature': razorpay_signature
            }
            #payment reallycame from razorpay
            try:
                razorpay_client.utility.verify_payment_signature(params)
            except razorpay.errors.SignatureVerificationError:
                topup.status = 'Failed'
                topup.save()
                redirect_url = reverse('wallet')
                return HttpResponse(f'''
                    <html><body>
                    <script>
                        if (window.opener) {{
                            window.opener.location.href = "{redirect_url}";
                            window.close();
                        }} else {{
                            window.location.href = "{redirect_url}";
                        }}
                    </script>
                    <p>Payment verification failed. Redirecting...</p>
                    </body></html>
                ''')
            
            # Payment verified successfully - add money to wallet
            with transaction.atomic():
                wallet, _ = Wallet.objects.get_or_create(user=topup.user)
                
                WalletTransaction.objects.create(
                    wallet=wallet,
                    amount=topup.amount,
                    transaction_type='Cr',
                    status='Completed',
                    description='Wallet Topup via Razorpay',
                    transaction_id="TXN-" + str(int(time.time())) + uuid.uuid4().hex[:4].upper()
                )
                
                wallet.balance += topup.amount
                wallet.save()
                
                # Update topup status
                topup.status = 'Completed'
                topup.razorpay_payment_id = razorpay_payment_id
                topup.razorpay_signature = razorpay_signature
                topup.save()
            
            # Add success message
            messages.success(request, f'₹{topup.amount} has been added to your wallet successfully!')
            
            # Return HTML that redirects to wallet page
            redirect_url = reverse('wallet')
            return HttpResponse(f'''
                <html><body>
                <script>
                    if (window.opener) {{
                        window.opener.location.href = "{redirect_url}";
                        window.close();
                    }} else {{
                        window.location.href = "{redirect_url}";
                    }}
                </script>
                <p>Payment successful! Redirecting...</p>
                </body></html>
            ''')
            
        except Exception as e:
            logger.error(f"Error verifying wallet payment: {e}")
            redirect_url = reverse('wallet')
            return HttpResponse(f'''
                <html><body>
                <script>
                    if (window.opener) {{
                        window.opener.location.href = "{redirect_url}";
                        window.close();
                    }} else {{
                        window.location.href = "{redirect_url}";
                    }}
                </script>
                <p>An error occurred. Redirecting...</p>
                </body></html>
            ''')
    
    return redirect('wallet')






@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def offer_management(request):
    try:
        search_query = request.GET.get('search', '')
        offers = Offer.objects.filter(
            Q(name__icontains=search_query) |
            Q(offer_type__icontains=search_query),
            is_active=True
        ).order_by('-created_at')

        # Pagination - 10 items per page
        page = request.GET.get('page', 1)
        paginator = Paginator(offers, 10)
        try:
            offers = paginator.page(page)
        except PageNotAnInteger:
            offers = paginator.page(1)
        except EmptyPage:
            offers = paginator.page(paginator.num_pages)

        data = {
            'offers': offers,
            'search_query': search_query,
            'offer_types': Offer.OFFER_TYPES,
            'first_name': request.user.name.title(),
            'is_paginated': paginator.num_pages > 1,
            'page_obj': offers,
        }
    except Exception as e:
        logger.error(f"Error in offer_management view for user {request.user.id}: {e}")
        messages.error(request, "An error occurred while loading offers. Please try again later.")
        data = {
            'offers': [],
            'search_query': '',
            'offer_types': getattr(Offer, "OFFER_TYPES", []),
            'first_name': request.user.name.title(),
            'is_paginated': False,
            'page_obj': None,
        }
    return render(request, 'offer.html', data)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_offer(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        offer_type = request.POST.get('offer_type')
        discount_percentage = request.POST.get('discount_percentage')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        if Offer.objects.filter(name__iexact=name).exists():
            messages.error(request, 'An offer with this name already exists.')
            return redirect('add_offer')
        
        try:
            offer = Offer(
                name=name,
                description=description,
                offer_type=offer_type,
                discount_percentage=int(discount_percentage),
                start_date=start_date,
                end_date=end_date
            )
            
            # Set product or category based on offer type
            if offer_type == 'Product':
                product_id = request.POST.get('product')
                if not product_id:
                    messages.error(request, 'Please select a product')
                    return redirect('add_offer')
                offer.product = get_object_or_404(Product, id=product_id)
            else:  # Category offer
                category_id = request.POST.get('category')
                if not category_id:
                    messages.error(request, 'Please select a category')
                    return redirect('add_offer')
                offer.category = get_object_or_404(Category, id=category_id)
            offer.save()
            messages.success(request, 'Offer added successfully!')
            return redirect('offer_management')
            
        except Exception as e:
            logger.error(f"Error adding offer: {e}")
            messages.error(request, 'An error occurred while adding the offer.')
            return redirect('add_offer')

    products = Product.objects.filter(is_deleted=False)
    categories = Category.objects.filter(is_deleted=False)
    context = {
        'products': products,
        'categories': categories,
        'first_name': request.user.name.title(),
    }
    return render(request, 'add_offer.html', context)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def edit_offer(request, offer_id):
    offer = get_object_or_404(Offer, id=offer_id)
    
    if request.method == 'POST':
        name = request.POST.get('name')
        
        if Offer.objects.filter(name__iexact=name).exclude(id=offer_id).exists():
            messages.error(request, 'An offer with this name already exists.')
            return redirect('edit_offer', offer_id=offer_id)
        
        try:
            offer.name = name
            offer.description = request.POST.get('description')
            offer.discount_percentage = int(request.POST.get('discount_percentage'))
            offer.start_date = request.POST.get('start_date')
            offer.end_date = request.POST.get('end_date')
            offer.save()
            
            messages.success(request, 'Offer updated successfully!')
            return redirect('offer_management')
            
        except Exception as e:
            logger.error(f"Error updating offer: {e}")
            messages.error(request, 'An error occurred while updating the offer.')
            return redirect('edit_offer', offer_id=offer_id)
    
    context = {
        'offer': offer,
        'first_name': request.user.name.title(),
    }
    return render(request, 'edit_offer.html', context)


@login_required
@admin_required
@require_POST
def delete_offer(request, offer_id):
    try:
        offer = get_object_or_404(Offer, id=offer_id)
        offer.is_active = False
        offer.save()
        return JsonResponse({'success': True, 'message': 'Offer deleted successfully!'})
    except Exception as e:
        logger.error(f"Error deleting offer {offer_id}: {e}")
        messages.error(request, 'An error occurred while deleting the offer.')
        return JsonResponse({'error': True, 'message': 'An error occurred while deleting the offer.'})


@login_required
@admin_required
def search_items(request):
    query = request.GET.get('q', '').strip()
    item_type = request.GET.get('type', '')
    
    if not query:
        return JsonResponse({'results': []})
    
    if item_type == 'product':
        items = Product.objects.filter(
            Q(name__istartswith=query) & 
            Q(is_deleted=False)
        ).order_by('name')[:10]  # order by name and limit to 10 results
        results = [{'id': item.id, 'name': item.name} for item in items]
    else:
        items = Category.objects.filter(
            Q(name__istartswith=query) & 
            Q(is_deleted=False)
        ).order_by('name')[:10]  # order by name and limit to 10 results
        results = [{'id': item.id, 'name': item.name} for item in items]
    
    return JsonResponse({'results': results})


