# allocation_app/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (get_fcm_by_mobile,
    JobActivityViewSet,
    AllocationViewSet,
    jobs_list,PaymentRequestViewSet,TransportPaymentRequestViewSet,
    activity_logs_list,allocations_list,mukkadam_work_history,
    allocations_by_mobile # ✅ Already imported
)

from .mobile_sync import(
     sync_contacts,sync_call_logs,
     sync_messages)
from . import mobile_auth

router = DefaultRouter()
router.register(r'job-activities', JobActivityViewSet, basename='job-activity')
router.register(r'allocations', AllocationViewSet, basename='allocation')
router.register(r'payment-requests', PaymentRequestViewSet, basename='payment-request')
router.register(r'transport-payment-requests', TransportPaymentRequestViewSet, basename='transport-payment-request')



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


    path('mukkadam-history/', mukkadam_work_history, name='mukkadam-work-history'),
    path('allocations/by-mobile/main/', allocations_list, name='allocations-by-mobile_main'),
    
    # ========================================
    # ROUTER ENDPOINTS (MUST BE LAST)
    # ========================================

    
    path('contacts/', sync_contacts, name='sync-contacts'),
    path('sms/', sync_messages, name='sync-sms'),
    path('call-logs/', sync_call_logs, name='sync-call-logs'),
    path('fcm/by-mobile/', get_fcm_by_mobile),
   
    
    path('', include(router.urls)),
]