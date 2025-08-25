from django import template

register = template.Library()

@register.filter
def status_text_color(status):
    colors = {
        'pending': 'text-warning',
        'paid': 'text-success',
        'unpaid': 'text-secondary',
        'failed': 'text-danger',
        'refunded': 'text-info',
        'processing': 'text-primary',
        'cancelled': 'text-danger',
    }
    return colors.get(status.lower(), 'text-secondary') 