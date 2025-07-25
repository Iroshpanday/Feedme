from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import uuid
from allauth.account.signals import user_signed_up
from allauth.socialaccount.models import SocialAccount
from django.dispatch import receiver



from django.dispatch import receiver
from allauth.account.signals import user_signed_up
from allauth.socialaccount.models import SocialAccount
import urllib.request



from django.conf import settings
import os
from django.core.files import File
from django.core.files.base import ContentFile
from io import BytesIO
import urllib.request
from PIL import Image  # Make sure to install pillow: pip install pillow

class UserProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        blank=True,
        null=True,
        default='profile_pics/default.png'  # Default image path
    )
    is_business_user = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username}'s Profile"

    def save(self, *args, **kwargs):
        if not self.profile_picture:
            self.profile_picture = 'profile_pics/default.png'
        super().save(*args, **kwargs)


@receiver(user_signed_up)
def save_profile_picture(request, user, **kwargs):
    profile, created = UserProfile.objects.get_or_create(user=user)

    social_account = SocialAccount.objects.filter(user=user, provider='google').first()
    
    if social_account:
        picture_url = social_account.extra_data.get('picture')

        if picture_url:
            try:
                result = urllib.request.urlretrieve(picture_url)
                profile.profile_picture.save(
                    f"google_{user.id}.jpg",
                    File(open(result[0], 'rb'))  # ✅ Fixed: Closed parenthesis
                )
            except Exception as e:
                print(f"Failed to download Google profile picture: {e}")
    
    profile.save()


class Category(models.Model):
    """Product categories with icons for the homepage"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    icon = models.CharField(max_length=50, help_text="FontAwesome icon class (e.g., 'fas fa-mobile-alt')")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def product_count_display(self):
        return self.products.filter(is_active=True).count()





class Brand(models.Model):
    """Product brands"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    logo = models.ImageField(upload_to='brands/', blank=True, null=True)
    description = models.TextField(blank=True)
    website = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Specification(models.Model):
    """Product specifications"""
    product = models.ForeignKey('Product', on_delete=models.CASCADE, related_name='specifications')
    ram = models.CharField(max_length=50, default='4 GB')
    processor = models.CharField(max_length=100, default='Unknown Processor')
    camera = models.CharField(max_length=200, default='Unknown Camera')
    display_quality = models.CharField(max_length=200, default='Unknown Display')
    key = models.CharField(max_length=100)
    value = models.CharField(max_length=200)

    class Meta:
        unique_together = ['product', 'key']
        ordering = ['key']

    def __str__(self):
        return f"{self.key}: {self.value}"


class Product(models.Model):
    """Products that can be reviewed"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='created_products'
    )
    
    # SEO and meta fields
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(max_length=300, blank=True)
    
    # Status and tracking
    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)
    view_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['-view_count']),
        ]
      

    def __str__(self):
        return f"{self.brand.name} {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.brand.name}-{self.name}")
        super().save(*args, **kwargs)

    @property
    def average_rating(self):
        """Calculate average rating using overall_rating"""
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(models.Avg('overall_rating'))['overall_rating__avg']
        return 0

    @property
    def total_reviews(self):
        """Get total number of approved reviews"""
        return self.reviews.filter(is_approved=True).count()

    @property
    def recent_popularity_score(self):
        """Calculate recent popularity based on views and reviews in last 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_reviews = self.reviews.filter(
            created_at__gte=thirty_days_ago,
            is_approved=True
        ).count()
        
        # Simple scoring: recent reviews * 10 + view count boost
        return recent_reviews * 10 + (self.view_count / 100)


class Review(models.Model):
    """Product reviews"""
    RATING_CHOICES = [
        (1, '1 Star'),
        (2, '2 Stars'),
        (3, '3 Stars'),
        (4, '4 Stars'),
        (5, '5 Stars'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='reviews')
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],null=True,  # Make it optional
    blank=True
    )
    overall_rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    performance_rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    battery_rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    camera_rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    display_rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    value_rating = models.IntegerField(
        choices=RATING_CHOICES,
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        null=True, blank=True
    )
    review_video = models.FileField(
        upload_to='review_videos/%Y/%m/%d/',
        null=True,
        blank=True,
        help_text="Upload a video review (only available for verified purchases)"
    )
    
    # Add these new fields for open feedback
    likes = models.TextField(blank=True, help_text="What do you like most about this mobile phone?")
    improvements = models.TextField(blank=True, help_text="What improvements would you suggest?")
    issues = models.TextField(blank=True, help_text="Any specific issues or problems?")
    recommendation = models.TextField(blank=True, help_text="Would you recommend this phone? Why or why not?")

    # User profile picture for reviews

    user_profile_picture = models.ImageField(upload_to='review_profile_pics/', blank=True, null=True)

    
    # Review metadata
    is_verified_purchase = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    helpful_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ['product', 'user']  # One review per user per product
        indexes = [
            models.Index(fields=['product', 'is_approved']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['rating']),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product.name} ({self.rating}★)"
     
    def save(self, *args, **kwargs):
        # Auto-approve reviews from staff/superusers
        if self.user.is_staff or self.user.is_superuser:
            self.is_approved = True
            
        # Save profile picture from user's profile
        if hasattr(self.user, 'profile') and self.user.profile.profile_picture:
            self.user_profile_picture = self.user.profile.profile_picture
            
        super().save(*args, **kwargs)

class ReviewHelpful(models.Model):
    """Track which users found reviews helpful"""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name='helpful_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['review', 'user']

    def __str__(self):
        return f"{self.user.username} found {self.review.title} helpful"


class SearchQuery(models.Model):
    """Track search queries for analytics"""
    query = models.CharField(max_length=200)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    results_count = models.PositiveIntegerField(default=0)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Search: {self.query} ({self.results_count} results)"


class ProductView(models.Model):
    """Track product page views"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='product_views')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.product.name} viewed at {self.created_at}"