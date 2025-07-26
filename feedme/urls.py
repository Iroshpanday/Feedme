"""
URL configuration for feedme project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path,include
from myapp import views
from django.views.generic import TemplateView
from reviews.views import CustomSignupView
from allauth.account.views import LoginView
urlpatterns = [
    path('admin/', admin.site.urls),
    # path('', TemplateView.as_view(template_name='home.html'), name='home'),
    
    # path('',include('myapp.urls')),
    path('accounts/', include('allauth.urls')),  # Allauth URLs
    path('accounts/signup/', CustomSignupView.as_view(), name='account_signup'),
    path('accounts/login/', LoginView.as_view(), name='account_login'),

    path('', include('reviews.urls')),
    
    

]

