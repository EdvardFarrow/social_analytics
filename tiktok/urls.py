from django.urls import path
from .views import TikTokLoginView, TikTokCallbackView, TikTokVideosView

urlpatterns = [
    path('login/', TikTokLoginView.as_view(), name='tiktok-login'),
    path('callback/', TikTokCallbackView.as_view(), name='tiktok-callback'),
    path('videos/', TikTokVideosView.as_view(), name='tiktok-videos'),
]
