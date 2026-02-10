from django.shortcuts import render,get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.cache import cache_control
from django.views.decorators.cache import cache_control
from admin.forms import CustomAuthenticationForm
from django.contrib.auth import logout
from wallet.models import Wallet, WalletTransaction, Offer
from django.utils import timezone
from datetime import datetime, timedelta
import json, uuid, time
from utils.decorators import admin_required
from django.contrib.auth import logout
from users.models import CustomUser
from django.db.models import Q, Count, Sum, F
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from orders.models import Order, OrderItem, ReturnRequest
from django.http import HttpResponse, HttpResponseNotAllowed
import xlsxwriter
from io import BytesIO
from reportlab.pdfgen import canvas
from decimal import Decimal
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_RIGHT, TA_CENTER, TA_LEFT
from reportlab.lib import colors

#admin login view

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def login_to_account(request):
    user = request.user

    if user.is_authenticated:
        if user.is_superuser:
            return redirect('admin_dashboard')
        else:
            logout(request)  # Prevent regular users from accessing admin panel
            messages.error(request, 'You are not authorized to access the admin panel.')
            return redirect('login')  # Redirect to user login or show admin login again

    if request.method == 'POST':
        form = CustomAuthenticationForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            if not user.is_superuser:
                messages.error(request, 'Only admin can login here.')
                return render(request, 'admin_login.html', {'form': form})
            login(request, user)
            username = user.username.title()
            # messages.success(request, f"Login Successful. Welcome, {username}!")
            return redirect('admin_dashboard')
        else:
            for error in form.non_field_errors():
                messages.error(request, error)
            return render(request, 'admin_login.html', {'form': form})
    else:
        form = CustomAuthenticationForm()
        return render(request, 'admin_login.html', {'form': form})


#dashboard view

@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def dashboard_view(request):
    return render(request,'dashboard.html')


#customers view

@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def customers_view(request):
    users = CustomUser.objects.filter(is_superuser=False).order_by('name')
    search_query = request.GET.get('search')
    status_filter = request.GET.get('status')

    if search_query:
        users = users.filter(
            Q(name__istartswith=search_query) |
            Q(email__istartswith=search_query) |
            Q(mobile_no__istartswith=search_query)
        )
    if status_filter:
        users = users.filter(status=status_filter)

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(users, 8)
    try:
        users_page = paginator.page(page)
    except PageNotAnInteger:
        users_page = paginator.page(1)
    except EmptyPage:
        users_page = paginator.page(paginator.num_pages)

    name = request.user.name.title()
    context = {
        'users': users_page,
        'name': name
    }
    print("sdfghj",users_page)
    return render(request, 'customers.html', context)


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def customer_status(request):
    if request.method == 'POST':
        try:
            email = request.POST.get('email')
            user = get_object_or_404(CustomUser, email=email)
            
            if user.status == 'Blocked':
                user.status = 'Active'
                action = 'listed'
            else:
                user.status = 'Blocked'
                action = 'unlisted'
            user.save()
            
            # Check if request is AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/x-www-form-urlencoded':
                from django.http import JsonResponse
                return JsonResponse({
                    'success': True,
                    'message': f"Customer {user.name.title()} {action} successfully.",
                    'new_status': user.status
                })
            
            messages.success(request, f"Customer {user.name.title()} {action} successfully.")
        except ObjectDoesNotExist:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'message': 'User not found.'}, status=404)
            messages.error(request, "User not found.")
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                from django.http import JsonResponse
                return JsonResponse({'success': False, 'message': str(e)}, status=500)
            messages.error(request, f"An unexpected error occurred: {e}")
    return redirect('customers')



