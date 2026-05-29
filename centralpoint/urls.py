from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    path('django-admin/', __import__('django.contrib.admin', fromlist=['site']).site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('admin-login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('admin-logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('', include('timeclock.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
