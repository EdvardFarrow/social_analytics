from django.urls import path
from .views import google_callback, google_login, ProtectedView

urlpatterns = [
    path('google/login/', google_login, name='google_login'),
    path('google/callback/', google_callback, name='google_callback'),
    path('protected/', ProtectedView.as_view(), name='protected'),
]
