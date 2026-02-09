from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.http import JsonResponse
from django.db.models import Q
from .models import Referral, ReferralOffer
from wallet.models import Wallet, WalletTransaction


@login_required
def my_referrals(request):
    """Display user's referral code and referral history"""
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    # Get or create user's referral code
    referral, created = Referral.objects.get_or_create(
        referrer=request.user,
        is_used=False,
        defaults={'referral_code': Referral._meta.get_field('referral_code').default()}
    )
    
    # Get all referrals made by this user
    successful_referrals = Referral.objects.filter(
        referrer=request.user,
        is_used=True
    ).select_related('referred_user').order_by('-used_at')
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(successful_referrals, 5)
    try:
        successful_referrals = paginator.page(page)
    except PageNotAnInteger:
        successful_referrals = paginator.page(1)
    except EmptyPage:
        successful_referrals = paginator.page(paginator.num_pages)
    
    # Get active referral offer
    active_offer = ReferralOffer.objects.filter(
        is_active=True,
        valid_from__lte=timezone.now()
    ).filter(
        Q(valid_until__gte=timezone.now()) | Q(valid_until__isnull=True)
    ).first()
    
    context = {
        'referral_code': referral.referral_code,
        'successful_referrals': successful_referrals,
        'total_referrals': Referral.objects.filter(referrer=request.user, is_used=True).count(),
        'active_offer': active_offer,
    }
    
    return render(request, 'referral/my_referrals.html', context)


def apply_referral_code(request):
    """Apply referral code during signup or in profile"""
    if request.method == 'POST':
        referral_code = request.POST.get('referral_code', '').strip().upper()
        
        if not referral_code:
            return JsonResponse({
                'success': False,
                'message': 'Please enter a referral code'
            })
        
        # Check if user already used a referral code
        if Referral.objects.filter(referred_user=request.user).exists():
            return JsonResponse({
                'success': False,
                'message': 'You have already used a referral code'
            })
        
        try:
            # Find the referral code
            referral = Referral.objects.get(referral_code=referral_code, is_used=False)
            
            # Can't use your own referral code
            if referral.referrer == request.user:
                return JsonResponse({
                    'success': False,
                    'message': 'You cannot use your own referral code'
                })
            
            # Get active offer
            active_offer = ReferralOffer.objects.filter(
                is_active=True,
                valid_from__lte=timezone.now()
            ).filter(
                Q(valid_until__gte=timezone.now()) | Q(valid_until__isnull=True)
            ).first()
            
            if not active_offer:
                return JsonResponse({
                    'success': False,
                    'message': 'No active referral offer at the moment'
                })
            
            # Mark referral as used
            referral.referred_user = request.user
            referral.is_used = True
            referral.used_at = timezone.now()
            referral.save()
            
            # DON'T give rewards immediately - they will be given after first purchase
            # give_referral_rewards(referral, active_offer)
            
            return JsonResponse({
                'success': True,
                'message': f'Referral code applied! You will receive ₹{active_offer.referred_reward} after your first purchase.'
            })
            
        except Referral.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Invalid or already used referral code'
            })
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid request method'
    })


def give_referral_rewards(referral, offer):
    """Give wallet rewards to both referrer and referred user"""
    from decimal import Decimal
    import time
    
    # Reward to the person who was referred (new user)
    if not referral.reward_given_to_referred and referral.referred_user:
        wallet, created = Wallet.objects.get_or_create(user=referral.referred_user)
        # Refresh from DB to ensure balance is Decimal
        wallet.refresh_from_db()
        wallet.balance = wallet.balance + Decimal(str(offer.referred_reward))
        wallet.save()
        
        # Generate transaction ID
        txn_id = f"REF{int(time.time())}{referral.referred_user.id}"
        
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='Cr',
            amount=Decimal(str(offer.referred_reward)),
            status='Completed',
            transaction_id=txn_id
        )
        
        referral.reward_given_to_referred = True
    
    # Reward to the person who referred (existing user)
    if not referral.reward_given_to_referrer:
        wallet, created = Wallet.objects.get_or_create(user=referral.referrer)
        # Refresh from DB to ensure balance is Decimal
        wallet.refresh_from_db()
        wallet.balance = wallet.balance + Decimal(str(offer.referrer_reward))
        wallet.save()
        
        # Generate transaction ID
        txn_id = f"REF{int(time.time())}{referral.referrer.id}"
        
        WalletTransaction.objects.create(
            wallet=wallet,
            transaction_type='Cr',
            amount=Decimal(str(offer.referrer_reward)),
            status='Completed',
            transaction_id=txn_id
        )
        
        referral.reward_given_to_referrer = True
    
    referral.save()
