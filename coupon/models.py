from django.db import models
from users.models import CustomUser

# Create your models here.

class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_type = models.CharField(max_length=10,
        choices=[('fixed', 'Fixed Amount'), ('percent', 'Percentage')],
        default='percent')
    description = models.TextField(blank=True)
    discount_value = models.IntegerField()
    max_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    min_cart_value = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    max_usage = models.PositiveIntegerField(default=1)
    max_usage_per_user = models.PositiveIntegerField(default=1)
    active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.code


class UserCoupon(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='used_coupons')
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE)
    order = models.ForeignKey('orders.Order', on_delete=models.SET_NULL, null=True, related_name='used_coupons')
    used_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email} - {self.coupon.code}"
