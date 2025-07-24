from django import forms
from .models import Product, Review, Brand, Category, Specification
from django.forms import inlineformset_factory
import os

class ProductForm(forms.ModelForm):
    brand_name = forms.CharField(max_length=100, required=True, label='Brand Name')
    category = forms.ModelChoiceField(queryset=Category.objects.filter(is_active=True), required=True)

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


# forms.py
from django import forms
from .models import Review, Product
import os

from django import forms
from .models import Review, Product
import logging

logger = logging.getLogger(__name__)

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = [
            'product', 'title', 'content',  'overall_rating',
            'performance_rating', 'battery_rating', 'camera_rating',
            'display_rating', 'value_rating', 'likes', 'improvements',
            'issues', 'recommendation', 'review_video', 'is_verified_purchase'
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'content': forms.Textarea(attrs={'class': 'form-control'}),
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'overall_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'performance_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'battery_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'camera_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'display_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'value_rating': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 5}),
            'likes': forms.Textarea(attrs={'class': 'form-control'}),
            'improvements': forms.Textarea(attrs={'class': 'form-control'}),
            'issues': forms.Textarea(attrs={'class': 'form-control'}),
            'recommendation': forms.Textarea(attrs={'class': 'form-control'}),
            'review_video': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_verified_purchase': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super(ReviewForm, self).__init__(*args, **kwargs)
        self.user = user
        if user:
            products = Product.objects.filter(is_active=True)
            logger.info(f"Product queryset for form: {products}")
            self.fields['product'].queryset = products
            if not products.exists():
                # Fallback: Add a dummy product for debugging if none exist
                from django.db import IntegrityError
                try:
                    from django.contrib.auth import get_user_model
                    User = get_user_model()
                    dummy_product, created = Product.objects.get_or_create(
                        name="Debug Product",
                        defaults={'is_active': True, 'created_by': user}
                    )
                    if created:
                        logger.info(f"Created dummy product: {dummy_product}")
                    self.fields['product'].queryset = Product.objects.filter(is_active=True)
                except IntegrityError:
                    logger.warning("Failed to create dummy product, using existing products")
            self.fields['product'].required = True
        # self.fields['rating'].required = True
        self.fields['title'].required = True
        self.fields['content'].required = True

    def save(self, commit=True):
        review = super().save(commit=False)
        if self.user:
            review.user = self.user
        if commit:
            review.save()
        return review