@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_orders(request):
    # name = request.user.name.title()
    order_items_list = (
        OrderItem.objects
        .select_related('order__user', 'product_variant__product')
        .order_by('-order__created_at')
    )

    search_query = request.GET.get('search', '').strip()
    print("Search Query:", search_query)

    if search_query:
        order_items_list = order_items_list.filter(
            Q(order__order_number__icontains=search_query) |   # Order ID
            Q(order__user__name__icontains=search_query) |     # Customer Name
            Q(order__user__email__icontains=search_query) |    # Email (optional)
            Q(product_variant__product__name__icontains=search_query)  # Product
        ).distinct()

    status_filter = request.GET.get('status', '')
    if status_filter:
        order_items_list = order_items_list.filter(status=status_filter)
    
    # Get return requests (items with status 'Return Requested')
    return_requests = OrderItem.objects.filter(
        status='Return_Requested'
    ).select_related(
        'order__user',
        'product_variant__product'
    ).order_by('-order__created_at')
    
    # Pagination
    paginator = Paginator(order_items_list, 5)
    page = request.GET.get('page', 1)
    try:
        order_items = paginator.page(page)
    except PageNotAnInteger:
        order_items = paginator.page(1)
    except EmptyPage:
        order_items = paginator.page(paginator.num_pages)
    
    first_name = request.user.name.title()
    data = {
        'order_items': order_items,
        'return_requests': return_requests,
        'status_choices': OrderItem.STATUS_CHOICES,
        'search_query': search_query,
        'status_filter': status_filter,
        'first_name': first_name,
    }
    return render(request, 'admin_orders.html', data)


@login_required
@admin_required
def handle_return_request(request, request_id, action):
    if not request.method == 'POST':
        return HttpResponseNotAllowed(['POST'])
    
    try:
        order_item = OrderItem.objects.get(id=request_id, status='Return_Requested')
        order = order_item.order
        return_requests = ReturnRequest.objects.filter(order_id=request_id).last()

        if action == 'approve':
            order_item.status = 'Returned'
            order_item.item_payment_status = 'Refunded'
            return_requests.status = 'Approved'

            # refund by proportion
            total_item_price = order_item.price * order_item.quantity
            proportion = total_item_price / (order.total_amount + order.discount)
            allocated_discount = order.discount * proportion
            returned_item_price = order_item.price  * order_item.quantity
            proportional_discount = (allocated_discount / order_item.quantity) * order_item.quantity
            refund_amount = returned_item_price - proportional_discount

            wallet, _ = Wallet.objects.get_or_create(user=order.user)
            from decimal import Decimal
            wallet.refresh_from_db()
            refund_decimal = Decimal(str(refund_amount))
            wallet.balance = wallet.balance + refund_decimal
            wallet.save()
            WalletTransaction.objects.create(
                            wallet=wallet,
                            transaction_type="Cr",
                            amount=refund_decimal,
                            status="Completed",
                            transaction_id="RT" + str(int(time.time()))[-6:] + uuid.uuid4().hex[:4].upper(),
                        )

            # qty
            product_variant = order_item.product_variant
            product_variant.quantity += order_item.quantity
            product_variant.save()

            messages.success(request, 'Return request approved successfully.')
        elif action == 'reject':
            order_item.status = 'Delivered'
            return_requests.status = 'Rejected'
            messages.error(request, 'Return request rejected.')
        else:
            messages.error(request, 'Invalid action.')
            return redirect('orders')
        
        order_item.save()
        return_requests.save()
        return redirect('orders')
        
    except OrderItem.DoesNotExist:
        messages.error(request, 'Return request not found.')
        return redirect('orders')


