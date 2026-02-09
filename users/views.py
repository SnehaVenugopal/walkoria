from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.views.decorators.http import require_POST
from django.conf import settings
import random,datetime
from django.views.decorators.cache import cache_control
from .models import CustomUser
from .forms import SignUpForm
from .forms import LoginForm
from .forms import ResetPasswordForm
from django.http import JsonResponse
import json




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

            # Store all signup data including referral code
            request.session['temp_signup_data'] = form.cleaned_data

            otp = str(random.randint(100000, 999999))
            print('\n' + '='*50)
            print('📧 SIGNUP OTP:', otp)
            print('='*50 + '\n')
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
        # Check if referral code is in URL (e.g., ?ref=ABC123)
        referral_code_from_url = request.GET.get('ref', '')
        
        # Pre-fill the form with referral code if present
        if referral_code_from_url:
            form = SignUpForm(initial={'referral_code': referral_code_from_url.upper()})
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
            
            # Apply referral code if provided
            referral_code = temp_data.get('referral_code', '').strip().upper()
            if referral_code:
                try:
                    from referral.models import Referral
                    from django.utils import timezone as tz
                    
                    referral = Referral.objects.get(referral_code=referral_code, is_used=False)
                    
                    # Mark referral as used
                    referral.referred_user = user
                    referral.is_used = True
                    referral.used_at = tz.now()
                    referral.save()
                    
                    messages.success(request, f"Account verified! You'll receive referral rewards after your first purchase.")
                except Referral.DoesNotExist:
                    # Referral code invalid, but don't block signup
                    messages.warning(request, "Account verified! (Referral code was invalid)")
                except Exception as e:
                    # Log the error but don't block signup
                    print(f"Error applying referral: {e}")
                    messages.success(request, "Account verified successfully!")
            else:
                messages.success(request, "Account verified successfully!")

            # Clear session
            for key in ['signup_otp', 'temp_signup_data', 'otp_created_at']:
                request.session.pop(key, None)

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
        print('\n' + '='*50)
        print('🔄 RESEND SIGNUP OTP:', new_otp)
        print('='*50 + '\n')
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
            # OTP already printed above
        except Exception:
            return JsonResponse({'success': False, 'message': 'Failed to send OTP. Please try again later.'}, status=500)

        return JsonResponse({'success': True, 'message': 'A new OTP has been sent to your email.'})

    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


#login view 

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')
    
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




def _otp_now_iso():
    return timezone.now().isoformat()

