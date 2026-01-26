from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.cache import cache_control
from django.db.models import Q
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.core.mail import send_mail
from django.utils.html import strip_tags
from django.utils import timezone
from datetime import timedelta
import random, uuid, time, json, logging
from product.models import Product
from category.models import Category
from django.conf import settings
from utils.decorators import admin_required
from .models import Wallet, WalletTransaction, Offer


logger = logging.getLogger(__name__)

@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def wallet_view(request):
    try:
        wallet, _ = Wallet.objects.get_or_create(user=request.user)
        transactions = WalletTransaction.objects.filter(wallet=wallet).order_by('-created_at')
        
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
        }
    except Exception as e:
        logger.error(f"Error in wallet_view for user {request.user.id}: {e}")
        messages.error(request, "An error occurred while loading your wallet. Please try again later.")
        data = {
            'wallet': None,
            'transactions': [],
        }
    return render(request, 'wallet.html', data)


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

        data = {
            'offers': offers,
            'search_query': search_query,
            'offer_types': Offer.OFFER_TYPES,
            'first_name': request.user.name.title(),
        }
    except Exception as e:
        logger.error(f"Error in offer_management view for user {request.user.id}: {e}")
        messages.error(request, "An error occurred while loading offers. Please try again later.")
        data = {
            'offers': [],
            'search_query': '',
            'offer_types': getattr(Offer, "OFFER_TYPES", []),
            'first_name': request.user.name.title(),
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
            return JsonResponse({'success': False, 'message': 'An offer with this name already exists.'})
        
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
                    return JsonResponse({'success': False, 'message': 'Please select a product'})
                offer.product = get_object_or_404(Product, id=product_id)
            else:  # Category offer
                category_id = request.POST.get('category')
                if not category_id:
                    return JsonResponse({'success': False, 'message': 'Please select a category'})
                offer.category = get_object_or_404(Category, id=category_id)
            offer.save()
            return JsonResponse({'success': True, 'message': 'Offer added successfully!'})
            
        except Exception as e:
            logger.error(f"Error adding offer: {e}")
            return JsonResponse({'success': False, 'message': 'An error occurred while adding the offer.'})

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
@require_POST
def edit_offer(request, offer_id):
    offer = get_object_or_404(Offer, id=offer_id)
    data = json.loads(request.body)
    name = data.get('name')
    
    if Offer.objects.filter(name=name).exclude(id=offer_id).exists():
        return JsonResponse({'success': False, 'message': 'An offer with this name already exists.'})
    
    offer.name = name
    offer.description = data.get('description')
    offer.start_date = data.get('start_date')
    offer.end_date = data.get('end_date')
    offer.save()
    
    return JsonResponse({'success': True, 'message': 'Offer updated successfully.'})


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


@login_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def add_money(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            amount = int(data.get('amount', 0))
            
            if amount < 100:
                return JsonResponse({'error': 'Amount must be at least ₹100'}, status=400)
            if amount > 20000:
                return JsonResponse({'error': 'Amount cannot exceed ₹20,000'}, status=400)
            
            # Generate OTP and set expiry
            otp = random.randint(100000, 999999)
            print(f"=== ADD MONEY OTP: {otp} ===")
            otp_expiry = (timezone.now() + timedelta(minutes=5)).isoformat()
            
            request.session['add_money_data'] = {
                'amount': amount,
                'otp': otp,
                'otp_expiry': otp_expiry
            }
            
            html_message = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; color: #333;">
                        <h2 style="color: #4CAF50;">Add Money to Wallet</h2>
                        <p>Dear {request.user.name.title()},</p>
                        <p>Please use the following code to verify your wallet recharge of ₹{amount}. <strong>This code will expire in 5 minutes.</strong></p>
                        <p style="font-size: 24px; font-weight: bold; color: #4CAF50;">{otp}</p>
                        <p>If you didn't request this, please ignore this email.</p>
                        <p>Best regards,<br>StrideKicks</p>
                    </body>
                </html>
                """
            plain_message = strip_tags(html_message)
            send_mail(
                'StrideKicks Wallet Recharge Verification',
                plain_message,
                settings.EMAIL_HOST_USER,
                [request.user.email],
                fail_silently=False,
                html_message=html_message,
            )
            
            return JsonResponse({'message': 'OTP sent successfully'})
        except (ValueError, TypeError, json.JSONDecodeError):
            logger.error(f"Invalid amount or data format in add_money for user {request.user.id}")
            return JsonResponse({'error': 'Invalid amount'}, status=400)
        except Exception as e:
            logger.error(f"Error in add_money for user {request.user.id}: {e}")
            return JsonResponse({'error': 'An error occurred while adding money to the wallet.'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def verify_add_money_otp(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            entered_otp = data.get('otp')
            
            add_money_data = request.session.get('add_money_data')
            if not add_money_data:
                return JsonResponse({'error': 'No pending transaction found'}, status=400)
            
            stored_otp = add_money_data.get('otp')
            otp_expiry = timezone.datetime.fromisoformat(add_money_data.get('otp_expiry'))
            
            if timezone.now() > otp_expiry:
                del request.session['add_money_data']
                return JsonResponse({'error': 'OTP has expired.'}, status=400)
            if str(entered_otp) != str(stored_otp):
                return JsonResponse({'error': 'Invalid OTP.'}, status=400)
            
            # Add money to wallet
            amount = add_money_data.get('amount')
            wallet, _ = Wallet.objects.get_or_create(user=request.user)
            
            transaction = WalletTransaction.objects.create(
                wallet=wallet,
                amount=amount,
                transaction_type='Cr',
                status='Completed',
                transaction_id="TXN-" + str(int(time.time())) + uuid.uuid4().hex[:4].upper()
            )
            
            wallet.balance += amount
            wallet.save()
            del request.session['add_money_data']
            
            return JsonResponse({'message': 'Money added successfully'})
        except Exception as e:
            logger.error(f"Error verifying OTP for add money for user {request.user.id}: {e}")
            return JsonResponse({'error': 'An error occurred while verifying the OTP.'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


@login_required
def resend_add_money_otp(request):
    if request.method == 'POST':
        try:
            add_money_data = request.session.get('add_money_data')
            if not add_money_data:
                return JsonResponse({'error': 'No pending transaction found'}, status=400)
            
            otp = random.randint(100000, 999999)
            print(f"=== RESEND OTP: {otp} ===")
            otp_expiry = (timezone.now() + timedelta(minutes=5)).isoformat()
            
            add_money_data['otp'] = otp
            add_money_data['otp_expiry'] = otp_expiry
            request.session['add_money_data'] = add_money_data
            
            # Send new OTP email
            amount = add_money_data.get('amount')
            html_message = f"""
                <html>
                    <body style="font-family: Arial, sans-serif; color: #333;">
                        <h2 style="color: #4CAF50;">Add Money to Wallet</h2>
                        <p>Dear {request.user.name},</p>
                        <p>Please use the following code to verify your wallet recharge of ₹{amount}. <strong>This code will expire in 5 minutes.</strong></p>
                        <p style="font-size: 24px; font-weight: bold; color: #4CAF50;">{otp}</p>
                        <p>If you didn't request this, please ignore this email.</p>
                        <p>Best regards,<br>StrideKicks</p>
                    </body>
                </html>
                """
            plain_message = strip_tags(html_message)
            send_mail(
                'StrideKicks Wallet Recharge Verification',
                plain_message,
                settings.EMAIL_HOST_USER,
                [request.user.email],
                fail_silently=False,
                html_message=html_message,
            )
            
            return JsonResponse({'message': 'OTP resent successfully'})
        except Exception as e:
            logger.error(f"Error resending OTP for add money for user {request.user.id}: {e}")
            return JsonResponse({'error': 'An error occurred while resending the OTP.'}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=405)

