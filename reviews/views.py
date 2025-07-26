from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse, reverse_lazy
from django.views.generic.edit import CreateView
from django.contrib.auth.mixins import LoginRequiredMixin
from .models import Product, Review, Brand, Specification, Category, SearchQuery, ProductView, UserProfile
from .forms import ReviewForm, ProductForm, SpecificationFormSet
import logging
from django.utils.text import slugify
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


from allauth.account.views import SignupView
from .forms import UserTypeForm

class CustomSignupView(SignupView):
    form_class = UserTypeForm  # Your custom form
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if 'user_type_form' not in context:
            context['user_type_form'] = UserTypeForm()
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # Save user type
        UserProfile.objects.create(
            user=self.user,
            is_business_user=form.cleaned_data.get('is_business_user', False)
        )
        return response

def home_view(request):
    """Home page view with dynamic content"""
    categories = Category.objects.filter(is_active=True).annotate(
        product_count=Count('products', filter=Q(products__is_active=True))
    ).order_by('name')[:12]
    
    top_products = Product.objects.filter(
        is_active=True,
        reviews__is_approved=True
    ).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(
        review_count__gte=1
    ).order_by('-avg_rating', '-review_count')[:4]
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    popular_products = Product.objects.filter(
        is_active=True
    ).annotate(
        recent_reviews=Count(
            'reviews', 
            filter=Q(
                reviews__created_at__gte=thirty_days_ago,
                reviews__is_approved=True
            )
        ),
        recent_views=Count(
            'product_views',
            filter=Q(product_views__created_at__gte=thirty_days_ago)
        ),
        total_review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(
        Q(recent_reviews__gt=0) | Q(recent_views__gt=0)
    ).order_by('-recent_reviews', '-recent_views', '-view_count')[:4]
    
    context = {
        'categories': categories,
        'top_products': top_products,
        'popular_products': popular_products,
    }
    
    return render(request, 'reviews/home.html', context)

def search_view(request):
    """Handle search functionality"""
    query = request.GET.get('q', '').strip()
    results = []
    results_count = 0
    
    if query:
        results = Product.objects.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query),
            is_active=True
        ).select_related('brand', 'category').annotate(
            avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
            review_count=Count('reviews', filter=Q(reviews__is_approved=True))
        ).order_by('-view_count', '-avg_rating')
        
        results_count = results.count()
        
        SearchQuery.objects.create(
            query=query,
            user=request.user if request.user.is_authenticated else None,
            results_count=results_count,
            ip_address=get_client_ip(request)
        )
    
    context = {
        'query': query,
        'results': results,
        'results_count': results_count,
    }
    
    return render(request, 'reviews/search_results.html', context)

