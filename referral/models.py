from django.db import models
from users.models import CustomUser
import uuid
import string
import random


def generate_referral_code():
    """Generate a unique 8-character referral code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))


class Referral(models.Model):
    """Tracks individual referral relationships"""
    referrer = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='referrals_made',
        help_text="User who owns this referral code"
    )
    referred_user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='referred_by', 
        null=True, 
        blank=True,
        help_text="User who used this referral code"
    )
    referral_code = models.CharField(
        max_length=20, 
        unique=True, 
        default=generate_referral_code
    )
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    used_at = models.DateTimeField(null=True, blank=True)
    
    # Reward tracking
    reward_given_to_referrer = models.BooleanField(default=False)
    reward_given_to_referred = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.referrer.email} - {self.referral_code}"


class ReferralOffer(models.Model):
    """Store the current referral offer/reward configuration"""
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    referrer_reward = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Reward amount for the person who refers"
    )
    referred_reward = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Reward amount for the new user who uses the code"
    )
    is_active = models.BooleanField(default=True)
    valid_from = models.DateTimeField()
    valid_until = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.name
