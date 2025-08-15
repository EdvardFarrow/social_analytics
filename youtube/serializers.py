from rest_framework import serializers
from .models import (
    YouTubeChannel, 
    YouTubeVideo, 
    YoutubeDailyStats,
    YoutubeAudienceDemographics,
)

class YouTubeVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = YouTubeVideo
        fields = [
            'id',
            'video_id',
            'title',
            'published_at',
            'views',
            'likes',
            'comments',
        ]

# Сериализатор для ежедневной статистики канала
class YoutubeDailyStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = YoutubeDailyStats
        fields = [
            'date',
            'subscribers_gained',
            'subscribers_lost',
            'views',
            'likes',
            'comments',
            'estimated_minutes_watched',
        ]

# Сериализатор для демографии аудитории
class YoutubeAudienceDemographicsSerializer(serializers.ModelSerializer):
    class Meta:
        model = YoutubeAudienceDemographics
        fields = [
            'age_group',
            'gender',
            'viewer_percentage',
        ]

class YouTubeChannelSerializer(serializers.ModelSerializer):
    videos = YouTubeVideoSerializer(many=True, read_only=True)
    daily_stats = YoutubeDailyStatsSerializer(many=True, read_only=True)
    demographics = YoutubeAudienceDemographicsSerializer(many=True, read_only=True)
    
    class Meta:
        model = YouTubeChannel
        fields = [
            'id',
            'channel_id',
            'title',
            'description',
            'created_at',
            'videos',
            'daily_stats',
            'demographics',
        ]