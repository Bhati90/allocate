# # my_project/celery.py

# import os
# from celery import Celery
# from celery.schedules import crontab

# # Set the default Django settings module
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'allocate.settings')

# # app = Celery('allocate')

# # Using a string here means the worker doesn't have to serialize
# # the configuration object to child processes.
# app.config_from_object('django.conf:settings', namespace='CELERY')

# # Load task modules from all registered Django app configs.
# app.autodiscover_tasks()

# # ✅ DEFINE THE SCHEDULE HERE
# app.conf.beat_schedule = {
#     'process-payments-every-night': {
#         'task': 'data.tasks.run_daily_payment_processing',
#         'schedule': crontab(hour=0, minute=30), # Runs at 12:30 AM daily
#     },
# }