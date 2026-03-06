from django.db import models
from django.utils import timezone
from users.models import CustomUser
from userpanel.models import Address
from product.models import ProductVariant
from coupon.models import Coupon


class Order(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('RP', 'Razor Pay'),
        ('WP', 'Wallet Pay'),
        ('COD', 'Cash on Delivery'),
    ]
    

    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='orders')
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(choices=PAYMENT_METHOD_CHOICES, max_length=4)
    payment_status = models.BooleanField(default=False)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, related_name='shipping_orders')
    shipping_cost = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)
    razorpay_order_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_payment_id = models.CharField(max_length=100, blank=True, null=True)
    razorpay_signature = models.CharField(max_length=200, blank=True, null=True)

    def calculate_total(self):
        self.subtotal = sum(item.price * item.quantity for item in self.items.all())
        self.save()

    def get_overall_status(self):
        """Determine overall order status based on all items' statuses"""
        items = self.items.all()
        if not items:
            return 'Pending'
        
        statuses = [item.status for item in items]
        
        # Check if all items have Payment_Failed status
        if all(s == 'Payment_Failed' for s in statuses):
            return 'Payment Failed'
        
        # Priority order for determining overall status
        # If all items have the same status, return that status
        if len(set(statuses)) == 1:
            return statuses[0].replace('_', ' ')
        
        # If any item is Delivered, show as Delivered (or Partially Delivered)
        if 'Delivered' in statuses:
            if all(s in ['Delivered', 'Returned', 'Cancelled'] for s in statuses):
                return 'Delivered'
            return 'Partially Delivered'
        
        # If any item is Shipped or On_the_Way
        if 'Shipped' in statuses or 'On_the_Way' in statuses:
            return 'Shipped'
        
        # If any item is Processing
        if 'Processing' in statuses:
            return 'Processing'
        
        # If all items are Cancelled
        if all(s == 'Cancelled' for s in statuses):
            return 'Cancelled'
        
        # If all items are Returned
        if all(s == 'Returned' for s in statuses):
            return 'Returned'
        
        # If any item has Return_Requested
        if 'Return_Requested' in statuses:
            return 'Return Requested'
        
        # Default to Pending
        return 'Pending'

    def __str__(self):
        return f"Order {self.order_number} by {self.user.name}"


