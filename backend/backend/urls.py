from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import register_user

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/auth/register/", register_user),
    path("api/auth/login/", TokenObtainPairView.as_view()),
    path("api/auth/refresh/", TokenRefreshView.as_view()),
    path("api/shopping/", include("shopping.urls")),
    path("api/", include("voice.urls")),
]
