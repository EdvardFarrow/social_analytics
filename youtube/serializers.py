from rest_framework import serializers
from .models import YouTubeChannel, YouTubeVideo, YouTubeChannelStats


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


class YouTubeChannelSerializer(serializers.ModelSerializer):
    videos = YouTubeVideoSerializer(many=True, read_only=True)
    new_subs = serializers.IntegerField()
    lost_subs = serializers.IntegerField()

    class Meta:
        model = YouTubeChannel
        fields = [
            'id',
            'channel_id',
            'title',
            'description',
            'created_at',
            'videos',
            'new_subs',
            'lost_subs',
        ]


class YouTubeChannelStatsSerializer(serializers.ModelSerializer):
    class Meta:
        model = YouTubeChannelStats
        fields = [
            'channel_id', 
            'title', 
            'subscriber_count', 
            'view_count', 
            'video_count',
            'last_updated'
            ]
