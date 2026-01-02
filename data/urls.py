# allocation_app/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    JobActivityViewSet,
    AllocationViewSet,
    jobs_list,
    activity_logs_list,
    allocations_by_mobile  # ✅ Already imported
)
from . import mobile_auth

router = DefaultRouter()
router.register(r'job-activities', JobActivityViewSet, basename='job-activity')
router.register(r'allocations', AllocationViewSet, basename='allocation')

urlpatterns = [
    # ========================================
    # AUTHENTICATION ENDPOINTS
    # ========================================
    path('login/', obtain_auth_token, name='api-token-auth'),
    path('auth/check-mobile/', mobile_auth.check_mobile, name='check-mobile'),
    path('auth/mobile-login/', mobile_auth.mobile_login, name='mobile-login'),
    path('auth/logout/', mobile_auth.mobile_logout, name='logout'),
    path('auth/me/', mobile_auth.get_current_user, name='current-user'),

    # ========================================
    # CUSTOM ENDPOINTS (BEFORE ROUTER)
    # ========================================
    path('jobs/', jobs_list, name='jobs-list'),  # Fetch from external API + enrich
    path('activity-logs/', activity_logs_list, name='activity-logs'),
    
    # ✅ ADD THIS: Allocations by mobile number
    path('allocations/by-mobile/', allocations_by_mobile, name='allocations-by-mobile'),
    
    # ========================================
    # ROUTER ENDPOINTS (MUST BE LAST)
    # ========================================
    path('', include(router.urls)),
]