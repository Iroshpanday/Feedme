from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth.decorators import login_required

app_name = 'reviews'

urlpatterns = [
    # Main pages
    path('', views.home_view, name='home'),
    path('search/', views.search_view, name='search'),
    
    # Product management routes
    path('product/add/', views.add_product_view, name='add_product'),
    path('product/create/', views.ProductCreateView.as_view(), name='create_product'),
    
    # Product detail routes
    path('product/<slug:slug>/', views.product_detail_view, name='product_detail'),
    path('category/<slug:slug>/', views.category_view, name='category'),
    path('brand/<slug:slug>/', views.brand_view, name='brand'),
    
    # Review URLs
    path('review/add/', views.add_review_view, name='add_review'),
    path('product/<slug:slug>/review/add/', views.add_review_view, name='add_review_product'),
    path('product/<slug:slug>/review/submit/', views.submit_review_view, name='submit_review'),
    path('review/create/', views.ReviewCreateView.as_view(), name='create_review'),
    
    # AJAX endpoints
    path('api/review/<uuid:review_id>/helpful/', views.mark_review_helpful, name='mark_helpful'),
    path('api/autocomplete/', views.autocomplete_search, name='autocomplete'),
    path('api/autocomplete-brands/', views.autocomplete_brands, name='autocomplete_brands'),


    path('dashboard/', login_required(views.dashboard_view), name='dashboard'),
    path('dashboard/user/', login_required(views.user_dashboard_view), name='user_dashboard'),
    path('dashboard/business/', login_required(views.business_dashboard_view), name='business_dashboard'),

      path('products/', views.products_view, name='products'),
    
    # API endpoints
    path('api/product-autocomplete/', views.product_autocomplete, name='product_autocomplete'),
    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

