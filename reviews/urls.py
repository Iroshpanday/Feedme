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
    path('product/<slug:slug>/edit/', login_required(views.ProductUpdateView.as_view()), name='edit_product'),
    
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

    
    # Dashboard AJAX endpoints
    path('api/profile/update/', views.update_profile_ajax, name='update_profile_ajax'),
    path('api/review/<uuid:review_id>/data/', views.get_review_data_ajax, name='get_review_data'),
    path('api/review/<uuid:review_id>/update/', views.update_review_ajax, name='update_review_ajax'),
    path('api/review/<uuid:review_id>/delete/', views.delete_review_ajax, name='delete_review_ajax'),

    #reviews edit
    path('review/<uuid:review_id>/edit/', views.edit_review_view, name='edit_review'),

    #About us Page
    path('about/', views.about_us, name='about-us'),

     # Business Analytics Dashboard
# Business Analytics Dashboard
path('business/analytics/', login_required(views.business_analytics_dashboard), name='business_analytics'),

# Analytics API endpoints  
path('api/benchmark-data/', views.benchmark_data_ajax, name='benchmark_data'),
path('api/word-cloud-data/', views.word_cloud_data_ajax, name='word_cloud_data'),
path('api/export-comparison-pdf/', views.export_comparison_pdf, name='export_comparison_pdf'),
path('api/export-comparison-csv/', views.export_comparison_csv, name='export_comparison_csv'),

    
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

