from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView
from frontend_app import user_views as frontend_views

urlpatterns = [
    path('admin/', admin.site.urls),
    # Project-level names for compatibility with templates using non-namespaced URLs
    path('login/', frontend_views.login_view, name='login'),
    path('signup/', frontend_views.signup_view, name='signup'),
    path('logout/', frontend_views.logout_view, name='logout'),
    # Redirect the default auth login to our custom login page for consistent styling
    path('accounts/login/', RedirectView.as_view(pattern_name='frontend_app:login', permanent=False), name='accounts_login_redirect'),
    path('accounts/', include('django.contrib.auth.urls')),
    path('', include(('frontend_app.urls', 'frontend_app'), namespace='frontend_app')),
]
