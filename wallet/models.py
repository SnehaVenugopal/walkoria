from django.db import models
from users.models import CustomUser
from product.models import Product
from category.models import Category
from django.utils import timezone


class Wallet(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wallet', null=True, blank=True)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email}'s Wallet - Balance: ₹{self.balance}"


class WalletTransaction(models.Model):
    TRANSACTION_TYPES = [
        ("Cr", "Credit"),
        ("Dr", "Debit"),
    ]

    TRANSACTION_STATUS = [
        ("Pending", "Pending"),
        ("Completed", "Completed"),
        ("Failed", "Failed"),
    ]

    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=10, choices=TRANSACTION_TYPES)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=TRANSACTION_STATUS, default="Pending")
    transaction_id = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.transaction_type.capitalize()} - {self.amount}"


class WalletTopup(models.Model):
    """Store pending wallet top-up requests for Razorpay verification"""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='wallet_topups')
    razorpay_order_id = models.CharField(max_length=100, unique=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Topup {self.razorpay_order_id} - ₹{self.amount} - {self.status}"


class Offer(models.Model):
    OFFER_TYPES = [
        ('Product', 'Product'),
        ('Category', 'Category'),
    ]

    name = models.CharField(max_length=100, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    offer_type = models.CharField(max_length=10, choices=OFFER_TYPES, default='Product')
    discount_percentage = models.PositiveIntegerField(default=0)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name='offers')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, null=True, blank=True, related_name='offers')
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        from django.core.exceptions import ValidationError
        if self.offer_type == 'Product' and not self.product:
            raise ValidationError('Product must be selected for product offer')
        if self.offer_type == 'Category' and not self.category:
            raise ValidationError('Category must be selected for category offer')
        if self.start_date and self.end_date and self.start_date >= self.end_date:
            raise ValidationError('End date must be after start date')
        if self.discount_percentage < 1 or self.discount_percentage > 90:
            raise ValidationError('Discount percentage must be between 1 and 90')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def is_valid(self):
        now = timezone.now()
        return (
            self.is_active and 
            self.start_date <= now <= self.end_date
        )

    def __str__(self):
        return f"{self.name} - {self.offer_type} Offer ({self.discount_percentage}%)"