@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_order_overview(request, order_id):
    first_name = request.user.name.title()
    order = get_object_or_404(Order, id=order_id)
    other_orders = Order.objects.filter(user=order.user).exclude(id=order_id)
    status_choices = OrderItem.STATUS_CHOICES
    
    # Calculate totals and identify offers
    items = order.items.all().select_related('product_variant__product__category')
    enhanced_items = []
    
    total_mrp = 0
    total_base_sale_price = 0
    total_offer_discount = 0
    total_final_price_calculated = 0

    for item in items:
        # Based on user feedback: item.price is the "Sale Price" (4900), not the final sold price (2450).
        # We must apply the offer on top of item.price.
        
        mrp = item.original_price * item.quantity
        sale_price = item.price * item.quantity # This is the "Price" to display
        
        total_mrp += mrp
        total_base_sale_price += sale_price
        
        item_offer_disc = 0
        offer_details = None
        
        # Check active offers at order time
        active_offer = Offer.objects.filter(
            (Q(offer_type='Product', product=item.product_variant.product) | 
             Q(offer_type='Category', category=item.product_variant.product.category)),
            start_date__lte=order.created_at,
            end_date__gte=order.created_at
        ).order_by('-discount_percentage').first()
        
        # Fallback: Loose Match if strict fails
        if not active_offer:
             active_offer = Offer.objects.filter(
                (Q(offer_type='Product', product=item.product_variant.product) | 
                 Q(offer_type='Category', category=item.product_variant.product.category))
            ).order_by('-discount_percentage').first()

        if active_offer:
             p = active_offer.discount_percentage
             # Calculate offer amount based on the Sale Price
             item_offer_disc = sale_price * (Decimal(p) / Decimal(100))
             
             offer_details = {
                'name': active_offer.name,
                'type': active_offer.offer_type,
                'percentage': active_offer.discount_percentage
             }
        
        total_offer_discount += item_offer_disc
        total_final_price_calculated += (sale_price - item_offer_disc)

        item.offer_details = offer_details
        item.final_price_display = sale_price - item_offer_disc
        enhanced_items.append(item)

    # Use the calculated final price as the effective "Sold Price" (Subtotal)
    total_sold_price = total_final_price_calculated

    # Calculate Normal Discount (MRP - Sale Price)
    total_normal_discount = total_mrp - total_base_sale_price
    if total_normal_discount < 0: total_normal_discount = 0

    data = {
        'first_name': first_name,
        'order': order,
        'other_orders': other_orders,
        'status_choices': status_choices,
        'items': enhanced_items, 
        'total_mrp': total_mrp,
        'total_base_sale_price': total_base_sale_price,
        'total_normal_discount': total_normal_discount,
        'total_offer_discount': total_offer_discount,
        'total_sold_price': total_sold_price,
    }
    return render(request, 'admin_order_overview.html', data)


@login_required
@admin_required
def update_order_item(request, item_id):
    order_item = get_object_or_404(OrderItem, id=item_id)
    order = order_item.order
    if request.method == 'POST':
        item = get_object_or_404(OrderItem, id=item_id)
        item.status = request.POST.get('status')
        item.admin_note = request.POST.get('admin_note')
        item.is_cancelled = 'True'
        item.save()

        if request.POST.get('status') == 'Returned' and order_item.item_payment_status == 'Paid':
            # refund by proportion
            total_item_price = order_item.price * order_item.quantity
            proportion = total_item_price / (order.total_amount + order.discount)
            allocated_discount = order.discount * proportion
            returned_item_price = order_item.price  * order_item.quantity
            proportional_discount = (allocated_discount / order_item.quantity) * order_item.quantity
            refund_amount = returned_item_price - proportional_discount

            order.total_amount -= refund_amount
            order.subtotal -= order_item.original_price
            order.save()
            if order.payment_method in ['RP', 'WP', 'PP'] or (order.payment_method == 'COD' and order_item.status == 'Delivered'):
                from decimal import Decimal
                wallet, _ = Wallet.objects.get_or_create(user=order.user)
                wallet.refresh_from_db()
                refund_decimal = Decimal(str(refund_amount))
                wallet.balance = wallet.balance + refund_decimal
                wallet.save()
                WalletTransaction.objects.create(
                                wallet=wallet,
                                transaction_type="Cr",
                                amount=refund_decimal,
                                status="Completed",
                                transaction_id="RT" + str(int(time.time()))[-6:] + uuid.uuid4().hex[:4].upper(),
                            )
                order_item.item_payment_status = 'Refunded'
                order_item.save()
        messages.success(request, 'Status updated sucessful')
        return redirect('orders')




# Sales Report Views

