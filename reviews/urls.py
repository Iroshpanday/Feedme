from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    # Main pages
    path('', views.home_view, name='home'),
    path('search/', views.search_view, name='search'),
    
    # Product management routes (ADD THESE FIRST)
    path('product/add/', views.add_product_view, name='add_product'),
    path('product/create/', views.ProductCreateView.as_view(), name='create_product'),
    
    # Product detail routes (MOVE THESE AFTER THE ADD ROUTES)
    path('product/<slug:slug>/', views.product_detail_view, name='product_detail'),
    path('category/<slug:slug>/', views.category_view, name='category'),
    path('brand/<slug:slug>/', views.brand_view, name='brand'),
    
    # AJAX endpoints
    path('api/review/<uuid:review_id>/helpful/', views.mark_review_helpful, name='mark_helpful'),
    path('api/autocomplete/', views.autocomplete_search, name='autocomplete'),
    path('api/autocomplete-brands/', views.autocomplete_brands, name='autocomplete_brands'),
]