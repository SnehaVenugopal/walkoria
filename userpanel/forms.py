from django import forms
from django.contrib.auth.hashers import check_password
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from users.models import CustomUser
from userpanel.models import Address
import re



class ProfileUpdateForm(forms.ModelForm):
    first_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        }),
        error_messages={
            'required': 'First name is required.',
            'max_length': 'First name cannot exceed 50 characters.'
        }
    )
    
    last_name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        }),
        error_messages={
            'required': 'Last name is required.',
            'max_length': 'Last name cannot exceed 50 characters.'
        }
    )
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        }),
        error_messages={
            'required': 'Email is required.',
            'invalid': 'Please enter a valid email address.'
        }
    )
    
    mobile_no = forms.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r'^[6-9]\d{9}$',
            message="Mobile number must be 10 digits starting with 6-9."
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your mobile number'
        }),
        error_messages={
            'required': 'Mobile number is required.'
        }
    )
    
    profile_image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        })
    )

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'mobile_no', 'profile_image']

    def clean_first_name(self):
        first_name = self.cleaned_data.get('first_name')
        if not re.match(r"^[A-Za-z]{2,}$", first_name):
            raise ValidationError("First name must contain only letters and be at least 2 characters long.")
        return first_name.title()

    def clean_last_name(self):
        last_name = self.cleaned_data.get('last_name')
        if not re.match(r"^[A-Za-z]{2,}$", last_name):
            raise ValidationError("Last name must contain only letters and be at least 2 characters long.")
        return last_name.title()

    def clean_email(self):
        email = self.cleaned_data.get('email').lower()
        if self.user and CustomUser.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise ValidationError("This email is already registered.")
        return email


class EmailVerificationForm(forms.Form):
    otp = forms.CharField(
        max_length=6,
        min_length=6,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit OTP',
            'maxlength': '6',
            'pattern': '[0-9]{6}',
            'autocomplete': 'one-time-code'
        }),
        error_messages={
            'required': 'OTP is required.',
            'min_length': 'OTP must be 6 digits.',
            'max_length': 'OTP must be 6 digits.'
        }
    )

    def clean_otp(self):
        otp = self.cleaned_data.get('otp')
        if not re.match(r'^\d{6}$', otp):
            raise ValidationError("OTP must be exactly 6 digits.")
        return otp


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your current password'
        }),
        error_messages={
            'required': 'Current password is required.'
        }
    )
    
    new_password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter new password (min 8 characters)'
        }),
        error_messages={
            'required': 'New password is required.',
            'min_length': 'Password must be at least 8 characters long.'
        }
    )
    
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your new password'
        }),
        error_messages={
            'required': 'Please confirm your new password.'
        }
    )

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_old_password(self):
        old_password = self.cleaned_data.get('old_password')
        if not check_password(old_password, self.user.password):
            raise ValidationError("Current password is incorrect.")
        return old_password

    def clean_new_password(self):
        new_password = self.cleaned_data.get('new_password')
        if ' ' in new_password:
            raise ValidationError("Password cannot contain spaces.")
        if len(new_password) < 8:
            raise ValidationError("Password must be at least 8 characters long.")
        return new_password

    def clean(self):
        cleaned_data = super().clean()
        old_password = cleaned_data.get('old_password')
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')

        if new_password and confirm_password:
            if new_password != confirm_password:
                raise ValidationError("New passwords do not match.")
            
            if old_password and check_password(new_password, self.user.password):
                raise ValidationError("New password cannot be the same as current password.")

        return cleaned_data


class AddressForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter full name'
        }),
        error_messages={
            'required': 'Full name is required.',
            'max_length': 'Full name cannot exceed 255 characters.'
        }
    )
    
    mobile_no = forms.CharField(
        max_length=10,
        validators=[RegexValidator(
            regex=r'^[6-9]\d{9}$',
            message="Mobile number must be 10 digits starting with 6-9."
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 10-digit mobile number'
        }),
        error_messages={
            'required': 'Mobile number is required.'
        }
    )
    
    pin_code = forms.CharField(
        max_length=6,
        validators=[RegexValidator(
            regex=r'^\d{6}$',
            message="PIN code must be exactly 6 digits."
        )],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter 6-digit PIN code'
        }),
        error_messages={
            'required': 'PIN code is required.'
        }
    )
    
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'House No, Building, Street, Area'
        }),
        error_messages={
            'required': 'Address is required.'
        }
    )
    
    street = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Street/Road name'
        }),
        error_messages={
            'required': 'Street is required.',
            'max_length': 'Street name cannot exceed 255 characters.'
        }
    )
    
    landmark = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Landmark (optional)'
        })
    )
    
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'City/Town'
        }),
        error_messages={
            'required': 'City is required.',
            'max_length': 'City name cannot exceed 100 characters.'
        }
    )
    
    state = forms.ChoiceField(
        choices=Address.STATE_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select'
        }),
        error_messages={
            'required': 'Please select a state.'
        }
    )
    
    default_address = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        })
    )

    class Meta:
        model = Address
        fields = ['full_name', 'mobile_no', 'pin_code', 'address', 'street', 'landmark', 'city', 'state', 'default_address']

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name')
        if not re.match(r"^[A-Za-z\s]{2,}$", full_name):
            raise ValidationError("Full name must contain only letters and spaces, minimum 2 characters.")
        return full_name.title()

    def clean_city(self):
        city = self.cleaned_data.get('city')
        if not re.match(r"^[A-Za-z\s]{2,}$", city):
            raise ValidationError("City name must contain only letters and spaces, minimum 2 characters.")
        return city.title()
    
    
     # Only check address limit for new addresses (not when editing existing ones)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # Extract user before calling parent
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        
        # Only check address limit for new addresses (not when editing existing ones)
        # Check if instance.pk is None to determine if it's a new address
        if hasattr(self, 'user') and self.user and not self.instance.pk:
            address_count = Address.objects.filter(
                user_id=self.user, 
                is_deleted=False
            ).count()
            
            if address_count >= 4:
                raise ValidationError(
                    "You can only have a maximum of 4 addresses. "
                    "Please delete an existing address to add a new one."
                )
        
        return cleaned_data