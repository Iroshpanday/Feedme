# reviews/forms.py
from django import forms
from .models import Product, Brand, Category,Review

class ProductForm(forms.ModelForm):
    brand_name = forms.CharField(
        max_length=100,
        required=True,
        help_text="Enter brand name (will create new brand if doesn't exist)"
    )

    class Meta:
        model = Product
        fields = ['name', 'category', 'description', 'price', 'image', 'meta_title', 'meta_description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'meta_description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Safer way to check for existing brand
        if self.instance and self.instance.pk:
            try:
                if hasattr(self.instance, 'brand') and self.instance.brand:
                    self.initial['brand_name'] = self.instance.brand.name
            except Brand.DoesNotExist:
                pass  # Brand was deleted or never set


# reviews/forms.py
from django import forms
from .models import Review, Product

# In forms.py, update the ReviewForm
# In forms.py, update the ReviewForm
class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = [
            'product', 'title', 
            'overall_rating', 'performance_rating', 'battery_rating', 
            'camera_rating', 'display_rating', 'value_rating',
            'likes', 'improvements', 'issues', 'recommendation',
            'is_verified_purchase', 'review_video'  # Add this
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'likes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What do you like most about this mobile phone?'}),
            'improvements': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What improvements would you suggest?'}),
            'issues': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any specific issues or problems?'}),
            'recommendation': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Would you recommend this phone? Why or why not?'}),
            'review_video': forms.FileInput(attrs={'accept': 'video/*'})  # Add this
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Initially hide the video field
        self.fields['review_video'].widget.attrs['class'] = 'hidden'
        self.fields['review_video'].required = False
        
        # Filter active products for the dropdown
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        
        if user:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(
                is_active=True
            ).distinct()
    
    def clean(self):
        cleaned_data = super().clean()
        is_verified = cleaned_data.get('is_verified_purchase')
        review_video = cleaned_data.get('review_video')
        
        # Make video required if it's a verified purchase
        if is_verified and not review_video:
            self.add_error('review_video', 'Please upload a video review for verified purchases')
        
        return cleaned_data
    class Meta:
        model = Review
        fields = [
            'product', 'title', 
            'overall_rating', 'performance_rating', 'battery_rating', 
            'camera_rating', 'display_rating', 'value_rating',
            'likes', 'improvements', 'issues', 'recommendation',
            'is_verified_purchase'
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'likes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What do you like most about this mobile phone?'}),
            'improvements': forms.Textarea(attrs={'rows': 3, 'placeholder': 'What improvements would you suggest?'}),
            'issues': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any specific issues or problems?'}),
            'recommendation': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Would you recommend this phone? Why or why not?'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter active products for the dropdown
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        
        if user:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(
                is_active=True
            ).distinct()
    class Meta:
        model = Review
        fields = ['product', 'title', 'content', 'rating', 'is_verified_purchase']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
            'product': forms.Select(attrs={'class': 'form-select'}),
        }
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Filter active products for the dropdown
        self.fields['product'].queryset = Product.objects.filter(is_active=True)
        
        # If user is provided, we can add additional filtering if needed
        if user:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(
                # Optional: You could filter products the user has purchased
                # orders__user=user,
                is_active=True
            ).distinct()