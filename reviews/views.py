from django.shortcuts import render, get_object_or_404
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta
from .models import Product, Category, Brand, Review, SearchQuery, ProductView


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
    ).order_by()[:4]
    # .order_by('-avg_rating', '-review_count')[:1]
    
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
        total_review_count=Count('reviews', filter=Q(reviews__is_approved=True))  # ✅ Renamed
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
        # Search in products
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
        
        # Log the search query
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
    """Product detail page"""
    product = get_object_or_404(Product, slug=slug, is_active=True)
    
    # Increment view count
    product.view_count += 1
    product.save(update_fields=['view_count'])
    
    # Log the product view
    ProductView.objects.create(
        product=product,
        user=request.user if request.user.is_authenticated else None,
        ip_address=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )
    
    # Get reviews
    reviews = Review.objects.filter(
        product=product,
        is_approved=True
    ).select_related('user').order_by('-created_at')
    
    # Calculate rating distribution
    rating_distribution = {}
    for i in range(1, 6):
        rating_distribution[i] = reviews.filter(rating=i).count()
    
    # Get related products
    related_products = Product.objects.filter(
        category=product.category,
        is_active=True
    ).exclude(id=product.id).annotate(
        avg_rating=Avg('reviews__rating', filter=Q(reviews__is_approved=True))
    )[:4]
    
    context = {
        'product': product,
        'reviews': reviews,
        'rating_distribution': rating_distribution,
        'related_products': related_products,
        'average_rating': product.average_rating,
        'total_reviews': product.total_reviews,
    }
    
    return render(request, 'reviews/product_detail.html', context)


def category_view(request, slug):
    """Category page showing all products in category"""
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
    """Brand page showing all products from brand"""
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
    """Helper function to get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


# API Views for AJAX requests
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required


@require_http_methods(["POST"])
@login_required
def mark_review_helpful(request, review_id):
    """Mark a review as helpful"""
    from .models import ReviewHelpful
    
    try:
        review = get_object_or_404(Review, id=review_id, is_approved=True)
        
        # Check if user already marked this review as helpful
        helpful, created = ReviewHelpful.objects.get_or_create(
            review=review,
            user=request.user
        )
        
        if created:
            # Increment helpful count
            review.helpful_count += 1
            review.save(update_fields=['helpful_count'])
            return JsonResponse({'status': 'added', 'count': review.helpful_count})
        else:
            # Remove helpful mark
            helpful.delete()
            review.helpful_count = max(0, review.helpful_count - 1)
            review.save(update_fields=['helpful_count'])
            return JsonResponse({'status': 'removed', 'count': review.helpful_count})
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@require_http_methods(["GET"])
def autocomplete_search(request):
    """Autocomplete suggestions for search"""
    query = request.GET.get('q', '').strip()
    suggestions = []
    
    if query and len(query) >= 2:
        # Get product suggestions
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
        
        # Get brand suggestions
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
        
        # Get category suggestions
        categories = Category.objects.filter(is_active=True).annotate(
    product_count=Count('products', filter=Q(products__is_active=True))
)
        
        for category in categories:
            suggestions.append({
                'type': 'category',
                'name': category.name,
                'url': f"/category/{category.slug}/",
                'icon': category.icon
            })
    
    return JsonResponse({'suggestions': suggestions})