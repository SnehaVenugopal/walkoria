from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.conf import settings
import random,datetime
from django.views.decorators.cache import cache_control
from .models import CustomUser
from .forms import SignUpForm
from .forms import LoginForm
from .forms import ResetPasswordForm
from django.http import JsonResponse



#user signup view

def signup_view(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            mobile = form.cleaned_data['mobile_no']
            

            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, 'Email is already registered.')
                return render(request, 'signup.html', {'form': form})

            if CustomUser.objects.filter(mobile_no=mobile).exists():
                messages.error(request, 'Mobile number is already registered.')
                return render(request, 'signup.html', {'form': form})

            request.session['temp_signup_data'] = form.cleaned_data

            otp = str(random.randint(100000, 999999))
            print('hfgjh',otp)
            request.session['signup_otp'] = otp
            request.session['otp_created_at'] = timezone.now().isoformat()

            subject = 'Walkoria - Your OTP Code'
            message = f"Hi {form.cleaned_data['name']},\n\nYour OTP is {otp}. It expires in 1 minute.\n\nThank you!"
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])

            return redirect('verify_otp')
        else:
            print("Form errors:", form.errors) 
            # The form will automatically show field-specific errors
            return render(request, 'signup.html', {'form': form})
    else:
        form = SignUpForm()
        return render(request, 'signup.html', {'form': form})
    
    

#otp 
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def verify_otp_view(request):
    otp_from_session = request.session.get('signup_otp')
    temp_data = request.session.get('temp_signup_data')
    created_at = request.session.get('otp_created_at')

    if not otp_from_session or not temp_data or not created_at:
        messages.error(request, "Session expired. Please sign up again.")
        return redirect('signup')
    
    created_time = timezone.datetime.fromisoformat(created_at)
    expiry_time = timezone.datetime.fromisoformat(created_at) + timezone.timedelta(minutes=1)
    is_expired = timezone.now() > expiry_time

    if request.method == 'POST':
        if is_expired:
            messages.error(request, "OTP expired. Please sign up again.")
            return redirect('signup')

        user_otp = ''.join([request.POST.get(f'otp{i}', '') for i in range(1, 7)])

        if user_otp == otp_from_session:
            user = CustomUser.objects.create(
                username=temp_data['email'].split('@')[0],
                email=temp_data['email'],
                mobile_no=temp_data['mobile_no'],
                name=temp_data['name'],
                password=make_password(temp_data['password']),
                is_active=True
            )

            # Clear session
            for key in ['signup_otp', 'temp_signup_data', 'otp_created_at']:
                request.session.pop(key, None)

            messages.success(request, "Account verified successfully!")
            return redirect('login')
        else:
            messages.error(request, "Invalid OTP.")

    elif is_expired:
        messages.error(request, "OTP expired. Please sign up again.")
        return redirect('signup')

    # return render(request, 'verify_otp.html', {
    #     'otp_expiry': expiry_time.isoformat()
    # })

    now = timezone.now()
    remaining_seconds = max(0, int((expiry_time - now).total_seconds()))

    return render(request, 'verify_otp.html', {
        'otp_expiry': expiry_time.isoformat(),
        'remaining_seconds': remaining_seconds,
        'is_expired': is_expired
    })




