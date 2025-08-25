from .models import Cart
def cart_count(request):
    if request.user.is_authenticated:
        try:
            cart = Cart.objects.get(user=request.user)
            cart_items = cart.items.all()
            # ✅ Count unique items instead of sum of quantities
            total_items = cart_items.count()
            return {'cart_count': total_items}
        except Cart.DoesNotExist:
            return {'cart_count': 0}
    return {'cart_count': 0}