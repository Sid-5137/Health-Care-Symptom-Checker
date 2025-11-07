# from django.contrib import admin
# from django.urls import path, include
# from frontend_app import user_views as frontend_views

# urlpatterns = [
#     path('admin/', admin.site.urls),

#     # Authentication routes
#     path('login/', frontend_views.login_view, name='login'),
#     path('signup/', frontend_views.signup_view, name='signup'),
#     path('logout/', frontend_views.logout_view, name='logout'),

#     # Make Django auth use our custom login page
#     path('accounts/login/', frontend_views.login_view, name='accounts_login_redirect'),
#     path('accounts/', include('django.contrib.auth.urls')),

#     # Include app URLs with namespace
#     path('', include(('frontend_app.urls', 'frontend_app'), namespace='frontend_app')),
# ]

from django.contrib import admin
from django.urls import include, path
from frontend_app import user_views as frontend_views

urlpatterns = [
    path('admin/', admin.site.urls),

    # Make Django auth use our custom login page but keep other auth routes available.
    path('accounts/login/', frontend_views.login_view, name='accounts_login_redirect'),
    path('accounts/', include('django.contrib.auth.urls')),

    # Let the app's URLconf provide namespaced routes like frontend_app:home.
    path('', include('frontend_app.urls')),
]
