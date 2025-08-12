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


class YouTubeChannelStats(models.Model):
    channel_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    subscriber_count = models.PositiveIntegerField()
    view_count = models.PositiveIntegerField()
    video_count = models.PositiveIntegerField()
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.title} ({self.channel_id})"
    
    
class YouTubeToken(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='youtube_token')
    access_token = models.TextField()
    refresh_token = models.TextField()
    token_expiry = models.DateTimeField()  

    def __str__(self):
        return f"Tokens for {self.user.email}"
    

class ChannelDailyStat(models.Model):
    channel_id = models.ForeignKey('YouTubeChannel', null=True, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField()  
    subscribers = models.BigIntegerField(default=0)
    views = models.BigIntegerField(default=0)
    video_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('channel_id', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.channel_id} — {self.date}"


class VideoDailyStat(models.Model):
    video_id = models.ForeignKey('YouTubeVideo', null=True, on_delete=models.CASCADE, related_name='daily_stats')
    channel_id = models.CharField(null=True, max_length=50, db_index=True)
    date = models.DateField(db_index=True)
    title = models.CharField(null=True, max_length=225)
    views = models.PositiveIntegerField()
    likes = models.PositiveIntegerField()
    comments = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('video_id', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.video_id.video_id} — {self.date}"    