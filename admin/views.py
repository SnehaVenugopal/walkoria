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
from utils.decorators import admin_required
from django.contrib.auth import logout
from users.models import CustomUser
from django.db.models import Q, Count, Sum
from django.core.exceptions import ObjectDoesNotExist
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from orders.models import Order, OrderItem, ReturnRequest
from django.http import HttpResponse, HttpResponseNotAllowed

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
        print(">>> POST received")
        print(request.POST)  # Check what is received
        try:
            email = request.POST.get('email')
            print(f">>> Email received: {email}")
            user = get_object_or_404(CustomUser, email=email)
            if user.status == 'Blocked':
                user.status = 'Active'
                messages.success(request, f"User {user.name.title()} has been successfully blocked.")
            else:
                user.status = 'Blocked'
                messages.success(request, f"User {user.name.title()} has been successfully unblocked.")
            user.save()
        except ObjectDoesNotExist:
            messages.error(request, "User not found.")
        except Exception as e:
            messages.error(request, f"An unexpected error occurred: {e}")
    return redirect('customers')



@login_required
@admin_required
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def admin_orders(request):
    order_items_list = OrderItem.objects.select_related('order__user', 'product_variant__product').order_by('-order__created_at')
    search_query = request.GET.get('search', '')
    if search_query:
        order_items_list = order_items_list.filter(
            Q(order__order_number__istartswith=search_query) |
            Q(order__user__user_id__istartswith=search_query) |
            Q(product_variant__product__name__istartswith=search_query)
        )
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

            # wallet, _ = Wallet.objects.get_or_create(user=order.user)
            # wallet.balance += int(refund_amount)
            # wallet.save()
            # WalletTransaction.objects.create(
            #                 wallet=wallet,
            #                 transaction_type="Cr",
            #                 amount=refund_amount,
            #                 status="Completed",
            #                 transaction_id="TXN-" + str(int(time.time())) + uuid.uuid4().hex[:4].upper(),
            #             )

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

    data = {
        'first_name': first_name,
        'order': order,
        'other_orders': other_orders,
        'status_choices': status_choices,
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
            # if order.payment_method in ['RP', 'WP'] or (order.payment_method == 'COD' and order_item.status == 'Delivered'):
            #     wallet, _ = Wallet.objects.get_or_create(user=order.user)
            #     wallet.balance += refund_amount
            #     wallet.save()
            #     WalletTransaction.objects.create(
            #                     wallet=wallet,
            #                     transaction_type="Cr",
            #                     amount=refund_amount,
            #                     status="Completed",
            #                     transaction_id="TXN-" + str(int(time.time())) + uuid.uuid4().hex[:4].upper(),
            #                 )
        messages.success(request, 'Status updated sucessful')
        return redirect('orders')



