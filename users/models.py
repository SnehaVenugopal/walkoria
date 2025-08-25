from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from datetime import timedelta
import random


class CustomUser(AbstractUser):
    name = models.CharField(max_length=150, blank=True)
    mobile_no = models.CharField(max_length=15, unique=True,blank=True,null=True)
    email = models.EmailField(unique=True)
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Blocked', 'Blocked'),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Active')
    profile_image = models.CharField(max_length=500, blank=True, null=True)
    first_name=None
    last_name=None
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

class OTPVerification(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expiry_time = models.DateTimeField(default=timezone.now() + timedelta(minutes=1))  # 1 minute expiry

    def is_valid(self):
        return timezone.now() - self.created_at < timezone.timedelta(minutes=1)
    def is_expired(self):
        return timezone.now() > self.expiry_time
    