def product_detail_view(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # Increment view count
    product.view_count += 1
    product.save(update_fields=['view_count'])
    
    # Track product view
    ProductView.objects.create(
        product=product,
        user=request.user if request.user.is_authenticated else None,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Get all approved reviews
    reviews = Review.objects.filter(
        product=product,
        is_approved=True
    ).select_related('user').order_by('-created_at')
    
    # Calculate rating statistics using overall_rating
    total_reviews = reviews.count()
    rating_distribution = {}
    
    # Calculate rating distribution and percentages using overall_rating
    for i in range(1, 6):
        count = reviews.filter(overall_rating=i).count()
        percentage = (count / total_reviews * 100) if total_reviews > 0 else 0
        rating_distribution[i] = {
            'count': count,
            'percentage': percentage
        }
    
    # Calculate average overall rating
    overall_avg = reviews.exclude(overall_rating=None).aggregate(
        avg=Avg('overall_rating')
    )['avg'] or 0
    
    # Calculate average ratings for different aspects
    aspect_ratings = {}
    aspects = [
        ('overall_rating', 'Overall'),
        ('performance_rating', 'Performance'),
        ('battery_rating', 'Battery Life'),
        ('camera_rating', 'Camera Quality'),
        ('display_rating', 'Display'),
        ('value_rating', 'Value for Money')
    ]
    
    for field, label in aspects:
        reviews_with_rating = reviews.exclude(**{field: None})
        if reviews_with_rating.exists():
            avg = reviews_with_rating.aggregate(
                avg=Avg(field)
            )['avg']
            aspect_ratings[field] = {
                'label': label,
                'average': round(avg, 1) if avg else 0,
                'count': reviews_with_rating.count()
            }
    
    # Get recent reviews (last 6)
    recent_reviews = reviews[:6]
    
    # Check if user has already reviewed
    user_has_reviewed = False
    user_review = None
    if request.user.is_authenticated:
        user_review = Review.objects.filter(
            product=product,
            user=request.user
        ).first()
        user_has_reviewed = user_review is not None
    
    # Initialize review form
    review_form = ReviewForm(user=request.user, instance=user_review)
    review_form.fields['product'].initial = product
    
    # Get product specifications
    specifications = product.specifications.all()
    
    # Get related products (same category)
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True
    ).exclude(id=product.id).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    )[:4]
    
    # Calculate monthly review trends (last 6 months)
    from django.utils import timezone
    from datetime import timedelta
    import calendar
    
    monthly_reviews = []
    for i in range(6):
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=32)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        
        count = reviews.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        monthly_reviews.append({
            'month': calendar.month_name[month_start.month][:3],
            'year': month_start.year,
            'count': count
        })
    
    monthly_reviews.reverse()
    
    # Get review highlights (most helpful and recent)
    helpful_reviews = reviews.filter(helpful_count__gt=0).order_by('-helpful_count')[:3]
    
    context = {
        'product': product,
        'reviews': reviews,
        'recent_reviews': recent_reviews,
        'helpful_reviews': helpful_reviews,
        'rating_distribution': rating_distribution,
        'aspect_ratings': aspect_ratings,
        'average_rating': overall_avg,
        'total_reviews': total_reviews,
        'user_has_reviewed': user_has_reviewed,
        'user_review': user_review,
        'review_form': review_form,
        'review_submitted': 'review_submitted' in request.GET,
        'specifications': specifications,
        'related_products': related_products,
        'monthly_reviews': monthly_reviews,
        'view_count': product.view_count,
    }
    
    return render(request, 'reviews/product_detail.html', context)
def category_view(request, slug):
    category = get_object_or_404(Category, slug=slug, is_active=True)
    
    products = Product.objects.filter(
        category=category,
        is_active=True
    ).select_related('brand').annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).order_by('-view_count', '-avg_rating')
    
    context = {
        'category': category,
        'products': products,
    }
    
    return render(request, 'reviews/category.html', context)

def brand_view(request, slug):
    brand = get_object_or_404(Brand, slug=slug, is_active=True)
    
    products = Product.objects.filter(
        brand=brand,
        is_active=True
    ).select_related('category').annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).order_by('-view_count', '-avg_rating')
    
    context = {
        'brand': brand,
        'products': products,
    }
    
    return render(request, 'reviews/brand.html', context)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@require_POST
@login_required
def mark_review_helpful(request, review_id):
    from .models import ReviewHelpful
    
    try:
        review = get_object_or_404(Review, id=review_id, is_approved=True)
        
        helpful, created = ReviewHelpful.objects.get_or_create(
            review=review,
            user=request.user
        )
        
        if created:
            review.helpful_count += 1
            review.save(update_fields=['helpful_count'])
            return JsonResponse({'status': 'added', 'count': review.helpful_count})
        else:
            helpful.delete()
            review.helpful_count = max(0, review.helpful_count - 1)
            review.save(update_fields=['helpful_count'])
            return JsonResponse({'status': 'removed', 'count': review.helpful_count})
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_GET
def autocomplete_search(request):
    query = request.GET.get('q', '').strip()
    suggestions = []
    
    if query and len(query) >= 2:
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(brand__name__icontains=query),
            is_active=True
        ).select_related('brand')[:5]
        
        for product in products:
            suggestions.append({
                'type': 'product',
                'name': f"{product.brand.name} {product.name}",
                'url': f"/product/{product.slug}/",
                'image': product.image.url if product.image else None
            })
        
        brands = Brand.objects.filter(
            name__icontains=query,
            is_active=True
        )[:3]
        
        for brand in brands:
            suggestions.append({
                'type': 'brand',
                'name': brand.name,
                'url': f"/brand/{brand.slug}/",
                'image': brand.logo.url if brand.logo else None
            })
        
        categories = Category.objects.filter(
            name__icontains=query,
            is_active=True
        )[:3]
        
        for category in categories:
            suggestions.append({
                'type': 'category',
                'name': category.name,
                'url': f"/category/{category.slug}/",
                'icon': category.icon
            })
    
    return JsonResponse({'suggestions': suggestions})