class OrderItem(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Payment_Failed', 'Payment Failed'),
        ('Processing', 'Processing'),
        ('On_Hold', 'On Hold'),
        ('Shipped', 'Shipped'),
        ('On_the_Way', 'On the Way'),
        ('Delivered', 'Delivered'),
        ('Cancelled', 'Cancelled'),
        ('Return_Requested', 'Return Requested'),
        ('Returned', 'Returned'),
        ('Refunded', 'Refunded'),
    ]

    CANCELLATION_REASON_CHOICES = [
        ('OPM', 'Order Placed by Mistake'),
        ('CMM', 'Changed My Mind'),
        ('DTL', 'Delivery Time Was Too Long'),
        ('ILN', 'Item No Longer Needed'),
        ('OWI', 'Ordered Wrong Item'),
        ('OFS', 'Item Not Available or Out of Stock'),
        ('DP', 'Received Damaged Product'),
        ('RII', 'Received Incorrect Item'),
        ('NME', 'Product Didn\'t Meet Expectations'),
        ('QC', 'Quality Concerns'),
        ('SCI', 'Size/Color Issue'),
    ]

    ITEM_PAYMENT_STATUS_CHOICES = [
        ('Pending', 'pending'),
        ('Paid', 'paid'),
        ('Unpaid', 'unpaid'),
        ('Failed', 'failed'),
        ('Refunded', 'refunded'),
        ('Processing', 'processing'),
        ('Cancelled', 'cancelled')
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, related_name='order_items')
    quantity = models.PositiveIntegerField()
    original_price = models.DecimalField(max_digits=10, decimal_places=2)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(choices=STATUS_CHOICES, max_length=24, default='Pending')
    item_payment_status = models.CharField(choices=ITEM_PAYMENT_STATUS_CHOICES, max_length=10, default='pending')
    cancellation_reason = models.CharField(choices=CANCELLATION_REASON_CHOICES, max_length=4, blank=True, null=True)
    custom_cancellation_reason = models.TextField(blank=True, null=True)
    admin_note = models.TextField(blank=True, null=True)
    is_cancelled = models.BooleanField(default=False)
    is_bill_generated = models.BooleanField(default=False)
    invoice_number = models.CharField(max_length=50, blank=True, null=True, unique=True)
    # Effective (after-offer) unit price saved at checkout — survives cancellation zeroing
    effective_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def generate_bill(self):
        if self.status == 'Delivered' and not self.is_bill_generated:
            self.invoice_number = f"INV-{self.id}{timezone.now().strftime('%Y%m%d%H%M%S')}"
            self.is_bill_generated = True
            self.save()

    def get_effective_price(self):
        """
        Return the price actually paid per unit for this item.

        item.price is saved at checkout with any active offer already applied,
        so we just return it directly.  We must NOT re-query the Offer table
        here because:
          1) The offer may have since expired — a fallback would then pick ANY
             offer regardless of dates, giving a wrong (too-low) price.
          2) Even a date-bounded query could mis-fire if the offer window was
             later edited.

        The snapshot in item.price is the single source of truth.
        """
        return self.price

    def get_effective_item_subtotal(self):
        """
        Return what was actually paid for this item after offer discounts
        (before coupon and delivery).

        Primary source: self.effective_price (saved at checkout, persists after
        cancellation even when order totals are zeroed out).
        Fallback: derived proportionally from live order totals (works for
        active orders; may show sale price for old cancelled orders).
        """
        from decimal import Decimal
        try:
            # Use saved effective price if available (set at checkout)
            if self.effective_price is not None:
                return round(self.effective_price * self.quantity, 2)

            # Fallback: compute from order totals (won't work after cancellation zeroes them)
            order = self.order
            shipping = order.shipping_cost or Decimal('0')
            coupon   = order.discount      or Decimal('0')
            items_total_after_offers = order.total_amount + coupon - shipping
            item_sale_value = self.price * self.quantity
            all_sale_value  = order.subtotal
            if all_sale_value > 0 and items_total_after_offers > 0:
                return round((item_sale_value / all_sale_value) * items_total_after_offers, 2)
            return round(item_sale_value, 2)
        except Exception:
            return round(self.price * self.quantity, 2)

    def get_effective_unit_price(self):
        """Return the effective (after-offer) price per unit."""
        subtotal = self.get_effective_item_subtotal()
        return round(subtotal / self.quantity, 2) if self.quantity else subtotal

    def get_refund_amount(self):
        """
        Calculate the actual amount credited to wallet on return/cancellation.

        Refund = item's effective (after-offer) value
                 − proportional coupon share
                 + delivery refund (ONLY if this is the last active item)

        The order stores:
          - total_amount  : items_after_offers + shipping - coupon
          - discount      : coupon amount
          - shipping_cost : delivery charge
          - subtotal      : raw sale_price × qty (NO offer applied)

        items_total_after_offers = total_amount + discount - shipping_cost

        ⚠️ IMPORTANT: This method is called AFTER the item's status is already
        saved as 'Cancelled' in the DB (order_item.save() runs before this call
        in cancel_product). So we must use exclude(pk=self.pk) — NOT
        exclude(status='Cancelled') — to determine whether other active items
        still remain. Using status='Cancelled' would incorrectly exclude the
        current item and give a wrong (too-high) delivery share in multi-item orders.
        """
        from decimal import Decimal
        try:
            order = self.order
            shipping = order.shipping_cost or Decimal('0')
            coupon   = order.discount      or Decimal('0')

            # True items-only total after offers, before coupon & delivery
            items_total_after_offers = order.total_amount + coupon - shipping

            # This item's sale-price weight
            item_sale_value = self.price * self.quantity
            all_sale_value  = order.subtotal  # sum of item.price * qty (no offer)

            # Derive this item's effective (after-offer) value
            if all_sale_value > 0:
                item_effective_value = (item_sale_value / all_sale_value) * items_total_after_offers
            else:
                item_effective_value = item_sale_value

            # Proportional coupon share for this item
            if items_total_after_offers > 0 and coupon > 0:
                coupon_proportion = item_effective_value / items_total_after_offers
                coupon_share = coupon * coupon_proportion
            else:
                coupon_share = Decimal('0')

            # Delivery refund:
            # Use exclude(pk=self.pk) — NOT exclude(status='Cancelled') — because
            # this item is ALREADY saved as 'Cancelled' in DB when this runs,
            # so checking status would always make len=1 in a 2-item order.
            # We check for other items that are still active (not cancelled/returned).
            other_active_items = order.items.exclude(pk=self.pk).exclude(
                status__in=['Cancelled', 'Returned', 'Payment_Failed', 'Refunded']
            )
            is_last_active_item = not other_active_items.exists()

            if is_last_active_item:
                # Truly the last item — refund the full delivery charge too
                item_delivery_share = shipping
            else:
                # Partial cancellation — delivery still needed for remaining items
                # Do NOT refund delivery
                item_delivery_share = Decimal('0')

            refund = item_effective_value - coupon_share + item_delivery_share
            return round(max(refund, Decimal('0')), 2)
        except Exception:
            return round(self.price * self.quantity, 2)

    def get_actual_refund_credited(self):
        """
        Return the actual refund amount that was credited to the wallet for
        this item's order cancellation/return by looking up the WalletTransaction.
        This is used in the Order Timeline so we show the real credited amount
        rather than recalculating (which returns 0 after order totals are zeroed).
        """
        try:
            from wallet.models import WalletTransaction
            txn = (
                WalletTransaction.objects
                .filter(
                    order=self.order,
                    transaction_type='Cr',
                    status='Completed',
                    description__icontains='Refund'
                )
                .order_by('-created_at')
                .first()
            )
            if txn:
                return txn.amount
            return None
        except Exception:
            return None

    def save(self, *args, **kwargs):
        if self.status == 'Delivered':
            if not self.is_bill_generated:
                self.generate_bill()
            self.item_payment_status = 'Paid'
        super().save(*args, **kwargs)
        if self.item_payment_status == 'Paid':
            order = self.order
            if all(item.item_payment_status == 'Paid' for item in order.items.all()):
                order.payment_status = True
                order.save()

    def __str__(self):
        return f"{self.product_variant.product.name} - {self.quantity} pcs at ₹{self.price}"

    @property
    def total_price(self):
        return self.price * self.quantity


class ReturnRequest(models.Model):
    order = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name='return_requests')
    status = models.CharField(
        max_length=20,
        choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')],
        default='Pending'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Return Request for {self.order.product_variant.product.name}"
