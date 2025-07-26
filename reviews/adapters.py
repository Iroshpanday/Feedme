# reviews/adapters.py
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from .models import UserProfile

class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)
        if commit:
            user.save()
            # Create user profile with business user flag if using custom form
            if hasattr(form, 'cleaned_data') and 'is_business_user' in form.cleaned_data:
                UserProfile.objects.create(
                    user=user,
                    is_business_user=form.cleaned_data.get('is_business_user', False)
                )
            else:
                # Create default profile for social signups
                UserProfile.objects.create(user=user, is_business_user=False)
        return user

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    def save_user(self, request, sociallogin, form=None):
        user = super().save_user(request, sociallogin, form)
        # Create user profile for social account users
        profile, created = UserProfile.objects.get_or_create(
            user=user,
            defaults={'is_business_user': False}
        )
        return user