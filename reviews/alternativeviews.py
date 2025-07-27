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
from .forms import ReviewForm, ProductForm, SpecificationFormSet,ProductEditForm
import logging
from django.utils.text import slugify
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from transformers import pipeline



logger = logging.getLogger(__name__)


from allauth.account.views import SignupView
from .forms import UserTypeForm


from django.core.cache import cache
from transformers import pipeline
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


import nltk

def download_nltk_data():
    for path, package in [
        ('tokenizers/punkt', 'punkt'),
        ('corpora/stopwords', 'stopwords'),
        ('corpora/wordnet', 'wordnet'),
        ('taggers/averaged_perceptron_tagger', 'averaged_perceptron_tagger'),
        ('corpora/omw-1.4', 'omw-1.4')
    ]:
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(package)

download_nltk_data()  # Safe to call, only downloads if missing


def generate_ai_summary(reviews):
    """
    Generates and caches AI summaries including pros, cons, and overall assessment.
    Returns: {'pros': str, 'cons': str, 'overall': str} or None if failed
    """
    if not reviews:
        return None

    try:
        # Safely get product_id from first valid review
        product_id = None
        for review in reviews:
            if hasattr(review, 'product') and hasattr(review.product, 'id'):
                product_id = review.product.id
                break
        
        if not product_id:
            logger.warning("No valid reviews with product association found")
            return None

        cache_key = f"ai_summary_v3_{product_id}"  # Changed version to v3

        # Return cached summary if available
        if cached := cache.get(cache_key):
            logger.debug(f"Using cached summary for product {product_id}")
            return cached

        # Initialize summarizer
        summarizer = pipeline(
            "summarization",
            model="sshleifer/distilbart-cnn-12-6",
            framework="pt"
        )

        # Prepare review text safely
        review_content = []
        for r in reviews[:10]:  # Only process first 10 reviews
            if isinstance(r, str):
                content = r[:200].strip()
            elif hasattr(r, 'content'):
                content = r.content[:200].strip()
            else:
                continue
            
            if content:
                review_content.append(content)

        combined_text = " ".join(review_content)

        if not combined_text:
            return None

        # Generate different aspects with specific prompts
        def generate_aspect(text, prompt_prefix):
            try:
                result = summarizer(
                    f"{prompt_prefix}: {text}",
                    max_length=100,
                    min_length=30,
                    truncation=True,
                    do_sample=False
                )
                return result[0]['summary_text']
            except:
                return ""

        # Generate all three aspects
        pros = generate_aspect(combined_text, "List the positive aspects")
        cons = generate_aspect(combined_text, "List the negative aspects")
        overall = generate_aspect(combined_text, "Provide an overall assessment")

        # Structure results
        result = {
            'pros': pros if pros else "No significant positive aspects mentioned",
            'cons': cons if cons else "No significant negative aspects mentioned",
            'overall': overall if overall else "Mixed reviews overall",
            'generated_at': str(timezone.now())
        }

        # Cache for 6 hours
        cache.set(cache_key, result, 60 * 60 * 6)
        logger.info(f"Generated new AI summary for product {product_id}")

        return result

    except Exception as e:
        logger.error(f"AI summary failed: {str(e)}")
        return None
    


    
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
    
    # Changed from 'reviews__rating' to 'reviews__overall_rating'
    top_products = Product.objects.filter(
        is_active=True,
        reviews__is_approved=True
    ).annotate(
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(
        review_count__gte=1
    ).order_by('-avg_rating', '-review_count')[:4]
    
    thirty_days_ago = timezone.now() - timedelta(days=30)
    # Changed from 'reviews__rating' to 'reviews__overall_rating'
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
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
        total_review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(
        Q(recent_reviews__gt=0) | Q(recent_views__gt=0)
    ).order_by('-recent_reviews', '-recent_views', '-avg_rating')[:4]
    
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

        # --- DEMO MODE (temporary override) ---
    DEMO_MODE = False  # Set to False later to disable

    if DEMO_MODE and reviews.count() < 4:
        demo_reviews = [
            {"content": "The battery life is outstanding - lasts 2 full days with heavy use."},
            {"content": "Camera takes great photos in daylight but struggles in low light."},
            {"content": "Performance is super smooth, no lag even with 20+ apps open."},
            {"content": "The AMOLED display is vibrant and perfect for watching videos."},
            {"content": "Feels premium but is overpriced compared to competitors."}
        ]
        context['ai_summary'] = generate_ai_summary(demo_reviews)
        context['is_demo'] = True  # Flag for template
    else:
        context['ai_summary'] = generate_ai_summary(reviews) if reviews.count() > 3 else None
        context['is_demo'] = False


    # DEMO ONLY - Simulate realistic reviews if you have fewer than 4
    if reviews.count() < 4:
        demo_reviews = [
            "Battery life is excellent, easily lasts 2 days.",
            "The camera takes sharp photos but struggles in low light.",
            "Very fast performance with no lag during multitasking.",
            "Display colors are vibrant and brightness is perfect.",
        ]
        context['ai_summary'] = generate_ai_summary(demo_reviews)

    # Generate AI summary (only if >3 reviews exist)
    context['ai_summary'] = generate_ai_summary(reviews) if reviews.count() > 3 else None
    
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
def add_product_view(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        
        if form.is_valid():
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
            
            # Create specification
            specification = Specification(
                product=product,
                ram=form.cleaned_data['ram'],
                storage=form.cleaned_data['storage'],
                processor=form.cleaned_data['processor'],
                rear_camera=form.cleaned_data['rear_camera'],
                # Optional fields
                screen_size=form.cleaned_data.get('screen_size', ''),
                resolution=form.cleaned_data.get('resolution', ''),
                refresh_rate=form.cleaned_data.get('refresh_rate', ''),
                display_type=form.cleaned_data.get('display_type', ''),
                front_camera=form.cleaned_data.get('front_camera', ''),
                video_recording=form.cleaned_data.get('video_recording', ''),
                battery_capacity=form.cleaned_data.get('battery_capacity', ''),
                network_support=form.cleaned_data.get('network_support', ''),
                wifi=form.cleaned_data.get('wifi', ''),
                bluetooth=form.cleaned_data.get('bluetooth', ''),
                nfc=form.cleaned_data.get('nfc', False),
                dimensions=form.cleaned_data.get('dimensions', ''),
                weight=form.cleaned_data.get('weight', ''),
                fingerprint_sensor=form.cleaned_data.get('fingerprint_sensor', ''),
                face_unlock=form.cleaned_data.get('face_unlock', False),
                operating_system=form.cleaned_data.get('operating_system', ''),
                audio_jack=form.cleaned_data.get('audio_jack', False),
                # Initialize key/value fields (can be updated later)
                key='general',
                value='specifications'
            )
            specification.save()
            
            messages.success(request, f'Product "{product.name}" added successfully!')
            return redirect('reviews:product_detail', slug=product.slug)
    else:
        form = ProductForm()
    
    context = {
        'form': form,
        'title': 'Add New Product'
    }
    return render(request, 'reviews/product_form.html', context)

from django.views.generic.edit import UpdateView
from django.urls import reverse

class ProductUpdateView(LoginRequiredMixin, UpdateView):
    model = Product
    form_class = ProductEditForm
    template_name = 'reviews/product_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Edit {self.object.name}'
        return context
    
    def form_valid(self, form):
        # Handle brand update first
        brand_name = form.cleaned_data['brand_name']
        brand, created = Brand.objects.get_or_create(
            name=brand_name,
            defaults={'slug': slugify(brand_name)}
        )
        
        # Update product with new brand
        self.object = form.save(commit=False)
        self.object.brand = brand
        self.object.save()
        
        # Update or create specification
        spec, created = Specification.objects.get_or_create(
            product=self.object,
            defaults={
                'ram': form.cleaned_data['ram'],
                'storage': form.cleaned_data['storage'],
                'processor': form.cleaned_data['processor'],
                'rear_camera': form.cleaned_data['rear_camera'],
                # Optional fields
                'screen_size': form.cleaned_data.get('screen_size', ''),
                'resolution': form.cleaned_data.get('resolution', ''),
                'refresh_rate': form.cleaned_data.get('refresh_rate', ''),
                'display_type': form.cleaned_data.get('display_type', ''),
                'front_camera': form.cleaned_data.get('front_camera', ''),
                'video_recording': form.cleaned_data.get('video_recording', ''),
                'battery_capacity': form.cleaned_data.get('battery_capacity', ''),
                'network_support': form.cleaned_data.get('network_support', ''),
                'wifi': form.cleaned_data.get('wifi', ''),
                'bluetooth': form.cleaned_data.get('bluetooth', ''),
                'nfc': form.cleaned_data.get('nfc', False),
                'dimensions': form.cleaned_data.get('dimensions', ''),
                'weight': form.cleaned_data.get('weight', ''),
                'fingerprint_sensor': form.cleaned_data.get('fingerprint_sensor', ''),
                'face_unlock': form.cleaned_data.get('face_unlock', False),
                'operating_system': form.cleaned_data.get('operating_system', ''),
                'audio_jack': form.cleaned_data.get('audio_jack', False),
                'key': 'general',
                'value': 'specifications'
            }
        )
        
        if not created:
            # Update existing specification
            spec.ram = form.cleaned_data['ram']
            spec.storage = form.cleaned_data['storage']
            spec.processor = form.cleaned_data['processor']
            spec.rear_camera = form.cleaned_data['rear_camera']
            # Optional fields
            spec.screen_size = form.cleaned_data.get('screen_size', '')
            spec.resolution = form.cleaned_data.get('resolution', '')
            spec.refresh_rate = form.cleaned_data.get('refresh_rate', '')
            spec.display_type = form.cleaned_data.get('display_type', '')
            spec.front_camera = form.cleaned_data.get('front_camera', '')
            spec.video_recording = form.cleaned_data.get('video_recording', '')
            spec.battery_capacity = form.cleaned_data.get('battery_capacity', '')
            spec.network_support = form.cleaned_data.get('network_support', '')
            spec.wifi = form.cleaned_data.get('wifi', '')
            spec.bluetooth = form.cleaned_data.get('bluetooth', '')
            spec.nfc = form.cleaned_data.get('nfc', False)
            spec.dimensions = form.cleaned_data.get('dimensions', '')
            spec.weight = form.cleaned_data.get('weight', '')
            spec.fingerprint_sensor = form.cleaned_data.get('fingerprint_sensor', '')
            spec.face_unlock = form.cleaned_data.get('face_unlock', False)
            spec.operating_system = form.cleaned_data.get('operating_system', '')
            spec.audio_jack = form.cleaned_data.get('audio_jack', False)
            spec.save()
        
        messages.success(self.request, f'Product "{self.object.name}" updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('reviews:product_detail', kwargs={'slug': self.object.slug})
    
    def get_success_url(self):
        return reverse('reviews:product_detail', kwargs={'slug': self.object.slug})


class ProductCreateView(CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'reviews/product_form.html'
    success_url = reverse_lazy('home')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Add New Product'
        return context
    
    def form_valid(self, form):
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
        
        # Create specification
        Specification.objects.create(
            product=self.object,
            ram=form.cleaned_data['ram'],
            storage=form.cleaned_data['storage'],
            processor=form.cleaned_data['processor'],
            rear_camera=form.cleaned_data['rear_camera'],
            # Optional fields with defaults
            screen_size=form.cleaned_data.get('screen_size', ''),
            resolution=form.cleaned_data.get('resolution', ''),
            refresh_rate=form.cleaned_data.get('refresh_rate', ''),
            display_type=form.cleaned_data.get('display_type', ''),
            front_camera=form.cleaned_data.get('front_camera', ''),
            video_recording=form.cleaned_data.get('video_recording', ''),
            battery_capacity=form.cleaned_data.get('battery_capacity', ''),
            network_support=form.cleaned_data.get('network_support', ''),
            wifi=form.cleaned_data.get('wifi', ''),
            bluetooth=form.cleaned_data.get('bluetooth', ''),
            nfc=form.cleaned_data.get('nfc', False),
            dimensions=form.cleaned_data.get('dimensions', ''),
            weight=form.cleaned_data.get('weight', ''),
            fingerprint_sensor=form.cleaned_data.get('fingerprint_sensor', ''),
            face_unlock=form.cleaned_data.get('face_unlock', False),
            operating_system=form.cleaned_data.get('operating_system', ''),
            audio_jack=form.cleaned_data.get('audio_jack', False),
            key='general',
            value='specifications'
        )
        
        messages.success(self.request, f'Product "{self.object.name}" added successfully!')
        return super().form_valid(form)

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
    """Business user dashboard with proper calculations"""
    if not hasattr(request.user, 'profile') or not request.user.profile.is_business_user:
        # Normal users shouldn't access this
        raise PermissionDenied("You don't have permission to access this page")
    
    # Get business-specific data with proper annotations
    products = Product.objects.filter(created_by=request.user).annotate(
        review_count=Count('reviews', filter=Q(reviews__is_approved=True)),
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True))
    ).select_related('brand', 'category').order_by('-created_at')
    
    # Calculate summary statistics
    total_reviews = sum(product.review_count or 0 for product in products)
    total_views = sum(product.view_count or 0 for product in products)
    
    # Calculate average rating across all products
    products_with_ratings = [p for p in products if p.avg_rating is not None]
    overall_avg_rating = (
        sum(p.avg_rating for p in products_with_ratings) / len(products_with_ratings)
        if products_with_ratings else 0
    )
    
    # Find top performer (highest rated product with at least 1 review)
    top_performer = None
    products_with_reviews = [p for p in products if (p.avg_rating or 0) > 0 and (p.review_count or 0) > 0]
    if products_with_reviews:
        top_performer = max(products_with_reviews, key=lambda x: x.avg_rating or 0)
    
    # Find most reviewed product
    most_reviewed = None
    if products_with_reviews:
        most_reviewed = max(products_with_reviews, key=lambda x: x.review_count or 0)
    
    context = {
        'products': products,
        'is_business_user': True,
        # Summary statistics
        'total_reviews': total_reviews,
        'total_views': total_views,
        'overall_avg_rating': round(overall_avg_rating, 1),
        # Top products
        'top_performer': top_performer,
        'most_reviewed': most_reviewed,
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

# Add these imports to your existing views.py
import json
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.db.models import Avg, Count, Q, F, Case, When, IntegerField
from django.core.cache import cache
from django.utils import timezone
from collections import Counter
import re
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.units import inch
import csv
from io import BytesIO, StringIO

@login_required
def business_analytics_dashboard(request):
    """Enhanced Business Analytics Dashboard"""
    if not hasattr(request.user, 'profile') or not request.user.profile.is_business_user:
        messages.error(request, "Access denied. Business account required.")
        return redirect('reviews:home')
    
    # Get filter parameters
    price_min = request.GET.get('price_min', 0)
    price_max = request.GET.get('price_max', 100000)
    category_id = request.GET.get('category', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset with filters
    products_qs = Product.objects.filter(is_active=True)
    
    if price_min:
        products_qs = products_qs.filter(price__gte=price_min)
    if price_max:
        products_qs = products_qs.filter(price__lte=price_max)
    if category_id:
        products_qs = products_qs.filter(category_id=category_id)
    
    # Date filtering for reviews
    reviews_qs = Review.objects.filter(is_approved=True)
    if date_from:
        reviews_qs = reviews_qs.filter(created_at__gte=date_from)
    if date_to:
        reviews_qs = reviews_qs.filter(created_at__lte=date_to)
    
    # Calculate trending products
    cache_key = f"trending_products_{hash(str(request.GET))}"
    trending_products = cache.get(cache_key)
    
    if not trending_products:
        trending_products = calculate_trending_products(products_qs, reviews_qs)
        cache.set(cache_key, trending_products, 300)  # Cache for 5 minutes
    
    # Calculate quick insights
    quick_insights = calculate_quick_insights(products_qs, reviews_qs)
    
    # Get categories for filters
    categories = Category.objects.filter(is_active=True).order_by('name')
    
    # Get top products for dropdowns
    top_products = products_qs.annotate(
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(review_count__gte=1).order_by('-avg_rating', '-review_count')[:20]
    
    context = {
        'trending_products': trending_products,
        'quick_insights': quick_insights,
        'categories': categories,
        'top_products': top_products,
        'filters': {
            'price_min': price_min,
            'price_max': price_max,
            'category_id': category_id,
            'date_from': date_from,
            'date_to': date_to,
        }
    }
    
    return render(request, 'reviews/business_analytics.html', context)

def calculate_trending_products(products_qs, reviews_qs):
    """Calculate trending products based on the formula"""
    trending = []
    
    for product in products_qs.annotate(
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(review_count__gte=1):
        
        # Calculate product age in days
        age_days = (timezone.now() - product.created_at).days
        if age_days == 0:
            age_days = 1  # Prevent division by zero
        
        # Calculate trending score
        score = (product.review_count * (product.avg_rating or 0)) / age_days
        
        trending.append({
            'product': product,
            'score': round(score, 2),
            'avg_rating': product.avg_rating or 0,
            'review_count': product.review_count,
            'age_days': age_days
        })
    
    # Sort by score and return top 5
    trending.sort(key=lambda x: x['score'], reverse=True)
    return trending[:5]

def calculate_quick_insights(products_qs, reviews_qs):
    """Calculate quick insights for the dashboard"""
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    # Fastest improving products (30-day rating improvement)
    improving_products = []
    for product in products_qs.annotate(
        recent_avg=Avg('reviews__overall_rating', 
                      filter=Q(reviews__created_at__gte=thirty_days_ago, reviews__is_approved=True)),
        older_avg=Avg('reviews__overall_rating', 
                     filter=Q(reviews__created_at__lt=thirty_days_ago, reviews__is_approved=True)),
        recent_count=Count('reviews', 
                          filter=Q(reviews__created_at__gte=thirty_days_ago, reviews__is_approved=True))
    ).filter(recent_count__gte=2, recent_avg__isnull=False, older_avg__isnull=False):
        
        improvement = (product.recent_avg or 0) - (product.older_avg or 0)
        if improvement > 0:
            improving_products.append({
                'product': product,
                'improvement': round(improvement, 2),
                'recent_avg': round(product.recent_avg, 1),
                'older_avg': round(product.older_avg, 1)
            })
    
    improving_products.sort(key=lambda x: x['improvement'], reverse=True)
    
    # Underrated products (high rating, low review count)
    underrated_products = products_qs.annotate(
        avg_rating=Avg('reviews__overall_rating', filter=Q(reviews__is_approved=True)),
        review_count=Count('reviews', filter=Q(reviews__is_approved=True))
    ).filter(
        avg_rating__gte=4.0,
        review_count__lt=10,
        review_count__gte=1
    ).order_by('-avg_rating')[:5]
    
    return {
        'improving_products': improving_products[:5],
        'underrated_products': underrated_products
    }

@login_required
def benchmark_data_ajax(request):
    """AJAX endpoint for benchmarking chart data"""
    if not request.user.profile.is_business_user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    product1_id = request.GET.get('product1')
    product2_id = request.GET.get('product2')
    
    if not product1_id or not product2_id:
        return JsonResponse({'error': 'Both products required'}, status=400)
    
    try:
        product1 = Product.objects.get(id=product1_id, is_active=True)
        product2 = Product.objects.get(id=product2_id, is_active=True)
        
        # Generate 6 months of data
        months_data = []
        for i in range(6):
            month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
            month_end = month_start + timedelta(days=32)
            month_end = month_end.replace(day=1) - timedelta(days=1)
            
            # Product 1 data
            p1_reviews = Review.objects.filter(
                product=product1,
                created_at__gte=month_start,
                created_at__lte=month_end,
                is_approved=True
            )
            p1_avg = p1_reviews.aggregate(avg=Avg('overall_rating'))['avg'] or 0
            p1_count = p1_reviews.count()
            
            # Product 2 data
            p2_reviews = Review.objects.filter(
                product=product2,
                created_at__gte=month_start,
                created_at__lte=month_end,
                is_approved=True
            )
            p2_avg = p2_reviews.aggregate(avg=Avg('overall_rating'))['avg'] or 0
            p2_count = p2_reviews.count()
            
            months_data.append({
                'month': month_start.strftime('%b'),
                'product1': {
                    'rating': round(p1_avg, 1),
                    'count': p1_count
                },
                'product2': {
                    'rating': round(p2_avg, 1),
                    'count': p2_count
                }
            })
        
        months_data.reverse()
        
        return JsonResponse({
            'success': True,
            'data': months_data,
            'products': {
                'product1': f"{product1.brand.name} {product1.name}",
                'product2': f"{product2.brand.name} {product2.name}"
            }
        })
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def word_cloud_data_ajax(request):
    """AJAX endpoint for word cloud data"""
    if not request.user.profile.is_business_user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    category_id = request.GET.get('category')
    
    if not category_id:
        return JsonResponse({'error': 'Category required'}, status=400)
    
    try:
        category = Category.objects.get(id=category_id, is_active=True)
        
        # Get all reviews for products in this category
        reviews = Review.objects.filter(
            product__category=category,
            is_approved=True,
            content__isnull=False
        ).values_list('content', flat=True)
        
        # Extract common words
        all_text = ' '.join(reviews).lower()
        
        # Remove common words and extract meaningful terms
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her', 'us', 'them', 'my', 'your', 'his', 'her', 'its', 'our', 'their'}
        
        words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text)
        filtered_words = [word for word in words if word not in stop_words]
        
        # Count word frequency
        word_counts = Counter(filtered_words)
        top_words = word_counts.most_common(20)
        
        # Format for word cloud
        word_data = [{'text': word, 'size': count} for word, count in top_words]
        
        return JsonResponse({
            'success': True,
            'words': word_data,
            'category': category.name
        })
        
    except Category.DoesNotExist:
        return JsonResponse({'error': 'Category not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def export_comparison_pdf(request):
    """Export product comparison as PDF"""
    if not request.user.profile.is_business_user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    product1_id = request.GET.get('product1')
    product2_id = request.GET.get('product2')
    
    if not product1_id or not product2_id:
        return JsonResponse({'error': 'Both products required'}, status=400)
    
    try:
        product1 = Product.objects.get(id=product1_id, is_active=True)
        product2 = Product.objects.get(id=product2_id, is_active=True)
        
        # Create PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        
        # Get styles
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=18, spaceAfter=30)
        
        # Build PDF content
        story = []
        
        # Title
        story.append(Paragraph(f"Product Comparison Report", title_style))
        story.append(Spacer(1, 12))
        
        # Product comparison table
        data = [
            ['Metric', f'{product1.brand.name} {product1.name}', f'{product2.brand.name} {product2.name}'],
            ['Category', product1.category.name, product2.category.name],
            ['Price', f'${product1.price}' if product1.price else 'N/A', f'${product2.price}' if product2.price else 'N/A'],
        ]
        
        # Add rating data
        p1_avg = product1.reviews.filter(is_approved=True).aggregate(avg=Avg('overall_rating'))['avg'] or 0
        p2_avg = product2.reviews.filter(is_approved=True).aggregate(avg=Avg('overall_rating'))['avg'] or 0
        p1_count = product1.reviews.filter(is_approved=True).count()
        p2_count = product2.reviews.filter(is_approved=True).count()
        
        data.extend([
            ['Average Rating', f'{p1_avg:.1f}', f'{p2_avg:.1f}'],
            ['Total Reviews', str(p1_count), str(p2_count)],
            ['Views', str(product1.view_count), str(product2.view_count)]
        ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        story.append(table)
        story.append(Spacer(1, 30))
        
        # Add summary
        story.append(Paragraph("Summary", styles['Heading2']))
        story.append(Paragraph(f"Generated on {timezone.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        
        # Build PDF
        doc.build(story)
        
        # Return response
        buffer.seek(0)
        response = HttpResponse(buffer, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="product_comparison_{timezone.now().strftime("%Y%m%d")}.pdf"'
        return response
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def export_comparison_csv(request):
    """Export product comparison as CSV"""
    if not request.user.profile.is_business_user:
        return JsonResponse({'error': 'Access denied'}, status=403)
    
    product1_id = request.GET.get('product1')
    product2_id = request.GET.get('product2')
    
    if not product1_id or not product2_id:
        return JsonResponse({'error': 'Both products required'}, status=400)
    
    try:
        product1 = Product.objects.get(id=product1_id, is_active=True)
        product2 = Product.objects.get(id=product2_id, is_active=True)
        
        # Create CSV
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Metric', f'{product1.brand.name} {product1.name}', f'{product2.brand.name} {product2.name}'])
        
        # Data rows
        writer.writerow(['Category', product1.category.name, product2.category.name])
        writer.writerow(['Price', f'${product1.price}' if product1.price else 'N/A', f'${product2.price}' if product2.price else 'N/A'])
        
        # Rating data
        p1_avg = product1.reviews.filter(is_approved=True).aggregate(avg=Avg('overall_rating'))['avg'] or 0
        p2_avg = product2.reviews.filter(is_approved=True).aggregate(avg=Avg('overall_rating'))['avg'] or 0
        p1_count = product1.reviews.filter(is_approved=True).count()
        p2_count = product2.reviews.filter(is_approved=True).count()
        
        writer.writerow(['Average Rating', f'{p1_avg:.1f}', f'{p2_avg:.1f}'])
        writer.writerow(['Total Reviews', str(p1_count), str(p2_count)])
        writer.writerow(['Views', str(product1.view_count), str(product2.view_count)])
        
        # Return response
        output.seek(0)
        response = HttpResponse(output.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="product_comparison_{timezone.now().strftime("%Y%m%d")}.csv"'
        return response
        
    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)



from django.shortcuts import render, get_object_or_404
import joblib
import re
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer
from collections import Counter
from .models import Product, Review

# # Initialize NLTK (should be done once)
# nltk.download('punkt')
# nltk.download('stopwords')
# nltk.download('wordnet')

# Load models (put this at module level to load once)
try:
    vectorizer = joblib.load('models/tfidf_vectorizer.pkl')
    model = joblib.load('models/rf_model.pkl')
except Exception as e:
    print(f"Error loading models: {e}")
    vectorizer = None
    model = None

def preprocess_text(text):
    if not isinstance(text, str) or not text.strip():
        return ''
    
    text = text.lower()
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    try:
        tokens = word_tokenize(text)
    except LookupError:
        print("⚠️ punkt_tab not found, using basic split as fallback.")
        tokens = text.split()
    stop_words = set(stopwords.words('english'))
    tokens = [t for t in tokens if t not in stop_words]
    lemmatizer = WordNetLemmatizer()
    tokens = [lemmatizer.lemmatize(t) for t in tokens]
    return ' '.join(tokens)

def analyze_review_sentiment(text):
    if not vectorizer or not model:
        return 'neutral'
    
    processed = preprocess_text(text)
    X_input = vectorizer.transform([processed])
    prediction = model.predict(X_input)
    return prediction[0]

def extract_keywords(text, n=3):
    processed = preprocess_text(text)
    tokens = processed.split()
    word_counts = Counter(tokens)
    return [word for word, count in word_counts.most_common(n)]

def business_product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug, is_active=True)
    reviews = Review.objects.filter(product=product, is_approved=True).select_related('user')
    
    # Analyze all reviews
    analyzed_reviews = []
    sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}
    
    for review in reviews:
        sentiment = analyze_review_sentiment(review.content)
        sentiment_counts[sentiment] += 1
        keywords = extract_keywords(review.content)
        
        analyzed_reviews.append({
            **review.__dict__,
            'sentiment': sentiment,
            'keywords': keywords
        })
    
    # Calculate percentages
    total_reviews = len(analyzed_reviews)
    positive_percentage = round((sentiment_counts['positive'] / total_reviews) * 100) if total_reviews else 0
    negative_percentage = round((sentiment_counts['negative'] / total_reviews) * 100) if total_reviews else 0
    neutral_percentage = round((sentiment_counts['neutral'] / total_reviews) * 100) if total_reviews else 0
    
    # Find most positive/negative reviews
    most_positive_review = max(analyzed_reviews, key=lambda x: 1 if x['sentiment'] == 'positive' else 0, default=None)
    most_negative_review = max(analyzed_reviews, key=lambda x: 1 if x['sentiment'] == 'negative' else 0, default=None)
    most_helpful_review = max(reviews, key=lambda x: x.helpful_count, default=None)
    
    # Find common keywords across all reviews
    all_keywords = []
    for review in analyzed_reviews:
        all_keywords.extend(review['keywords'])
    common_keywords = Counter(all_keywords).most_common(10)
    
    context = {
        'product': product,
        'analyzed_reviews': analyzed_reviews,
        'positive_percentage': positive_percentage,
        'negative_percentage': negative_percentage,
        'neutral_percentage': neutral_percentage,
        'positive_count': sentiment_counts['positive'],
        'negative_count': sentiment_counts['negative'],
        'neutral_count': sentiment_counts['neutral'],
        'most_positive_review': most_positive_review,
        'most_negative_review': most_negative_review,
        'most_helpful_review': most_helpful_review,
        'common_keywords': common_keywords,
    }
    
    return render(request, 'reviews/business_product_detail.html', context)


