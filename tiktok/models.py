from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()

class TikTokToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tiktok_token')
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    token_expiry = models.DateTimeField()

    def __str__(self):
        return f"TikTok tokens for {self.user.email}"


class TikTokVideo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tiktok_videos')
    video_id = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    create_time = models.DateTimeField()
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    shares = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.video_id
