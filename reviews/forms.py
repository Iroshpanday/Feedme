# reviews/forms.py
from django import forms
from .models import Product, Brand, Category

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