def _otp_remaining_seconds(created_iso: str, minutes: int = 1) -> int:
    try:
        created_dt = timezone.datetime.fromisoformat(created_iso)
    except Exception:
        return 0
    expiry_dt = created_dt + timezone.timedelta(minutes=minutes)
    remaining = int((expiry_dt - timezone.now()).total_seconds())
    return max(0, remaining)

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def forgot_password_view(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip().lower()

        if not email:
            messages.error(request, 'Please enter your email address.')
            return render(request, 'forgot_password.html')

        try:
            user = CustomUser.objects.get(email=email)
        except CustomUser.DoesNotExist:
            messages.error(request, 'No account found with that email.')
            return render(request, 'forgot_password.html')

        if user.status == "Blocked":
            messages.error(request, 'Your account is blocked. Please contact support.')
            return render(request, 'forgot_password.html')

        # Generate and store OTP in session
        otp = str(random.randint(100000, 999999))
        request.session['reset_email'] = email
        request.session['reset_otp'] = otp
        request.session['reset_otp_created_at'] = _otp_now_iso()

        # Send email
        subject = 'Walkoria - Password Reset OTP'
        plain_message = f'Your password reset OTP is: {otp}. It expires in 1 minute.'
        html_message = f"""
        <html>
            <body style="font-family: Arial, sans-serif; color: #333;">
                <h2 style="color:#ff429d; margin:0 0 10px;">Password Reset</h2>
                <p style="font-size:16px; margin:0 0 8px;">
                  Your OTP is
                  <strong style="font-size:22px;color:#ff429d;">{otp}</strong>
                </p>
                <p style="font-size:16px;margin:0;">This code expires in 1 minute.</p>
            </body>
        </html>
        """
        print('\n' + '='*50)
        print('🔐 FORGOT PASSWORD OTP:', otp)
        print('='*50 + '\n')
        try:
            send_mail(
                subject,
                plain_message,
                getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                [email],
                fail_silently=False,
                html_message=html_message,
            )
            messages.success(request, 'OTP sent to your email.')
        except Exception:
            messages.error(request, 'Failed to send OTP. Please try again later.')
            return render(request, 'forgot_password.html')

        return redirect('reset_password')

    return render(request, 'forgot_password.html')

@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def reset_password_view(request):
    email = request.session.get('reset_email')
    otp_in_session = request.session.get('reset_otp')
    created_at = request.session.get('reset_otp_created_at')

    if not (email and otp_in_session and created_at):
        messages.error(request, 'Session expired. Please request a new OTP.')
        return redirect('forgot_password')

    remaining_seconds = _otp_remaining_seconds(created_at, minutes=1)

    if request.method == 'POST':
        # Build user-entered OTP from 6 inputs
        user_otp = ''.join([request.POST.get(f'otp{i}', '') for i in range(1, 7)])
        form = ResetPasswordForm(request.POST)

        if remaining_seconds <= 0:
            messages.error(request, 'OTP expired. Please request a new one.')
            return redirect('forgot_password')

        if user_otp != otp_in_session:
            messages.error(request, 'Invalid OTP.')
            return render(request, 'reset_password.html', {'form': form, 'remaining_seconds': remaining_seconds})

        if form.is_valid():
            try:
                user = CustomUser.objects.get(email=email)
            except CustomUser.DoesNotExist:
                messages.error(request, 'Account not found.')
                return redirect('forgot_password')

            new_password = form.cleaned_data['password']
            user.password = make_password(new_password)
            user.save()

            # Clear session
            for key in ['reset_email', 'reset_otp', 'reset_otp_created_at']:
                request.session.pop(key, None)

            messages.success(request, 'Password reset successful. You can now log in.')
            return redirect('login')
        else:
            return render(request, 'reset_password.html', {'form': form, 'remaining_seconds': remaining_seconds})

    form = ResetPasswordForm()
    return render(request, 'reset_password.html', {'form': form, 'remaining_seconds': remaining_seconds})

@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def verify_reset_otp_view(request):
    """
    AJAX endpoint to verify OTP without submitting the full form.
    Returns JSON response indicating success/failure.
    """
    try:
        data = json.loads(request.body)
        user_otp = data.get('otp', '')
    except (json.JSONDecodeError, KeyError):
        return JsonResponse({'success': False, 'message': 'Invalid request.'}, status=400)

    email = request.session.get('reset_email')
    otp_in_session = request.session.get('reset_otp')
    created_at = request.session.get('reset_otp_created_at')

    if not (email and otp_in_session and created_at):
        return JsonResponse({'success': False, 'message': 'Session expired. Please start again.'}, status=400)

    remaining_seconds = _otp_remaining_seconds(created_at, minutes=1)

    if remaining_seconds <= 0:
        return JsonResponse({
            'success': False, 
            'reason': 'expired',
            'message': 'OTP expired. Please resend a new code.'
        })

    if user_otp != otp_in_session:
        return JsonResponse({'success': False, 'message': 'Invalid OTP.'})

    return JsonResponse({'success': True, 'message': 'OTP verified successfully.'})

@require_POST
@cache_control(no_cache=True, must_revalidate=True, no_store=True)
def resend_reset_otp_view(request):
    email = request.session.get('reset_email')
    if not email:
        return JsonResponse({'success': False, 'message': 'Session expired. Please start again.'}, status=400)

    otp = str(random.randint(100000, 999999))
    request.session['reset_otp'] = otp
    request.session['reset_otp_created_at'] = _otp_now_iso()

    subject = 'Walkoria - New Password Reset OTP'
    plain_message = f'Your new password reset OTP is: {otp}. It expires in 1 minute.'
    html_message = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color:#ff429d; margin:0 0 10px;">Password Reset</h2>
            <p style="font-size:16px; margin:0 0 8px;">
              Your new OTP is
              <strong style="font-size:22px;color:#ff429d;">{otp}</strong>
            </p>
            <p style="font-size:16px;margin:0;">This code expires in 1 minute.</p>
        </body>
    </html>
    """
    print('\n' + '='*50)
    print('🔄 RESEND PASSWORD RESET OTP:', otp)
    print('='*50 + '\n')
    try:
        send_mail(
            subject,
            plain_message,
            getattr(settings, 'DEFAULT_FROM_EMAIL', None),
            [email],
            fail_silently=False,
            html_message=html_message,
        )
        return JsonResponse({'success': True, 'message': 'A new OTP has been sent to your email.'})
    except Exception:
        return JsonResponse({'success': False, 'message': 'Failed to resend OTP. Please try again.'}, status=500)


#logout view
def logout_account(request):
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('login')

