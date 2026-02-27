from .models import CustomUser
from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
import re
from django.utils.translation import gettext_lazy as _

#signup form validation for userside 
class SignUpForm(forms.Form):
    name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    mobile_no = forms.CharField(max_length=10, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True, min_length=8)
    confirm_password = forms.CharField(widget=forms.PasswordInput, required=True)
    referral_code = forms.CharField(
        max_length=20, 
        required=False,  # Optional field
        widget=forms.TextInput(attrs={
            'placeholder': 'Enter referral code (Optional)',
            'class': 'form-control'
        }),
        label='Referral Code (Optional)'
    )

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if not re.match(r"^[A-Za-z]{3,}(?: [A-Za-z]+)*$", name):
            raise ValidationError("Invalid name format. Use only letters and spaces.")
        return name
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if CustomUser.objects.filter(email=email).exists():
            raise ValidationError("Email already exists.")
        return email

    def clean_mobile_no(self):
        mobile = self.cleaned_data.get('mobile_no')
        if not mobile.isdigit() or len(mobile) != 10:
            raise ValidationError("Mobile number must be exactly 10 digits.")
        if CustomUser.objects.filter(mobile_no=mobile).exists():
            raise ValidationError("Mobile number already exists.")
        return mobile

    # def clean(self):
    #     cleaned_data = super().clean()
    #     password = cleaned_data.get('password')
    #     confirm_password = cleaned_data.get('confirm_password')
    #     if (password and " " in password) or (confirm_password and " " in confirm_password):
    #         raise ValidationError("Password should not contain spaces.")
    #     elif (password and re.search(r"\s", password)) or (confirm_password and re.search(r"\s", confirm_password)):
    #         raise ValidationError("Password should not contain spaces or blank characters.")
    #     elif len(password) < 8:
    #         raise ValidationError('Password length should atleast 8 char.')
    #     elif password != confirm_password:
    #         raise ValidationError('Password do not match.')
    #     return password
    
    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')
        referral_code = cleaned_data.get('referral_code')
    
        # 1. Space checks
        if password and re.search(r"\s", password):
            self.add_error('password', "Password should not contain spaces or blank characters.")
    
        if confirm_password and re.search(r"\s", confirm_password):
            self.add_error('confirm_password', "Password should not contain spaces or blank characters.")
    
        # 2. Length check
        if password and len(password) < 8:
            self.add_error('password', "Password length should be at least 8 characters.")
    
        # 3. Match check
        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', "Passwords do not match.")
        
        # 4. Referral code validation (if provided)
        if referral_code:
            from referral.models import Referral
            referral_code = referral_code.strip().upper()
            try:
                referral = Referral.objects.get(referral_code=referral_code, is_used=False)
            except Referral.DoesNotExist:
                self.add_error('referral_code', "Invalid or already used referral code.")
    
        return cleaned_data

    # def clean(self):
    #     cleaned_data = super().clean()
    #     password = cleaned_data.get('password')
    #     confirm_password = cleaned_data.get('confirm_password')
    #     if password and confirm_password and password != confirm_password:
    #         self.add_error('confirm_password',"Passwords do not match.")



#reset password validations 

class ResetPasswordForm(forms.Form):
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password (min 8 characters)'}),
        label='Password',
        error_messages={
            'required': 'New password is required.',
            'min_length': 'Password must be at least 8 characters long.',
        }
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm new password'}),
        label='Confirm Password',
        error_messages={
            'required': 'Please confirm your password.',
        }
    )

    def clean_password(self):
        password = self.cleaned_data.get('password', '')
        if re.search(r'\s', password):
            raise ValidationError('Password must not contain spaces or blank characters.')
        if len(password) < 8:
            raise ValidationError('Password must be at least 8 characters long.')
        return password

    def clean(self):
        cleaned_data = super().clean()
        password        = cleaned_data.get('password', '')
        confirm_password = cleaned_data.get('confirm_password', '')

        if confirm_password and re.search(r'\s', confirm_password):
            self.add_error('confirm_password', 'Password must not contain spaces or blank characters.')

        if password and confirm_password and password != confirm_password:
            self.add_error('confirm_password', 'Passwords do not match.')

        return cleaned_data
            
            
#login part validation

class LoginForm(forms.Form):
    email = forms.EmailField(label="Email", max_length=100)
    password = forms.CharField(label="Password", widget=forms.PasswordInput)
            




