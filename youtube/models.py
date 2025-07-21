from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class YouTubeChannel(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='youtube_channels')
    channel_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class YouTubeVideo(models.Model):
    channel = models.ForeignKey(YouTubeChannel, on_delete=models.CASCADE, related_name='videos')
    video_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    published_at = models.DateTimeField()
    views = models.IntegerField(default=0)
    likes = models.IntegerField(default=0)
    comments = models.IntegerField(default=0)

    def __str__(self):
        return self.title