#resend otp view

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def resend_otp_view(request):
    """
    Resend OTP during signup verification.
    Generates a new OTP, updates session, and sends it to the user's email.
    Returns a JSON response for AJAX calls.
    """
    if request.method == 'POST':
        # Get the stored temp signup data
        temp_data = request.session.get('temp_signup_data')
        if not temp_data:
            return JsonResponse({'success': False, 'message': 'Session expired. Please sign up again.'}, status=400)

        # Generate a new OTP
        new_otp = str(random.randint(100000, 999999))
        print(new_otp,"ggdghgfrrrrrrrrrr")
        request.session['signup_otp'] = new_otp
        request.session['otp_created_at'] = timezone.now().isoformat()

        # Prepare email
        name = temp_data.get('name', 'User')
        subject = 'Walkoria - Your New OTP Code'
        plain_message = f"Hi {name},\n\nYour new OTP is {new_otp}. It expires in 1 minute.\n\nThank you!"
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">
                <div style="max-width: 600px; margin: auto; border: 1px solid #ddd; border-radius: 8px; padding: 20px; background-color: #f9f9f9;">
                    <h2 style="color: #4CAF50; text-align: center;">Email Verification</h2>
                    <p style="font-size: 16px;">Dear {name.title()},</p>
                    <p style="font-size: 16px;">
                        Your new OTP for verification is:
                        <strong style="font-size: 22px; color: #ff0000;">{new_otp}</strong>
                        <br>This code will expire in 1 minute.
                    </p>
                    <p style="font-size: 16px;">If you didn’t request this, no action is needed.</p>
                    <p style="font-size: 16px;">Best regards,<br>Walkoria Team</p>
                </div>
            </body>
        </html>
        """

        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [temp_data['email']],
                fail_silently=False,
                html_message=html_message
            )
            print('hfgjh',new_otp)
        except Exception:
            return JsonResponse({'success': False, 'message': 'Failed to send OTP. Please try again later.'}, status=500)

        return JsonResponse({'success': True, 'message': 'A new OTP has been sent to your email.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


#login view 

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data.get('email')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, email=email, password=password)
            if user is not None:
                if user.status == 'Blocked':
                    messages.error(request, 'Your account is blocked, please contact customer care!')
                else:
                    login(request, user)
                    messages.success(request, f"Welcome back, {user.name.title()}!")
                    return redirect('home')
            else:
                messages.error(request, 'Invalid email or password.')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = LoginForm()

    return render(request, 'login.html', {'form': form})


otp_storage = {}
def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        try:
            user = CustomUser.objects.get(email=email)
            otp = str(random.randint(100000, 999999))
            otp_storage[email] = {
                'otp': otp,
                'timestamp': timezone.now()
            }
            send_mail(
                'Your OTP for Password Reset',
                f'Your OTP is: {otp}',
                'admin@yourapp.com',
                [email],
                fail_silently=False,
            )
            request.session['reset_email'] = email
            messages.success(request, 'OTP sent to your email.')
            return redirect('forgot_pass_otp')
        except CustomUser.DoesNotExist:
            messages.error(request, 'Email not found.')

    return render(request, 'forgot_pass.html')


#Verify OTP for forgot password

def forgot_pass_verify_otp(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_pass')

    if request.method == 'POST':
        entered_otp = request.POST.get('otp')
        stored = otp_storage.get(email)
        if stored and stored['otp'] == entered_otp:
            otp_time = stored['timestamp']
            if timezone.now() - otp_time <= datetime.timedelta(minutes=1):
                messages.success(request, 'OTP verified.')
                return redirect('reset_password')
            else:
                messages.error(request, 'OTP expired.')
        else:
            messages.error(request, 'Invalid OTP.')

    return render(request, 'forgot_pass_otp.html')



# Step 3: Reset Password
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def reset_password(request):
    email = request.session.get('reset_email')
    if not email:
        return redirect('forgot_password')

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            password = form.cleaned_data['password']
            user = CustomUser.objects.get(email=email)
            user.password = make_password(password)
            user.save()
            del request.session['reset_email']
            otp_storage.pop(email, None)
            messages.success(request, 'Password reset successful. Please login.')
            return redirect('login')
    else:
        form = ResetPasswordForm()

    return render(request, 'reset_pass.html', {'form': form})

#homepage view
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
# @login_required
# def home_view(request):
#     return render(request, 'home.html')


# views.py
# @cache_control(no_cache=True, must_revalidate=True, no_store=True)
# def landing_page(request):
#     return render(request, 'landing.html')



def logout_account(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

