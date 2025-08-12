from django.core.management.base import BaseCommand
from youtube.models import YouTubeToken
from youtube.services import update_channel_and_video_stats

class Command(BaseCommand):
    help = "Update stats Youtube channels and video for all users"

    def handle(self, *args, **kwargs):
        tokens = YouTubeToken.objects.all()
        for token in tokens:
            try:
                update_channel_and_video_stats(token)
                self.stdout.write(self.style.SUCCESS(f"Update for user {token.user.email}"))
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error update for {token.user.email}: {e}"))
