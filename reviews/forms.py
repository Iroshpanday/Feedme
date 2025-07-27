from django import forms
from .models import Product, Review, Brand, Category, Specification, UserProfile
from django.forms import inlineformset_factory
from allauth.account.forms import SignupForm
import os


from django import forms
from django.contrib.auth.models import User
from .models import UserProfile

class ProfileUpdateForm(forms.ModelForm):
    """Form for updating user profile information"""
    
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email']
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter username'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter first name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter last name'
            }),
            'email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter email address'
            }),
        }

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise forms.ValidationError("This username is already taken.")
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.exclude(pk=self.instance.pk).filter(email=email).exists():
            raise forms.ValidationError("This email is already registered.")
        return email

class UserProfileForm(forms.ModelForm):
    """Form for updating UserProfile model"""
    
    class Meta:
        model = UserProfile
        fields = ['profile_picture', 'is_business_user']
        widgets = {
            'profile_picture': forms.FileInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'accept': 'image/*'
            }),
            'is_business_user': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }, choices=[
                (False, 'Personal Account'),
                (True, 'Business Account')
            ])
        }

    def clean_profile_picture(self):
        picture = self.cleaned_data.get('profile_picture')
        if picture:
            # Check file size (max 5MB)
            if picture.size > 5 * 1024 * 1024:
                raise forms.ValidationError("Image file too large (max 5MB)")
            
            # Check file type
            allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if picture.content_type not in allowed_types:
                raise forms.ValidationError("Invalid image format. Please use JPEG, PNG, GIF, or WebP.")
        
        return picture

class ReviewEditForm(forms.ModelForm):
    """Enhanced form for editing reviews"""
    
    class Meta:
        model = Review
        fields = [
            'title', 'content', 'overall_rating', 'performance_rating',
            'battery_rating', 'camera_rating', 'display_rating', 'value_rating',
            'likes', 'improvements', 'issues', 'recommendation'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'placeholder': 'Enter review title'
            }),
            'content': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 4,
                'placeholder': 'Write your detailed review...'
            }),
            'overall_rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'performance_rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'battery_rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'camera_rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'display_rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'value_rating': forms.Select(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500'
            }),
            'likes': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 2,
                'placeholder': 'What do you like most about this product?'
            }),
            'improvements': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 2,
                'placeholder': 'What improvements would you suggest?'
            }),
            'issues': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 2,
                'placeholder': 'Any specific issues or problems?'
            }),
            'recommendation': forms.Textarea(attrs={
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500',
                'rows': 2,
                'placeholder': 'Would you recommend this product? Why or why not?'
            }),
        }

class CustomSignupForm(SignupForm):
    """Custom signup form with business user checkbox"""
    is_business_user = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'business-user-checkbox'
        }),
        label='I am signing up as a business user'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Add custom styling to existing fields
        self.fields['email'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Enter your email address'
        })
        self.fields['username'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm your password'
        })

    def save(self, request):
        user = super().save(request)
        # Create or update user profile with business user flag
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'is_business_user': self.cleaned_data.get('is_business_user', False)}
        )
        if not created:
            profile.is_business_user = self.cleaned_data.get('is_business_user', False)
            profile.save()
        return user

class UserTypeForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['is_business_user']
        widgets = {
            'is_business_user': forms.CheckboxInput(attrs={
                'class': 'form-check-input',
                'id': 'business-user-checkbox'
            })
        }
        labels = {
            'is_business_user': 'Register as a Business User'
        }

from django import forms
from .models import Product, Specification

