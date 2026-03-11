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


# ---------------------------------------------------------------------------
# Email helper utilities
# ---------------------------------------------------------------------------

def _build_registration_otp_email(name: str, otp: str, is_resend: bool = False):
    """Return (subject, plain_message, html_message) for registration OTP emails.
    Both the initial send and resend use this same template.
    """
    subject = 'Walkoria – Verify Your Email Address'
    action_note = 'Here is your new verification code:' if is_resend else 'To complete your registration, enter the verification code below:'
    plain_message = (
        f"Hi {name},\n\n"
        f"Welcome to Walkoria!\n\n"
        f"{action_note}\n\n"
        f"  OTP: {otp}\n\n"
        f"This code expires in 1 minute. Do NOT share it with anyone.\n\n"
        f"If you did not create a Walkoria account, please ignore this email.\n\n"
        f"– The Walkoria Team"
    )
    html_message = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,Helvetica,sans-serif;color:#333;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:32px 0;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">

            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(135deg,#ff429d,#ff6eb4);padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#fff;font-size:26px;letter-spacing:1px;">Walkoria</h1>
                <p style="margin:6px 0 0;color:rgba(255,255,255,.85);font-size:13px;">Your Fashion Destination</p>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:36px 40px;">
                <p style="font-size:16px;margin:0 0 8px;">Hi <strong>{name.title()}</strong>,</p>
                <p style="font-size:15px;color:#555;margin:0 0 24px;">Welcome to Walkoria! {action_note}</p>

                <!-- OTP box -->
                <div style="text-align:center;background:#fff5fa;border:2px dashed #ff429d;border-radius:10px;padding:24px 20px;margin:0 0 28px;">
                  <p style="margin:0 0 6px;font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;">Your One-Time Password</p>
                  <span style="font-size:40px;font-weight:700;letter-spacing:10px;color:#ff429d;">{otp}</span>
                  <p style="margin:12px 0 0;font-size:13px;color:#e74c3c;">⏳ Expires in <strong>1 minute</strong></p>
                </div>

                <!-- How to use -->
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9f9f9;border-radius:8px;margin:0 0 24px;">
                  <tr><td style="padding:18px 20px;">
                    <p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#333;">How to verify your account:</p>
                    <ol style="margin:0;padding-left:18px;font-size:14px;color:#555;line-height:1.8;">
                      <li>Return to the Walkoria registration page.</li>
                      <li>Enter the 6-digit OTP shown above.</li>
                      <li>Click <em>Verify</em> to activate your account.</li>
                    </ol>
                  </td></tr>
                </table>

                <!-- Security notice -->
                <p style="font-size:13px;color:#888;background:#fffbe6;border-left:4px solid #f0ad4e;padding:10px 14px;border-radius:4px;margin:0 0 24px;">
                  🔒 <strong>Security tip:</strong> Walkoria will never ask you for this code via phone, chat, or any other means. Do not share it with anyone.
                </p>

                <p style="font-size:14px;color:#555;margin:0;">If you did not create a Walkoria account, you can safely ignore this email. Your email address will not be used without verification.</p>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="background:#f4f4f7;padding:20px 40px;text-align:center;border-top:1px solid #eee;">
                <p style="margin:0;font-size:12px;color:#aaa;">© 2025 Walkoria. All rights reserved.</p>
                <p style="margin:4px 0 0;font-size:12px;color:#aaa;">This is an automated message — please do not reply.</p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    return subject, plain_message, html_message


def _build_password_reset_otp_email(otp: str, is_resend: bool = False):
    """Return (subject, plain_message, html_message) for password-reset OTP emails.
    Both the initial send and resend use this same template.
    """
    subject = 'Walkoria – Password Reset OTP'
    action_note = 'Here is your new password reset code:' if is_resend else 'We received a request to reset the password for your Walkoria account. Use the code below to proceed:'
    plain_message = (
        f"Password Reset Request\n\n"
        f"{action_note}\n\n"
        f"  OTP: {otp}\n\n"
        f"This code expires in 1 minute. Do NOT share it with anyone.\n\n"
        f"If you did not request a password reset, please ignore this email. Your password will remain unchanged.\n\n"
        f"– The Walkoria Team"
    )
    html_message = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
    <body style="margin:0;padding:0;background:#f4f4f7;font-family:Arial,Helvetica,sans-serif;color:#333;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f7;padding:32px 0;">
        <tr><td align="center">
          <table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:10px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08);">

            <!-- Header -->
            <tr>
              <td style="background:linear-gradient(135deg,#ff429d,#ff6eb4);padding:32px 40px;text-align:center;">
                <h1 style="margin:0;color:#fff;font-size:26px;letter-spacing:1px;">Walkoria</h1>
                <p style="margin:6px 0 0;color:rgba(255,255,255,.85);font-size:13px;">Password Reset Request</p>
              </td>
            </tr>

            <!-- Body -->
            <tr>
              <td style="padding:36px 40px;">
                <p style="font-size:15px;color:#555;margin:0 0 24px;">{action_note}</p>

                <!-- OTP box -->
                <div style="text-align:center;background:#fff5fa;border:2px dashed #ff429d;border-radius:10px;padding:24px 20px;margin:0 0 28px;">
                  <p style="margin:0 0 6px;font-size:12px;color:#888;text-transform:uppercase;letter-spacing:1px;">Your One-Time Password</p>
                  <span style="font-size:40px;font-weight:700;letter-spacing:10px;color:#ff429d;">{otp}</span>
                  <p style="margin:12px 0 0;font-size:13px;color:#e74c3c;">⏳ Expires in <strong>1 minute</strong></p>
                </div>

                <!-- How to use -->
                <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9f9f9;border-radius:8px;margin:0 0 24px;">
                  <tr><td style="padding:18px 20px;">
                    <p style="margin:0 0 8px;font-size:14px;font-weight:600;color:#333;">How to reset your password:</p>
                    <ol style="margin:0;padding-left:18px;font-size:14px;color:#555;line-height:1.8;">
                      <li>Return to the Walkoria password reset page.</li>
                      <li>Enter the 6-digit OTP shown above.</li>
                      <li>Set your new password and click <em>Reset</em>.</li>
                    </ol>
                  </td></tr>
                </table>

                <!-- Security notice -->
                <p style="font-size:13px;color:#888;background:#fffbe6;border-left:4px solid #f0ad4e;padding:10px 14px;border-radius:4px;margin:0 0 24px;">
                  🔒 <strong>Security tip:</strong> Walkoria will never ask you for this code via phone, chat, or any other means. Do not share it with anyone.
                </p>

                <p style="font-size:14px;color:#555;margin:0;">If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
              </td>
            </tr>

            <!-- Footer -->
            <tr>
              <td style="background:#f4f4f7;padding:20px 40px;text-align:center;border-top:1px solid #eee;">
                <p style="margin:0;font-size:12px;color:#aaa;">© 2025 Walkoria. All rights reserved.</p>
                <p style="margin:4px 0 0;font-size:12px;color:#aaa;">This is an automated message — please do not reply.</p>
              </td>
            </tr>

          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
    return subject, plain_message, html_message


