from django.db import models
from users.models import CustomUser
from product.models import Product


# Create your models here.


class ProductReview(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.IntegerField(choices=[(i, f"{i} Star") for i in range(1, 6)])
    title = models.CharField(max_length=255, blank=True, null=True)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=True)
    is_verified_purchase = models.BooleanField(default=False)

    def __str__(self):
        return f"Review by {self.user} on {self.product.name}"