class ProductForm(forms.ModelForm):
    brand_name = forms.CharField(max_length=100, required=True, label='Brand Name')
    category = forms.ModelChoiceField(queryset=Category.objects.filter(is_active=True), required=True)
    
    # Specification fields
    ram = forms.CharField(max_length=50, initial='4 GB')
    storage = forms.CharField(max_length=50, initial='128 GB')
    processor = forms.CharField(max_length=100, initial='Unknown Processor')
    rear_camera = forms.CharField(max_length=200, initial='Unknown Camera')
    
    # Optional fields (will be handled in the view)
    screen_size = forms.CharField(max_length=50, required=False)
    resolution = forms.CharField(max_length=100, required=False)
    refresh_rate = forms.CharField(max_length=50, required=False)
    display_type = forms.CharField(max_length=100, required=False)
    front_camera = forms.CharField(max_length=200, required=False)
    video_recording = forms.CharField(max_length=200, required=False)
    battery_capacity = forms.CharField(max_length=100, required=False)
    network_support = forms.CharField(max_length=200, required=False)
    wifi = forms.CharField(max_length=100, required=False)
    bluetooth = forms.CharField(max_length=100, required=False)
    nfc = forms.BooleanField(required=False)
    dimensions = forms.CharField(max_length=100, required=False)
    weight = forms.CharField(max_length=50, required=False)
    fingerprint_sensor = forms.CharField(max_length=100, required=False)
    face_unlock = forms.BooleanField(required=False)
    operating_system = forms.CharField(max_length=100, required=False)
    audio_jack = forms.BooleanField(required=False)

    class Meta:
        model = Product
        fields = [
            'name', 'category', 'description', 'price', 'image',
            'meta_title', 'meta_description', 'is_active', 'is_featured'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'meta_description': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_brand_name(self):
        return self.cleaned_data['brand_name'].strip()
    
class ProductEditForm(ProductForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            # Set initial brand name from existing product
            self.fields['brand_name'].initial = self.instance.brand.name
            
            
            spec = self.instance.specifications.first()
            if spec:
                # Required specifications
                self.fields['ram'].initial = spec.ram
                self.fields['storage'].initial = spec.storage
                self.fields['processor'].initial = spec.processor or 'Unknown Processor'
                self.fields['rear_camera'].initial = spec.rear_camera or 'Unknown Camera'
                
                # Optional specifications
                self.fields['screen_size'].initial = spec.screen_size
                self.fields['resolution'].initial = spec.resolution
                self.fields['refresh_rate'].initial = spec.refresh_rate
                self.fields['display_type'].initial = spec.display_type
                self.fields['front_camera'].initial = spec.front_camera
                self.fields['video_recording'].initial = spec.video_recording
                self.fields['battery_capacity'].initial = spec.battery_capacity
                self.fields['network_support'].initial = spec.network_support
                self.fields['wifi'].initial = spec.wifi
                self.fields['bluetooth'].initial = spec.bluetooth
                self.fields['nfc'].initial = spec.nfc
                self.fields['dimensions'].initial = spec.dimensions
                self.fields['weight'].initial = spec.weight
                self.fields['fingerprint_sensor'].initial = spec.fingerprint_sensor
                self.fields['face_unlock'].initial = spec.face_unlock
                self.fields['operating_system'].initial = spec.operating_system
                self.fields['audio_jack'].initial = spec.audio_jack

class SpecificationForm(forms.ModelForm):
    class Meta:
        model = Specification
        fields = ['key', 'value']
        widgets = {
            'key': forms.TextInput(attrs={'class': 'form-control'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
        }

SpecificationFormSet = inlineformset_factory(
    Product,
    Specification,
    form=SpecificationForm,
    extra=5,
    can_delete=True
)

import logging
logger = logging.getLogger(__name__)

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = [
            'product', 'title', 'content', 'overall_rating',
            'performance_rating', 'battery_rating', 'camera_rating',
            'display_rating', 'value_rating', 'likes', 'improvements',
            'issues', 'recommendation', 'review_video', 'is_verified_purchase'
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control'}),
            'overall_rating': forms.HiddenInput(),
            'performance_rating': forms.HiddenInput(),
            'battery_rating': forms.HiddenInput(),
            'camera_rating': forms.HiddenInput(),
            'display_rating': forms.HiddenInput(),
            'value_rating': forms.HiddenInput(),
            'likes': forms.Textarea(attrs={'class': 'form-control'}),
            'improvements': forms.Textarea(attrs={'class': 'form-control'}),
            'issues': forms.Textarea(attrs={'class': 'form-control'}),
            'recommendation': forms.Textarea(attrs={'class': 'form-control'}),
            'review_video': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_verified_purchase': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, instance=None, **kwargs):
        super(ReviewForm, self).__init__(*args, instance=instance, **kwargs)
        self.user = user
        if user:
            self.fields['product'].queryset = Product.objects.filter(is_active=True)
            self.fields['product'].required = True
        
        # Make required fields explicit
        self.fields['title'].required = True
        self.fields['content'].required = True
        self.fields['overall_rating'].required = True
        
        # Set initial values for all ratings when editing
        if instance:
            self.initial['overall_rating'] = instance.overall_rating or 0
            self.initial['performance_rating'] = instance.performance_rating or 0
            self.initial['battery_rating'] = instance.battery_rating or 0
            self.initial['camera_rating'] = instance.camera_rating or 0
            self.initial['display_rating'] = instance.display_rating or 0
            self.initial['value_rating'] = instance.value_rating or 0

    def save(self, commit=True):
        review = super().save(commit=False)
        if self.user:
            review.user = self.user
        
        # Ensure all ratings are properly set
        review.overall_rating = self.cleaned_data.get('overall_rating', 0)
        review.performance_rating = self.cleaned_data.get('performance_rating', 0)
        review.battery_rating = self.cleaned_data.get('battery_rating', 0)
        review.camera_rating = self.cleaned_data.get('camera_rating', 0)
        review.display_rating = self.cleaned_data.get('display_rating', 0)
        review.value_rating = self.cleaned_data.get('value_rating', 0)
        
        if not self.cleaned_data.get('is_verified_purchase', False):
            review.review_video = None
        
        if commit:
            review.save()
        return review