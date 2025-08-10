from django.urls import path
from .views import RegisterView, LoginPageView, LogoutView, google_callback, google_login, ProtectedView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginPageView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('google/login/', google_login, name='google_login'),
    path('google/callback/', google_callback, name='google_callback'),
    path('protected/', ProtectedView.as_view(), name='protected'),
]