@require_POST
def autocomplete_brands(request):
    query = request.GET.get('q', '').strip()
    suggestions = []
    
    if query and len(query) >= 2:
        brands = Brand.objects.filter(
            name__icontains=query,
            is_active=True
        ).values('id', 'name')[:10]
        
        suggestions = list(brands)
    
    return JsonResponse({'brands': suggestions})

@login_required
@permission_required('reviews.add_product', raise_exception=True)
def add_product_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        spec_formset = SpecificationFormSet(request.POST, instance=Product())
        
        if form.is_valid() and spec_formset.is_valid():
            brand_name = form.cleaned_data['brand_name']
            brand, created = Brand.objects.get_or_create(
                name=brand_name,
                defaults={'slug': slugify(brand_name)}
            )
            
            product = form.save(commit=False)
            product.brand = brand
            product.created_by = request.user
            
            if not product.slug:
                product.slug = slugify(f"{brand.name}-{product.name}")
            
            product.save()
            form.save_m2m()
            
            spec_formset.instance = product
            spec_formset.save()
            
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('reviews:product_detail', slug=product.slug)
    else:
        form = ProductForm()
        spec_formset = SpecificationFormSet(instance=Product())
    
    context = {
        'form': form,
        'spec_formset': spec_formset,
        'title': 'Add New Product'
    }
    return render(request, 'reviews/product_form.html', context)