@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def sales_report(request):
    report_type = request.GET.get('type', 'monthly') # Default to monthly to show more data initially
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    # Get local date
    local_now = timezone.localtime(timezone.now())
    today = local_now.date()
    
    start_date = today
    end_date = today

    if report_type == 'daily':
        start_date = today
        end_date = today
    elif report_type == 'weekly':
        start_date = today - timedelta(days=7)
        end_date = today
    elif report_type == 'monthly':
        start_date = today.replace(day=1)
        end_date = today
    elif report_type == 'yearly':
        start_date = today.replace(month=1, day=1)
        end_date = today
    elif report_type == 'custom':
        if start_date_str and end_date_str:
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                start_date = today
                end_date = today
        else:
            start_date = today
            end_date = today

    # Create aware datetimes for the range to be precise
    # Start of start_date (00:00:00)
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    # End of end_date (23:59:59.999999)
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    # Filter orders
    # Exclude Cancelled orders for a valid "Sales" report
    orders = Order.objects.filter(
        created_at__range=(start_datetime, end_datetime)
    ).exclude(items__status='Cancelled').distinct().select_related('user').annotate(
        items_discount=Sum((F('items__original_price') - F('items__price')) * F('items__quantity'))
    ).order_by('-created_at')

    # Calculate totals
    total_sales_count = orders.count()
    
    # Aggregate totals
    # We calculate item discounts again in aggregate because iterating over all orders for sum is inefficient
    totals = orders.aggregate(
        total_rev=Sum('total_amount'),
        total_coupon_disc=Sum('discount'),
        total_items_disc=Sum((F('items__original_price') - F('items__price')) * F('items__quantity'))
    )
    
    total_amount = totals['total_rev'] or 0
    # Total Discount = Coupon Discount + Product Offer Discount
    total_discount = (totals['total_coupon_disc'] or 0) + (totals['total_items_disc'] or 0)
    
    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(orders, 10)

    try:
        orders_page = paginator.page(page)
    except PageNotAnInteger:
        orders_page = paginator.page(1)
    except EmptyPage:
        orders_page = paginator.page(paginator.num_pages)

    context = {
        'orders': orders_page,
        'report_type': report_type,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'total_sales_count': total_sales_count,
        'total_amount': total_amount,
        'total_discount': total_discount,
        'first_name': request.user.first_name or request.user.name, 
    }
    
    return render(request, 'sales_report.html', context)


@login_required
@admin_required
def download_report_excel(request):
    report_type = request.GET.get('type', 'daily')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    local_now = timezone.localtime(timezone.now())
    today = local_now.date()
    
    # Priority 1: Use specific dates if provided (from URL or Custom filter)
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            # Fallback if invalid format
            start_date = today
            end_date = today
    # Priority 2: Use Report Type Logic
    else:
        if report_type == 'daily':
            start_date = today
            end_date = today
        elif report_type == 'weekly':
            start_date = today - timedelta(days=7)
            end_date = today
        elif report_type == 'monthly':
            start_date = today.replace(day=1)
            end_date = today
        elif report_type == 'yearly':
            start_date = today.replace(month=1, day=1)
            end_date = today
        else: # custom handled above or fallback
            start_date = today
            end_date = today

    # Create aware datetimes for the range to be precise
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    orders = Order.objects.filter(
        created_at__range=(start_datetime, end_datetime)
    ).exclude(items__status='Cancelled').select_related('user').prefetch_related('items__product_variant__product').annotate(
        items_discount=Sum((F('items__original_price') - F('items__price')) * F('items__quantity'))
    ).distinct().order_by('-created_at')

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = 'attachment; filename="Walkoria_Sales_Report.xlsx"'

    output = BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    
    headers = [
        'Order ID', 'Date', 'Customer', 'Product', 'Variant', 
        'Quantity', 'Unit Price', 'Total Item Price', 
        'Item Discount', 'Coupon Discount', 'Total Order Discount', 'Payable Amount', 'Payment Method', 'Status'
    ]
    
    header_format = workbook.add_format({
        'bold': True,
        'border': 1,
        'bg_color': '#f2f2f2',
        'align': 'center',
        'valign': 'vcenter'
    })
    
    cell_format = workbook.add_format({
        'border': 1,
        'align': 'center',
        'valign': 'vcenter'
    })
    
    # Write headers
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_format)
        worksheet.set_column(col, col, 15)

    row = 1
    for order in orders:
        total_order_discount = (order.discount or 0) + (order.items_discount or 0)
        for item in order.items.all():
            worksheet.write(row, 0, order.order_number, cell_format)
            worksheet.write(row, 1, order.created_at.strftime('%Y-%m-%d'), cell_format)
            worksheet.write(row, 2, order.user.name, cell_format)
            
            product_name = item.product_variant.product.name if item.product_variant else "N/A"
            worksheet.write(row, 3, product_name, cell_format)
            
            variant_info = f"{item.product_variant.size} - {item.product_variant.color}" if item.product_variant else "N/A"
            worksheet.write(row, 4, variant_info, cell_format)
            
            worksheet.write(row, 5, item.quantity, cell_format)
            worksheet.write(row, 6, float(item.price), cell_format)
            worksheet.write(row, 7, float(item.total_price), cell_format) # Item total
            
            # Item discount
            item_disc = (item.original_price - item.price) * item.quantity
            worksheet.write(row, 8, float(item_disc), cell_format)

            # Coupon Discount (Per Order) - Show on every row or just first? Excel usually prefers every row for sorting.
            # But might be confusing if summed. Let's precise: "Coupon Discount (Order Level)"
            worksheet.write(row, 9, float(order.discount), cell_format)
            
            # Total Discount (Item + Coupon)
            worksheet.write(row, 10, float(total_order_discount), cell_format)
            
            # Payable amount per order.
            worksheet.write(row, 11, float(order.total_amount), cell_format)
            
            worksheet.write(row, 12, order.get_payment_method_display(), cell_format)
            worksheet.write(row, 13, item.status, cell_format)
            row += 1

    workbook.close()
    output.seek(0)
    response.write(output.read())
    return response


