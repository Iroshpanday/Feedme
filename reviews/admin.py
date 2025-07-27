from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    Category, Brand, Product, Review, ReviewHelpful, 
    SearchQuery, ProductView, UserProfile
)
from .models import Specification  

# Add UserProfile inline
class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fk_name = 'user'
    fields = ('profile_picture', 'is_business_user')

# Customize User Admin
class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_business_user')
    list_select_related = ('profile', )

    def is_business_user(self, instance):
        return instance.profile.is_business_user
    is_business_user.short_description = 'Business User'
    is_business_user.boolean = True

    def get_inline_instances(self, request, obj=None):
        if not obj:
            return list()
        return super().get_inline_instances(request, obj)

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'product_count', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active']
    
    def product_count(self, obj):
        return obj.product_count
    product_count.short_description = 'Products'

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ['name', 'logo_preview', 'website', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active']
    
    def logo_preview(self, obj):
        if obj.logo:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius: 50%;" />',
                obj.logo.url
            )
        return "No Logo"
    logo_preview.short_description = 'Logo'

class SpecificationInline(admin.TabularInline):
    model = Specification
    extra = 1
    fields = [
        'key', 'value', 'ram', 'storage', 'processor', 'chipset', 'gpu',
        'screen_size', 'resolution', 'refresh_rate', 'display_type',
        'rear_camera', 'front_camera', 'video_recording',
        'battery_capacity', 'network_support', 'wifi', 'bluetooth', 'nfc',
        'dimensions', 'weight', 'fingerprint_sensor', 'face_unlock',
        'operating_system', 'audio_jack'
    ]
    can_delete = True 

