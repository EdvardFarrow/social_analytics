from celery import shared_task
from .models import YouTubeToken
from .services import update_channel_and_video_stats

@shared_task
def update_all_users_youtube_stats():
    tokens = YouTubeToken.objects.all()
    for token in tokens:
        try:
            update_channel_and_video_stats(token)
        except Exception as e:
            print(f"Failed to update stats for user {token.user.email}: {e}")