# ---------------------------------------------------------------------------
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

            subject, plain_message, html_message = _build_registration_otp_email(
                name=form.cleaned_data['name'], otp=otp, is_resend=False
            )
            send_mail(
                subject, plain_message, settings.DEFAULT_FROM_EMAIL, [email],
                fail_silently=False, html_message=html_message
            )

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

        # Prepare and send email using the shared registration template
        name = temp_data.get('name', 'User')
        subject, plain_message, html_message = _build_registration_otp_email(
            name=name, otp=new_otp, is_resend=True
        )

        try:
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [temp_data['email']],
                fail_silently=False,
                html_message=html_message
            )
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

        # Send email using the shared password-reset template
        subject, plain_message, html_message = _build_password_reset_otp_email(otp=otp, is_resend=False)
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

    if request.method == 'POST':
        # Recalculate fresh – the value from GET is stale by submission time
        remaining_seconds = _otp_remaining_seconds(created_at, minutes=1)
        user_otp = ''.join([request.POST.get(f'otp{i}', '') for i in range(1, 7)])
        form = ResetPasswordForm(request.POST)

        if remaining_seconds <= 0:
            messages.error(request, 'OTP expired. Please request a new one.')
            return redirect('forgot_password')

        if user_otp != otp_in_session:
            messages.error(request, 'Invalid OTP. Please check and try again.')
            remaining_seconds = _otp_remaining_seconds(created_at, minutes=1)
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

            for key in ['reset_email', 'reset_otp', 'reset_otp_created_at']:
                request.session.pop(key, None)

            messages.success(request, 'Password reset successful. You can now log in.')
            return redirect('login')
        else:
            remaining_seconds = _otp_remaining_seconds(created_at, minutes=1)
            return render(request, 'reset_password.html', {'form': form, 'remaining_seconds': remaining_seconds})

    remaining_seconds = _otp_remaining_seconds(created_at, minutes=1)
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

    subject, plain_message, html_message = _build_password_reset_otp_email(otp=otp, is_resend=True)
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