class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'reviews/product_form.html'
    success_url = reverse_lazy('home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['spec_formset'] = SpecificationFormSet(self.request.POST, instance=Product())
        else:
            context['spec_formset'] = SpecificationFormSet(instance=Product())
        context['title'] = 'Add New Product'
        return context
    
    def form_valid(self, form):
        spec_formset = SpecificationFormSet(self.request.POST, instance=Product())
        if spec_formset.is_valid():
            brand_name = form.cleaned_data['brand_name']
            brand, created = Brand.objects.get_or_create(
                name=brand_name,
                defaults={'slug': slugify(brand_name)}
            )
            
            self.object = form.save(commit=False)
            self.object.brand = brand
            self.object.created_by = self.request.user
            
            if not self.object.slug:
                self.object.slug = slugify(f"{brand.name}-{self.object.name}")
            
            self.object.save()
            form.save_m2m()
            
            spec_formset.instance = self.object
            spec_formset.save()
            
            messages.success(self.request, f'Product "{self.object.name}" added successfully!')
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

@login_required
def add_review_view(request):
    """
    Render and handle the review form for a standalone review page
    """
    if request.method == 'POST':
        form = ReviewForm(request.POST, request.FILES, user=request.user)
        logger.info(f"Received POST data: {request.POST}, Files: {request.FILES}, Initial form: {form.initial}")
        if form.is_valid():
            review = form.save(commit=False)
            review.user = request.user
            # Check for existing review
            existing_review = Review.objects.filter(product=review.product, user=review.user).first()
            if existing_review:
                logger.info(f"Updating existing review ID: {existing_review.id}")
                existing_review.title = review.title
                existing_review.content = review.content
                existing_review.rating = review.rating
                existing_review.is_approved = True
                existing_review.save()
                messages.success(request, 'Your existing review has been updated successfully!')
                return redirect('reviews:product_detail', slug=review.product.slug)
            else:
                # Force approval for debugging
                review.is_approved = True
                review.save()
                logger.info(f"Review saved successfully! ID: {review.id}, Product: {review.product.id}, User: {review.user.id}, Data: {form.cleaned_data}")
                messages.success(request, 'Your review has been submitted successfully!')
                return redirect('reviews:product_detail', slug=review.product.slug)
        else:
            logger.warning(f"Form validation failed for /review/add/: Request data: {request.POST}, Files: {request.FILES}, Errors: {form.errors}")
            context = {
                'form': form,
                'title': 'Add New Review',
                'errors': form.errors,
                'debug_message': 'POST request received but form validation failed. Check logs for details.'
            }
            return render(request, 'reviews/review_form.html', context)
    else:
        form = ReviewForm(user=request.user)
        logger.info(f"Initial form for GET: {form.initial}")
    
    context = {
        'form': form,
        'title': 'Add New Review'
    }
    return render(request, 'reviews/review_form.html', context)

@login_required
@require_POST
def submit_review_view(request, slug):
    """
    Handle review form submission for a specific product
    """
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    form = ReviewForm(request.POST, request.FILES, user=request.user)
    
    if form.is_valid():
        try:
            review = form.save(commit=False)
            review.user = request.user
            review.product = product
            # Check for existing review
            existing_review = Review.objects.filter(product=review.product, user=review.user).first()
            if existing_review:
                logger.info(f"Updating existing review ID: {existing_review.id}")
                existing_review.title = review.title
                existing_review.content = review.content
                existing_review.rating = review.rating
                existing_review.is_approved = True
                existing_review.save()
                messages.success(request, 'Your existing review has been updated successfully!')
            else:
                # Force approval for debugging
                review.is_approved = True
                review.save()
                logger.info(f"Review saved successfully! ID: {review.id}, Product: {review.product.id}, User: {review.user.id}, Data: {form.cleaned_data}")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Review submitted successfully!',
                    'redirect_url': reverse('reviews:product_detail', kwargs={'slug': product.slug})
                })
            
            messages.success(request, 'Your review has submitted successfully!')
            return redirect('reviews:product_detail', slug=product.slug)
            
        except Exception as e:
            logger.error(f"Error saving review for product {product.slug}: {str(e)}")
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'An error occurred while submitting your review.',
                    'errors': {'__all__': [str(e)]}
                }, status=500)
            messages.error(request, 'An error occurred while submitting your review.')
            return redirect('reviews:product_detail', slug=product.slug)
    
    else:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Please fix the errors below.',
                'errors': dict(form.errors)
            }, status=400)
        
        context = {
            'product': product,
            'review_form': form,
            'user_has_reviewed': Review.objects.filter(product=product, user=request.user).exists(),
            'reviews': Review.objects.filter(product=product, is_approved=True).select_related('user').order_by('-created_at'),
            'rating_distribution': {
                i: {
                    'count': Review.objects.filter(product=product, rating=i, is_approved=True).count(),
                    'percentage': (Review.objects.filter(product=product, rating=i, is_approved=True).count() / 
                                 product.total_reviews * 100) if product.total_reviews > 0 else 0
                } for i in range(1, 6)
            },
            'average_rating': product.average_rating,
            'total_reviews': product.total_reviews,
            'specifications': product.specifications.all(),
        }
        return render(request, 'reviews/product_detail.html', context)

class ReviewCreateView(LoginRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = 'reviews/review_form.html'
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        form.instance.user = self.request.user
        
        if not form.cleaned_data.get('is_verified_purchase', False):
            form.instance.review_video = None
        
        try:
            review = form.save()
            logger.info(f"Review saved successfully! ID: {review.id}")
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Review submitted!',
                    'redirect_url': self.get_success_url()
                })
            
            messages.success(self.request, 'Review submitted successfully!')
            return redirect(self.get_success_url())
            
        except Exception as e:
            logger.error(f"Error saving review: {str(e)}")
            messages.error(self.request, 'Error saving review')
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        logger.info(f"Form errors: {form.errors}")
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': dict(form.errors),
                'message': 'Please fix the errors below'
            })
        return super().form_invalid(form)
    
    def get_success_url(self):
        return reverse('reviews:product_detail', kwargs={'slug': self.object.product.slug})
    
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

@login_required
def dashboard_view(request):
    """Main dashboard route that redirects to appropriate dashboard"""
    if not hasattr(request.user, 'profile'):
        # Create profile if it doesn't exist (for users who signed up before this feature)
        from .models import UserProfile
        UserProfile.objects.create(user=request.user)
    
    if request.user.profile.is_business_user:
        return redirect('reviews:business_dashboard')
    else:
        return redirect('reviews:user_dashboard')