class ReviewInline(admin.TabularInline):
    model = Review
    extra = 0
    fields = ['user', 'title', 'overall_rating', 'is_approved', 'created_at', 'review_video_preview']  # ✅ Now uses 'overall_rating'
    readonly_fields = ['created_at', 'review_video_preview']
    can_delete = False
    
    def review_video_preview(self, obj):
        if obj.review_video:
            return format_html(
                '<video width="100" height="60" controls><source src="{}" type="video/mp4">Your browser does not support the video tag.</video>',
                obj.review_video.url
            )
        return "No Video"
    review_video_preview.short_description = 'Video'

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'brand', 'category', 'price', 'image_preview', 
        'average_rating', 'total_reviews', 'view_count', 'is_active', 'is_featured'
    ]
    list_filter = [
        'category', 'brand', 'is_active', 'is_featured', 'created_at'
    ]
    search_fields = ['name', 'description', 'brand__name']
    prepopulated_fields = {'slug': ('name',)}
    list_editable = ['is_active', 'is_featured', 'price']
    inlines = [ReviewInline, SpecificationInline]  # ✅ Combined into one line (no duplication)
    autocomplete_fields = ['brand']  # Optional: Adds search for brands
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'slug', 'brand', 'category', 'description', 'price', 'image')
        }),
        ('SEO', {
            'fields': ('meta_title', 'meta_description'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active', 'is_featured', 'view_count')
        }),
    )
    
    readonly_fields = ['view_count']

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 8px;" />',
                obj.image.url
            )
        return "No Image"
    image_preview.short_description = 'Image'
    
    def average_rating(self, obj):
        rating = obj.average_rating
        if rating is None:
            return "No ratings"
        stars = '★' * int(rating) + '☆' * (5 - int(rating))
        return format_html(
            '<span style="color: #f59e0b;">{}</span> ({})',
            stars,
            "{:.1f}".format(float(rating))
        )
        
    def total_reviews(self, obj):
        count = obj.total_reviews
        if count > 0:
            url = reverse('admin:reviews_review_changelist') + f'?product__id__exact={obj.id}'
            return format_html('<a href="{}">{} reviews</a>', url, count)
        return "0 reviews"
    total_reviews.short_description = 'Reviews'

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'product_link', 'user', 'user_profile_picture_display', 
        'overall_rating_stars', 'is_approved', 'is_verified_purchase', 
        'helpful_count', 'created_at'
    ]
    list_filter = [
        'overall_rating', 'is_approved', 'is_verified_purchase', 'created_at', 
        'product__category', 'product__brand'
    ]

    search_fields = ['title', 'content', 'user__username', 'product__name']
    list_editable = ['is_approved', 'is_verified_purchase']
    date_hierarchy = 'created_at'
    
    fieldsets = (
        ('Review Details', {
            'fields': (
                'product', 'user', 'title', 'content', 'rating',
                'overall_rating', 'performance_rating', 'battery_rating',
                'camera_rating', 'display_rating', 'value_rating'
            )
        }),
        ('Feedback', {
            'fields': ('likes', 'improvements', 'issues', 'recommendation'),
            'classes': ('collapse',)
        }),
        ('Media', {
            'fields': ('review_video', 'review_video_preview'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_approved', 'is_verified_purchase', 'helpful_count')
        }),
    )
    
    readonly_fields = ['helpful_count', 'review_video_preview']

    def user_profile_picture_display(self, obj):
        if obj.user_profile_picture:
            return format_html(
                '<img src="{}" width="30" height="30" style="border-radius: 50%;" />',
                obj.user_profile_picture.url
            )
        return "No Image"
    user_profile_picture_display.short_description = 'Profile Picture'
    
    def product_link(self, obj):
        url = reverse('admin:reviews_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'
    
    def overall_rating_stars(self, obj):
        # Use overall_rating instead of rating
        rating = obj.overall_rating
        if rating is None:
            return "No rating"
        stars = '★' * rating + '☆' * (5 - rating)
        return format_html('<span style="color: #f59e0b;">{}</span>', stars)
    overall_rating_stars.short_description = 'Overall Rating'

    def rating_stars(self, obj):
        if obj.rating is None:
            return "No rating"
        stars = '★' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #f59e0b;">{}</span>', stars)
    rating_stars.short_description = 'Rating'
    
    def review_video_preview(self, obj):
        if obj.review_video:
            return format_html(
                '<video width="320" height="240" controls><source src="{}" type="video/mp4">Your browser does not support the video tag.</video>',
                obj.review_video.url
            )
        return "No Video"
    review_video_preview.short_description = 'Video Preview'
    
    actions = ['approve_reviews', 'disapprove_reviews']
    
    def approve_reviews(self, request, queryset):
        updated = queryset.update(is_approved=True)
        self.message_user(request, f'{updated} reviews were approved.')
    approve_reviews.short_description = 'Approve selected reviews'
    
    def disapprove_reviews(self, request, queryset):
        updated = queryset.update(is_approved=False)
        self.message_user(request, f'{updated} reviews were disapproved.')
    disapprove_reviews.short_description = 'Disapprove selected reviews'

@admin.register(ReviewHelpful)
class ReviewHelpfulAdmin(admin.ModelAdmin):
    list_display = ['review_title', 'user', 'created_at']
    list_filter = ['created_at']
    search_fields = ['review__title', 'user__username']
    
    def review_title(self, obj):
        return obj.review.title
    review_title.short_description = 'Review'

@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ['query', 'user', 'results_count', 'ip_address', 'created_at']
    list_filter = ['results_count', 'created_at']
    search_fields = ['query', 'user__username']
    date_hierarchy = 'created_at'
    readonly_fields = ['query', 'user', 'results_count', 'ip_address', 'created_at']
    
    def has_add_permission(self, request):
        return False

@admin.register(ProductView)
class ProductViewAdmin(admin.ModelAdmin):
    list_display = ['product_link', 'category', 'user_info', 'ip_address', 'view_date']
    list_filter = ['created_at', 'product__category', 'product__brand']
    search_fields = ['product__name', 'user__username', 'ip_address']
    date_hierarchy = 'created_at'
    readonly_fields = ['product', 'user', 'ip_address', 'user_agent', 'created_at', 'device_info']
    
    fieldsets = (
        ('View Information', {
            'fields': ('product', 'user', 'created_at')
        }),
        ('Technical Details', {
            'fields': ('ip_address', 'user_agent', 'device_info'),
            'classes': ('collapse',)
        }),
    )
    
    def product_link(self, obj):
        url = reverse('admin:reviews_product_change', args=[obj.product.id])
        return format_html('<a href="{}">{}</a>', url, obj.product.name)
    product_link.short_description = 'Product'
    
    def category(self, obj):
        return obj.product.category.name
    category.short_description = 'Category'
    
    def user_info(self, obj):
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return "Anonymous"
    user_info.short_description = 'User'
    
    def view_date(self, obj):
        return obj.created_at.strftime("%b %d, %Y %H:%M")
    view_date.short_description = 'View Date'
    view_date.admin_order_field = 'created_at'
    
    def device_info(self, obj):
        if obj.user_agent:
            from user_agents import parse
            ua = parse(obj.user_agent)
            return format_html(
                '<strong>Device:</strong> {}<br>'
                '<strong>OS:</strong> {}<br>'
                '<strong>Browser:</strong> {}',
                ua.device.family if ua.device.family != "Other" else "Desktop",
                ua.os.family,
                ua.browser.family
            )
        return "Unknown"
    device_info.short_description = 'Device Details'
    
    def has_add_permission(self, request):
        return False
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('product__category', 'product__brand', 'user')