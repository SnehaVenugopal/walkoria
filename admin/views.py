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



