from django import forms
from .models import Product, Review, Brand, Category, Specification
from django.forms import inlineformset_factory

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


class ReviewForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        queryset=Product.objects.filter(is_active=True),
        widget=forms.HiddenInput()
    )

    class Meta:
        model = Review
        fields = [
            'product', 'title', 'content', 'rating', 'is_verified_purchase',
            'likes', 'improvements', 'issues', 'recommendation'
        ]
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
            'likes': forms.Textarea(attrs={'rows': 3}),
            'improvements': forms.Textarea(attrs={'rows': 3}),
            'issues': forms.Textarea(attrs={'rows': 3}),
            'recommendation': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if not self.user.is_authenticated:
            self.fields.pop('is_verified_purchase')