# Add these imports to your existing views.py
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
import json
from PIL import Image
import os
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile

# Update your existing user_dashboard_view
@login_required
def user_dashboard_view(request):
    """Enhanced user dashboard with more features"""
    if hasattr(request.user, 'profile') and request.user.profile.is_business_user:
        return redirect('reviews:business_dashboard')
    
    # Create profile if it doesn't exist
    if not hasattr(request.user, 'profile'):
        UserProfile.objects.create(user=request.user)
    
    # Get user's reviews with additional stats
    reviews = request.user.reviews.select_related('product', 'product__brand', 'product__category').order_by('-created_at')
    
    # Calculate user statistics
    total_reviews = reviews.count()
    approved_reviews = reviews.filter(is_approved=True)
    total_helpful_votes = sum(review.helpful_count for review in reviews)
    
    # Calculate average rating given by user
    user_avg_rating = 0
    if approved_reviews.exists():
        rating_sum = 0
        rating_count = 0
        for review in approved_reviews:
            rating = review.overall_rating or review.rating
            if rating:
                rating_sum += rating
                rating_count += 1
        user_avg_rating = round(rating_sum / rating_count, 1) if rating_count > 0 else 0
    
    # Get recent product views (last 10)
    recent_views = ProductView.objects.filter(
        user=request.user
    ).select_related('product', 'product__brand').order_by('-created_at')[:10]
    
    # Achievement calculations
    achievements = []
    if total_reviews >= 1:
        achievements.append({
            'title': 'First Review',
            'description': 'You wrote your first review!',
            'icon': 'fas fa-medal',
            'color': 'yellow'
        })
    if total_reviews >= 5:
        achievements.append({
            'title': 'Review Explorer',
            'description': '5 reviews completed!',
            'icon': 'fas fa-star',
            'color': 'blue'
        })
    if total_reviews >= 10:
        achievements.append({
            'title': 'Review Master',
            'description': '10 reviews completed!',
            'icon': 'fas fa-crown',
            'color': 'purple'
        })
    if total_helpful_votes >= 10:
        achievements.append({
            'title': 'Helpful Reviewer',
            'description': 'Your reviews helped 10+ people!',
            'icon': 'fas fa-thumbs-up',
            'color': 'green'
        })
    
    # Monthly activity for the last 6 months
    from datetime import datetime, timedelta
    import calendar
    
    monthly_activity = []
    for i in range(6):
        month_start = datetime.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=32)
        month_end = month_end.replace(day=1) - timedelta(days=1)
        
        month_reviews = reviews.filter(
            created_at__gte=month_start,
            created_at__lte=month_end
        ).count()
        
        monthly_activity.append({
            'month': calendar.month_name[month_start.month][:3],
            'year': month_start.year,
            'reviews': month_reviews
        })
    
    monthly_activity.reverse()
    
    context = {
        'reviews': reviews[:10],  # Latest 10 reviews for display
        'all_reviews': reviews,  # All reviews for JS processing
        'total_reviews': total_reviews,
        'approved_reviews_count': approved_reviews.count(),
        'pending_reviews_count': reviews.filter(is_approved=False).count(),
        'total_helpful_votes': total_helpful_votes,
        'user_avg_rating': user_avg_rating,
        'recent_views': recent_views,
        'achievements': achievements,
        'monthly_activity': monthly_activity,
        'is_business_user': False,
        'profile': request.user.profile
    }
    
    return render(request, 'reviews/user_dashboard.html', context)

