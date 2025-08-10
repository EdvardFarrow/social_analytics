from rest_framework import serializers
from .models import TikTokVideo

class TikTokVideoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TikTokVideo
        fields = [
            'video_id', 
            'description', 
            'create_time', 
            'views', 
            'likes', 
            'comments', 
            'shares'
        ]
