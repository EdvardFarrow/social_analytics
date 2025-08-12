import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'social_analytics.settings')

app = Celery('social_analytics')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()




app.conf.beat_schedule = {
    'update-youtube-stats-daily': {
        'task': 'youtube.tasks.update_all_users_youtube_stats',
        'schedule': crontab(minute=0, hour=3),  
    },
}