# Add new AJAX views for dashboard functionality
@login_required
@csrf_exempt
def update_profile_ajax(request):
    """Handle profile updates via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        user = request.user
        profile = user.profile
        
        # Update user data
        user.username = request.POST.get('username', user.username)
        user.email = request.POST.get('email', user.email)
        user.first_name = request.POST.get('first_name', user.first_name)
        user.last_name = request.POST.get('last_name', user.last_name)
        
        # Update profile data
        is_business_user = request.POST.get('is_business_user', 'false').lower() == 'true'
        profile.is_business_user = is_business_user
        
        # Handle profile picture upload
        if request.FILES.get('profile_picture'):
            profile_pic = request.FILES['profile_picture']
            
            # Validate image
            try:
                img = Image.open(profile_pic)
                img.verify()
            except Exception:
                return JsonResponse({'error': 'Invalid image file'}, status=400)
            
            # Reset file pointer
            profile_pic.seek(0)
            
            # Save the image
            profile.profile_picture = profile_pic
        
        user.save()
        profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Profile updated successfully!',
            'data': {
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'is_business_user': profile.is_business_user,
                'profile_picture_url': profile.profile_picture.url if profile.profile_picture else None
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_review_data_ajax(request, review_id):
    """Get review data for editing"""
    try:
        review = get_object_or_404(Review, id=review_id, user=request.user)
        
        data = {
            'id': str(review.id),
            'title': review.title,
            'content': review.content,
            'overall_rating': review.overall_rating,
            'performance_rating': review.performance_rating,
            'battery_rating': review.battery_rating,
            'camera_rating': review.camera_rating,
            'display_rating': review.display_rating,
            'value_rating': review.value_rating,
            'likes': review.likes,
            'improvements': review.improvements,
            'issues': review.issues,
            'recommendation': review.recommendation,
            'product': {
                'id': str(review.product.id),
                'name': review.product.name,
                'brand': review.product.brand.name
            }
        }
        
        return JsonResponse({'success': True, 'data': data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@csrf_exempt
def update_review_ajax(request, review_id):
    """Update review via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        review = get_object_or_404(Review, id=review_id, user=request.user)
        
        # Update review data
        review.title = request.POST.get('title', review.title)
        review.content = request.POST.get('content', review.content)
        
        # Update ratings
        ratings = ['overall_rating', 'performance_rating', 'battery_rating', 
                  'camera_rating', 'display_rating', 'value_rating']
        
        for rating in ratings:
            value = request.POST.get(rating)
            if value and value.isdigit():
                setattr(review, rating, int(value))
        
        # Update open feedback fields
        review.likes = request.POST.get('likes', review.likes)
        review.improvements = request.POST.get('improvements', review.improvements)
        review.issues = request.POST.get('issues', review.issues)
        review.recommendation = request.POST.get('recommendation', review.recommendation)
        
        # Reset approval status for updated reviews
        review.is_approved = request.user.is_staff
        
        review.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Review updated successfully!',
            'review_id': str(review.id)
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def delete_review_ajax(request, review_id):
    """Delete review via AJAX"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        review = get_object_or_404(Review, id=review_id, user=request.user)
        product_name = review.product.name
        review.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Review for {product_name} deleted successfully!'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Add new URL patterns to your urls.py
"""
Add these to your urlpatterns in urls.py:

    # Dashboard AJAX endpoints
    path('api/profile/update/', views.update_profile_ajax, name='update_profile_ajax'),
    path('api/review/<uuid:review_id>/data/', views.get_review_data_ajax, name='get_review_data'),
    path('api/review/<uuid:review_id>/update/', views.update_review_ajax, name='update_review_ajax'),
    path('api/review/<uuid:review_id>/delete/', views.delete_review_ajax, name='delete_review_ajax'),
