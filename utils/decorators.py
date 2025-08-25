from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth import logout


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        else:
            logout(request)
            messages.error(request, 'You are not authorized to access this page.')
            return redirect('login_to_account')
    return wrapper
