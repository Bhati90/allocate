# allocation_app/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    JobActivityViewSet,
    AllocationViewSet,
    jobs_list,
    activity_logs_list
)

router = DefaultRouter()
router.register(r'job-activities', JobActivityViewSet, basename='job-activity')
router.register(r'allocations', AllocationViewSet, basename='allocation')

urlpatterns = [
    path('', include(router.urls)),
    path('jobs/', jobs_list, name='jobs-list'),  # Fetch from external API + enrich
    path('activity-logs/', activity_logs_list, name='activity-logs'),
]