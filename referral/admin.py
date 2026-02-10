from django.contrib import admin
from .models import Referral, ReferralOffer


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = [
        'referral_code', 
        'referrer', 
        'referred_user', 
        'is_used', 
        'reward_given_to_referrer',
        'reward_given_to_referred',
        'created_at'
    ]
    list_filter = ['is_used', 'reward_given_to_referrer', 'reward_given_to_referred', 'created_at']
    search_fields = ['referral_code', 'referrer__email', 'referred_user__email']
    readonly_fields = ['created_at', 'used_at']
    date_hierarchy = 'created_at'


@admin.register(ReferralOffer)
class ReferralOfferAdmin(admin.ModelAdmin):
    list_display = [
        'name', 
        'referrer_reward', 
        'referred_reward', 
        'is_active', 
        'valid_from', 
        'valid_until'
    ]
    list_filter = ['is_active', 'valid_from']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']
