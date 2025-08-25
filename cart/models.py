from django.db import models
from users.models import CustomUser
from product.models import Product, ProductVariant


class Cart(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='carts', null=True, blank=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    delivery_charge = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart for {self.user.email if self.user else 'Anonymous'}"

    def calculate_total(self):
        self.total_price = sum(item.total_price for item in self.items.all() if item.quantity > 0)
        self.delivery_charge = 0 if self.total_price > 4999 else 99
        self.total_price += self.delivery_charge
        self.save()

    def get_total_actual_price(self):
        return sum(item.get_actual_price() for item in self.items.all() if item.quantity > 0)


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name='cart_items')
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    added_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.clean()

        if self.quantity > 0:
            # Calculate total based on sale price and quantity
            self.total_price = self.variant.sale_price * self.quantity
        else:
            self.total_price = 0

        # Save CartItem, then update cart total
        super().save(*args, **kwargs)
        self.cart.calculate_total()

    def __str__(self):
        return f"{self.quantity} of {self.product.name} in cart ID {self.cart.id}"

    def get_actual_price(self):
        return self.variant.actual_price * self.quantity

    def get_subtotal(self):
        """Get subtotal based on sale price and quantity"""
        return self.variant.sale_price * self.quantity

    def get_offer_discount(self):
        """Calculate offer discount based on sale price"""
        try:
            from wallet.models import Offer
            from django.utils import timezone
            
            now = timezone.now()
            total_sale_price = self.variant.sale_price * self.quantity
            
            # Check product offer
            product_offer = Offer.objects.filter(
                product=self.variant.product,
                offer_type='Product',
                start_date__lte=now,
                end_date__gte=now,
                is_active=True
            ).order_by('-discount_percentage').first()
            
            # Check category offer
            category_offer = Offer.objects.filter(
                category=self.variant.product.category,
                offer_type='Category',
                start_date__lte=now,
                end_date__gte=now,
                is_active=True
            ).order_by('-discount_percentage').first()
            
            # Get the best discount
            product_discount = product_offer.discount_percentage if product_offer else 0
            category_discount = category_offer.discount_percentage if category_offer else 0
            
            best_discount = max(product_discount, category_discount)
            if best_discount > 0:
                return (total_sale_price * best_discount) / 100
            return 0
        except ImportError:
            # If wallet app doesn't exist, return 0
            return 0
    
    def get_final_price(self):
        """Calculate final price after offer discount"""
        total_sale_price = self.variant.sale_price * self.quantity
        offer_discount = self.get_offer_discount()
        return total_sale_price - offer_discount

    def get_offer_details(self):
        """Get details of the applied offer"""
        try:
            from wallet.models import Offer
            from django.utils import timezone
            
            now = timezone.now()
            
            # Check product offer
            product_offer = Offer.objects.filter(
                product=self.variant.product,
                offer_type='Product',
                start_date__lte=now,
                end_date__gte=now,
                is_active=True
            ).order_by('-discount_percentage').first()
            
            # Check category offer
            category_offer = Offer.objects.filter(
                category=self.variant.product.category,
                offer_type='Category',
                start_date__lte=now,
                end_date__gte=now,
                is_active=True
            ).order_by('-discount_percentage').first()
            
            if not product_offer and not category_offer:
                return None
                
            # Return the better offer
            if (product_offer and category_offer and 
                product_offer.discount_percentage >= category_offer.discount_percentage):
                return {
                    'name': product_offer.name,
                    'type': 'Product',
                    'discount': product_offer.discount_percentage
                }
            elif category_offer:
                return {
                    'name': category_offer.name,
                    'type': 'Category',
                    'discount': category_offer.discount_percentage
                }
            else:
                return {
                    'name': product_offer.name,
                    'type': 'Product',
                    'discount': product_offer.discount_percentage
                }
        except ImportError:
            return None
