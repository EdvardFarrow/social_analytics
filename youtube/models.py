from django.db import models
from django.conf import settings

class YouTubeChannel(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='youtube_channels')
    channel_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title

class YouTubeVideo(models.Model):
    channel = models.ForeignKey(YouTubeChannel, on_delete=models.CASCADE, related_name='videos')
    video_id = models.CharField(max_length=255, unique=True)
    title = models.CharField(max_length=255)
    published_at = models.DateTimeField()
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)
    
    def __str__(self):
        return self.title

# Модель для ежедневной статистики канала (из Analytics API)
class YoutubeDailyStats(models.Model):
    channel = models.ForeignKey(YouTubeChannel, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField()
    subscribers_gained = models.IntegerField(default=0)
    subscribers_lost = models.IntegerField(default=0)
    views = models.BigIntegerField(default=0)
    estimated_minutes_watched = models.BigIntegerField(default=0)
    likes = models.BigIntegerField(default=0)
    comments = models.BigIntegerField(default=0)

    class Meta:
        unique_together = ('channel', 'date')
        ordering = ['date']
        verbose_name_plural = 'YouTube Daily Stats'

    def __str__(self):
        return f'{self.channel.title} - {self.date}'

# Модель для демографии аудитории (из Analytics API)
class YoutubeAudienceDemographics(models.Model):
    channel = models.ForeignKey(YouTubeChannel, on_delete=models.CASCADE)
    age_group = models.CharField(max_length=60)
    gender = models.CharField(max_length=60)
    views = models.IntegerField(default=0)
    watch_time_minutes = models.FloatField(default=0)
    viewer_percentage = models.FloatField(null=True, blank=True)

    class Meta:
        unique_together = ('channel', 'age_group', 'gender')
        verbose_name_plural = "YouTube Audience Demographics"
    
    def __str__(self):
        return f"{self.channel.title} - {self.age_group} - {self.gender}"


# Модель для ежедневной статистики видео (снимки)
class YouTubeVideoDailyStats(models.Model):
    video = models.ForeignKey(YouTubeVideo, on_delete=models.CASCADE, related_name='daily_stats')
    date = models.DateField()
    views = models.PositiveIntegerField(default=0)
    likes = models.PositiveIntegerField(default=0)
    comments = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('video', 'date')
        ordering = ['date']
        verbose_name_plural = 'YouTube Video Daily Stats'

    def __str__(self):
        return f'{self.video.title} - {self.date}'