@login_required
@admin_required
def download_report_pdf(request):
    report_type = request.GET.get('type', 'daily')
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    today = timezone.localtime(timezone.now()).date()
    
    # Priority 1: Use specific dates if provided (from URL or Custom filter)
    if start_date_str and end_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            # Fallback if invalid format
            start_date = today
            end_date = today
    # Priority 2: Use Report Type Logic
    else:
        if report_type == 'daily':
            start_date = today
            end_date = today
        elif report_type == 'weekly':
            start_date = today - timedelta(days=7)
            end_date = today
        elif report_type == 'monthly':
            start_date = today.replace(day=1)
            end_date = today
        elif report_type == 'yearly':
            start_date = today.replace(month=1, day=1)
            end_date = today
        else: # custom handled above or fallback
            start_date = today
            end_date = today

    # Create aware datetimes for the range to be precise
    start_datetime = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    orders = Order.objects.filter(
        created_at__range=(start_datetime, end_datetime)
    ).exclude(items__status='Cancelled').select_related('user').prefetch_related('items__product_variant__product').annotate(
        items_discount=Sum((F('items__original_price') - F('items__price')) * F('items__quantity'))
    ).distinct().order_by('-created_at')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Walkoria_Sales_Report.pdf"'
    
    # Use Landscape for more width
    doc = SimpleDocTemplate(response, pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    elements = []

    styles = getSampleStyleSheet()
    
    # Custom Styles for Professional Look
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=18,
        alignment=TA_CENTER,
        spaceAfter=10,
        textColor=colors.HexColor('#2c3e50')
    )
    
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#7f8c8d')
    )
    
    header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontSize=8,
        fontName='Helvetica-Bold',
        alignment=TA_CENTER,
        textColor=colors.white
    )
    
    cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontSize=7,
        alignment=TA_CENTER,
        textColor=colors.black
    )

    # --- Header Section ---
    elements.append(Paragraph("WALKORIA", title_style))
    elements.append(Paragraph("123 Fashion Street, Kerala, India - 670001", subtitle_style))
    elements.append(Paragraph("Email: support@walkoria.com | Phone: +91 9876543210", subtitle_style))
    elements.append(Spacer(1, 20))
    
    elements.append(Paragraph(f"Sales Report: {start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}", 
        ParagraphStyle('Period', parent=styles['Heading2'], fontSize=12, alignment=TA_CENTER, spaceAfter=15)))

    # Calculate overall totals for the PDF
    totals = orders.aggregate(
        total_rev=Sum('total_amount'),
        total_coupon_disc=Sum('discount'),
        total_items_disc=Sum((F('items__original_price') - F('items__price')) * F('items__quantity'))
    )
    
    total_sales_amount = totals['total_rev'] or 0
    total_discount_amount = (totals['total_coupon_disc'] or 0) + (totals['total_items_disc'] or 0)
    
    # Summary Table
    summary_data = [
        ['Total Revenue', f"Rs. {total_sales_amount:,.2f}"],
        ['Total Discount Given', f"Rs. {total_discount_amount:,.2f}"],
        ['Total Orders', str(orders.count())]
    ]
    summary_table = Table(summary_data, colWidths=[150, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#ecf0f1')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))

    # --- Main Data Table ---
    # Columns: Date | Order ID | Customer | Product | MRP | Sold At | Qty | Disc. | Coupon | Order Total | Status
    headers = ['Date', 'Order #', 'Customer', 'Product', 'MRP', 'Sold At', 'Qty', 'Disc.', 'Coupon', 'Order Total', 'Status']
    table_data = [[Paragraph(h, header_style) for h in headers]]
    
    for order in orders:
        for i, item in enumerate(order.items.all()):
            p_name = item.product_variant.product.name if item.product_variant else "N/A"
            v_info = f" ({item.product_variant.size}-{item.product_variant.color})" if item.product_variant else ""
            full_product_name = p_name + v_info
            
            # Truncate to fit column
            if len(full_product_name) > 30:
                full_product_name = full_product_name[:27] + "..."

            # Calculations
            mrp_val = item.original_price
            sold_val = item.price
            qty_val = item.quantity
            
            # Use Order Total Amount (Final Paid Amount) & Coupon
            # Show ONLY on the first item row for the order to avoid confusion
            if i == 0:
                order_total_disp = f"Rs.{order.total_amount:,.2f}"
                coupon_disp = f"Rs.{order.discount:,.2f}" if order.discount > 0 else "-"
                order_id_disp = str(order.order_number)
                date_disp = order.created_at.strftime('%Y-%m-%d')
                customer_disp = order.user.name
            else:
                order_total_disp = "" 
                coupon_disp = ""
                order_id_disp = ""
                date_disp = ""
                customer_disp = ""
            
            # Context rows
            order_id_disp = str(order.order_number)
            date_disp = order.created_at.strftime('%Y-%m-%d')
            customer_disp = order.user.name

            # Item Discount
            item_discount_val = (mrp_val - sold_val) * qty_val
            
            # Formatting
            mrp_disp = f"Rs.{mrp_val:,.2f}"
            sold_disp = f"Rs.{sold_val:,.2f}"
            disc_disp = f"Rs.{item_discount_val:,.2f}"
            
            # Highlight discount if exists
            if item_discount_val > 0:
                disc_paragraph = Paragraph(f"<font color='green'>{disc_disp}</font>", cell_style)
            else:
                disc_paragraph = Paragraph("-", cell_style)

            # Highlight coupon if exists
            if i == 0 and order.discount > 0:
                 coupon_paragraph = Paragraph(f"<font color='blue'>{coupon_disp}</font>", cell_style)
            elif i == 0:
                 coupon_paragraph = Paragraph("-", cell_style)
            else:
                 coupon_paragraph = Paragraph("", cell_style)

            table_data.append([
                Paragraph(date_disp, cell_style),
                Paragraph(order_id_disp, cell_style),
                Paragraph(customer_disp, cell_style),
                Paragraph(full_product_name, cell_style),
                Paragraph(mrp_disp, cell_style),
                Paragraph(sold_disp, cell_style),
                Paragraph(str(qty_val), cell_style),
                disc_paragraph,
                coupon_paragraph,
                Paragraph(order_total_disp, cell_style), # Order Total
                Paragraph(item.status, cell_style)
            ])

    # Define table style
    table_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')), # Modern dark header
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.lightgrey),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
    ])

    # Add alternating row colors
    for i in range(1, len(table_data)):
        if i % 2 == 0:
            bg_color = colors.HexColor('#f8f9fa')
        else:
            bg_color = colors.white
        table_style.add('BACKGROUND', (0, i), (-1, i), bg_color)

    # Column Widths for Landscape 
    # Adjusted for Coupon column
    # Date: 55, Order: 65, Cust: 80, Prod: 140, MRP: 45, Sold: 45, Qty: 25, Disc: 45, Cpn: 45, Total: 55, Status: 60
    col_widths = [55, 65, 80, 140, 45, 45, 25, 45, 45, 55, 60]
    
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(table_style)
    elements.append(t)
    
    doc.build(elements)
    return response