"""
@login_required
def business_dashboard_view(request):
    """Business user dashboard"""
    if not request.user.profile.is_business_user:
        # Normal users shouldn't access this
        raise PermissionDenied("You don't have permission to access this page")
    
    # Get business-specific data
    from .models import Product
    products = Product.objects.filter(created_by=request.user).annotate(
        review_count=Count('reviews'),
        avg_rating=Avg('reviews__overall_rating')
    )
    
    context = {
        'products': products,
        'is_business_user': True
    }
    return render(request, 'reviews/business_dashboard.html', context)

#product view ko lagi

from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count

def products_view(request):
    """
    Display all products with search and filtering functionality
    """
    # Get search query
    query = request.GET.get('q', '').strip()
    
    # Get filter parameters
    category_slug = request.GET.get('category', '')
    brand_slug = request.GET.get('brand', '')
    sort_by = request.GET.get('sort', 'newest')
    
    # Start with all active products
    products = Product.objects.filter(is_active=True).select_related('brand', 'category')
    
    # Apply search filter
    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query)
        )
        
        # Log search query
        SearchQuery.objects.create(
            query=query,
            user=request.user if request.user.is_authenticated else None,
            results_count=products.count(),
            ip_address=get_client_ip(request)
        )
    
    # Apply category filter
    if category_slug:
        products = products.filter(category__slug=category_slug)
    
    # Apply brand filter
    if brand_slug:
        products = products.filter(brand__slug=brand_slug)
    
    # Annotate with ratings and review counts
    products = products.annotate(
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True)),
        recent_reviews=Count(
            'reviews',
            filter=Q(
                reviews__created_at__gte=timezone.now() - timedelta(days=30),
                reviews__is_approved=True
            )
        )
    )
    
    # Apply sorting
    if sort_by == 'rating':
        products = products.order_by('-avg_rating', '-review_count')
    elif sort_by == 'reviews':
        products = products.order_by('-review_count', '-avg_rating')
    elif sort_by == 'popular':
        products = products.order_by('-recent_reviews', '-view_count', '-avg_rating')
    else:  # newest
        products = products.order_by('-created_at')
    
    # Pagination
    paginator = Paginator(products, 12)  # Show 12 products per page
    page_number = request.GET.get('page')
    products_page = paginator.get_page(page_number)
    
    # Get all categories and brands for filters
    categories = Category.objects.filter(is_active=True).order_by('name')
    brands = Brand.objects.filter(is_active=True).order_by('name')
    
    # Add additional properties for template
    # for product in products_page:
    #     product.total_reviews = product.review_count
    #     product.average_rating = product.avg_rating or 0
    
    context = {
        'products': products_page,
        'categories': categories,
        'brands': brands,
        'query': query,
        'selected_category': category_slug,
        'selected_brand': brand_slug,
        'selected_sort': sort_by,
        'total_count': paginator.count,
    }
    
    return render(request, 'reviews/products.html', context)


# Add this autocomplete view for search suggestions
@require_GET
def product_autocomplete(request):
    """
    Provide autocomplete suggestions for product search
    """
    query = request.GET.get('q', '').strip()
    suggestions = []
    
    if query and len(query) >= 2:
        # Get product suggestions
        products = Product.objects.filter(
            Q(name__icontains=query) | Q(brand__name__icontains=query),
            is_active=True
        ).select_related('brand').annotate(
            avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
            review_count=Count('reviews', filter=Q(reviews__is_approved=True))
        )[:8]
        
        for product in products:
            suggestions.append({
                'type': 'product',
                'name': f"{product.brand.name} {product.name}",
                'url': f"/product/{product.slug}/",
                'image': product.image.url if product.image else None,
                'rating': product.avg_rating or 0,
                'reviews': product.review_count,
                'brand': product.brand.name,
            })
        
        # Get brand suggestions
        # brands = Brand.objects.filter(
        #     name__icontains=query,
        #     is_active=True
        # )[:3]
        
        # for brand in brands:
        #     suggestions.append({
        #         'type': 'brand',
        #         'name': brand.name,
        #         'url': f"/brand/{brand.slug}/",
        #         'image': brand.logo.url if brand.logo else None
        #     })
    
    return JsonResponse({'suggestions': suggestions})


# this is for reviewedit functionality
@login_required
def edit_review_view(request, review_id):
    """View for editing an existing review"""
    review = get_object_or_404(Review, id=review_id, user=request.user)
    
    if request.method == 'POST':
        form = ReviewForm(request.POST, request.FILES, user=request.user, instance=review)
        if form.is_valid():
            updated_review = form.save(commit=False)
            updated_review.is_approved = False  # Reset approval status when edited
            updated_review.save()
            
            messages.success(request, 'Your review has been updated successfully!')
            return redirect('reviews:product_detail', slug=review.product.slug)
    else:
        form = ReviewForm(user=request.user, instance=review)
    
    context = {
        'form': form,
        'title': 'Edit Your Review',
        'review': review,
        'product': review.product
    }
    return render(request, 'reviews/review_form.html', context)

# for ABOUTUS PAGE

def about_us(request):
    """View function for the About Us page"""
    context = {
        'title': 'About Us',
        'page_description': 'Learn more about feedMe and our mission',
        # Add any other context variables you need
    }
    return render(request, 'reviews/aboutus.html', context)
