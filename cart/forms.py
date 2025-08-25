from django import forms
from django.core.exceptions import ValidationError
from .models import CartItem
from product.models import ProductVariant

class AddToCartForm(forms.Form):
    product_id = forms.IntegerField(widget=forms.HiddenInput())
    variant_id = forms.IntegerField(widget=forms.HiddenInput())
    quantity = forms.IntegerField(
        min_value=1,
        max_value=5,
        initial=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '5'
        })
    )
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        if quantity < 1:
            raise ValidationError("Quantity must be at least 1")
        if quantity > 5:
            raise ValidationError("Maximum quantity limit is 5 per product")
        return quantity
    
    def clean_variant_id(self):
        variant_id = self.cleaned_data.get('variant_id')
        try:
            variant = ProductVariant.objects.get(id=variant_id)
            if variant.quantity < 1:
                raise ValidationError("This product is out of stock")
            return variant_id
        except ProductVariant.DoesNotExist:
            raise ValidationError("Invalid product variant")

class UpdateCartItemForm(forms.Form):
    quantity = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '1',
            'max': '5'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.cart_item = kwargs.pop('cart_item', None)
        super().__init__(*args, **kwargs)
    
    def clean_quantity(self):
        quantity = self.cleaned_data.get('quantity')
        
        if quantity < 1:
            raise ValidationError("Quantity must be at least 1")
        if quantity > 5:
            raise ValidationError("Maximum quantity limit is 5 per product")
            
        if self.cart_item:
            if quantity > self.cart_item.variant.quantity:
                raise ValidationError(f"Only {self.cart_item.variant.quantity} items available in stock")
        
        return quantity

class CouponForm(forms.Form):
    coupon_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter coupon code',
            'style': 'text-transform: uppercase;'
        })
    )
    
    def clean_coupon_code(self):
        coupon_code = self.cleaned_data.get('coupon_code')
        if coupon_code:
            coupon_code = coupon_code.upper().strip()
            if len(coupon_code) < 3:
                raise ValidationError("Coupon code must be at least 3 characters long")
        return coupon_code

class CartValidationForm(forms.Form):
    """Form to validate entire cart before checkout"""
    
    def __init__(self, *args, **kwargs):
        self.cart = kwargs.pop('cart', None)
        super().__init__(*args, **kwargs)
    
    def clean(self):
        cleaned_data = super().clean()
        
        if not self.cart:
            raise ValidationError("No cart found")
        
        cart_items = self.cart.items.all()
        
        if not cart_items.exists():
            raise ValidationError("Cart is empty")
        
        # Check stock availability for all items
        out_of_stock_items = []
        exceeds_stock_items = []
        
        for item in cart_items:
            # Check if product/category is blocked
            if not item.product.is_listed or item.product.is_deleted:
                raise ValidationError(f"{item.product.name} is no longer available")
            
            if not item.product.category.is_listed or item.product.category.is_deleted:
                raise ValidationError(f"{item.product.name} category is no longer available")
            
            # Check stock
            if item.variant.quantity < 1:
                out_of_stock_items.append(item.product.name)
            elif item.quantity > item.variant.quantity:
                exceeds_stock_items.append({
                    'name': item.product.name,
                    'requested': item.quantity,
                    'available': item.variant.quantity
                })
        
        if out_of_stock_items:
            raise ValidationError(f"The following items are out of stock: {', '.join(out_of_stock_items)}")
        
        if exceeds_stock_items:
            error_messages = []
            for item in exceeds_stock_items:
                error_messages.append(f"{item['name']}: requested {item['requested']}, only {item['available']} available")
            raise ValidationError(f"Stock limit exceeded for: {'; '.join(error_messages)}")
        
        return cleaned_data
