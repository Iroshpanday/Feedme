from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.text import slugify
import uuid


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


class Product(models.Model):
    """Products that can be reviewed"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products')
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name='products')
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to='products/', blank=True, null=True)
    created_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
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
        """Calculate average rating from all reviews"""
        reviews = self.reviews.filter(is_approved=True)
        if reviews.exists():
            return reviews.aggregate(models.Avg('rating'))['rating__avg']
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
        validators=[MinValueValidator(1), MaxValueValidator(5)]
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
        upload_to='review_videos/',
        null=True,
        blank=True,
        help_text="Upload a video review (only available for verified purchases)"
    )
    
    # Add these new fields for open feedback
    likes = models.TextField(blank=True, help_text="What do you like most about this mobile phone?")
    improvements = models.TextField(blank=True, help_text="What improvements would you suggest?")
    issues = models.TextField(blank=True, help_text="Any specific issues or problems?")
    recommendation = models.TextField(blank=True, help_text="Would you recommend this phone? Why or why not?")
    
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
     
     # In models.py, update the Review model
    def save(self, *args, **kwargs):
        # Auto-approve reviews from staff/superusers
        if self.user.is_staff or self.user.is_superuser:
            self.is_approved = True
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