# allocation_app/urls.py

from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import (DetailedRecommendationView, MakeCallView, UserProfileView,
   mukkadam_scorecard_details,UserListAPIView,
    mukkadam_scorecard_summary,update_activity,
    JobActivityViewSet, get_job_details,get_user_calls,get_call_details,
    AllocationViewSet,transporter_work_history,ExotelWebhookView,
    jobs_list,PaymentRequestViewSet,TransportPaymentRequestViewSet,
    activity_logs_list,allocations_list,mukkadam_work_history,
    allocations_by_mobile # ✅ Already imported
)

from .mobile_sync import(sync_messages,
     get_sync_checkpoint, sync_contacts,sync_call_logs,message_stats,
     )
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
    # path('allocation-analytics/', comprehensive_analytics, name='allocation-analytics'),
    # path('supply-health/', supply_health_dashboard, name='supply-health'),
    # path('calls/user/', get_user_calls, name='user-calls'),
    
    # Get specific call details
    path('calls/<int:call_id>/', get_call_details, name='call-details'),
    path('calls/webhook/', ExotelWebhookView.as_view(), name='exotel-webhook'),
    path('calls/make/', MakeCallView.as_view(), name='make-call'),
    # path('api/calls/status/<str:call_sid>/', CallStatusView.as_view(), name='call-status'),
    # path('api/calls/update/<str:call_sid>/', UpdateCallDetailsView.as_view(), name='update-call'),

    path('login/', obtain_auth_token, name='api-token-auth'),
    path('auth/check-mobile/', mobile_auth.check_mobile, name='check-mobile'),
    path('auth/mobile-login/', mobile_auth.mobile_login, name='mobile-login'),
    path('auth/logout/', mobile_auth.mobile_logout, name='logout'),
    # path('auth/me/', mobile_auth.get_current_user, name='current-user'),

    path('auth/me/', UserProfileView.as_view(), name='user-profile'),
    
    path('detailed-recommendations/', DetailedRecommendationView.as_view(), name='detailed-recs'),
    
    # ========================================
    # CUSTOM ENDPOINTS (BEFORE ROUTER)
    # ========================================
    path('jobs/', jobs_list, name='jobs-list'),  # Fetch from external API + enrich
    path('activity-logs/', activity_logs_list, name='activity-logs'),
    
    # ✅ ADD THIS: Allocations by mobile number
    path('allocations/by-mobile/', allocations_by_mobile, name='allocations-by-mobile'),

    path('update-activity/', update_activity, name='update_activity'),
    path('mukkadam-history/', mukkadam_work_history, name='mukkadam-work-history'),
    path('allocations/by-mobile/main/', allocations_list, name='allocations-by-mobile_main'),
    
    # ========================================
    # ROUTER ENDPOINTS (MUST BE LAST)
    # ========================================
    
    path('mukkadam-scorecard-summary/', mukkadam_scorecard_summary, name='mukkadam-scorecard-summary'),
    path('mukkadam-scorecard-details/<int:mukkadam_id>/', mukkadam_scorecard_details, name='mukkadam-scorecard-details'),



   path('job-details/<str:job_id>/', get_job_details, name='get-job-details'),
    path('users/all/', UserListAPIView.as_view(), name='user-list-api'),
    path('contacts/', sync_contacts, name='sync-contacts'),
    path('sms/', sync_messages, name='sync-sms'),
    path('sms/sync-checkpoint/', get_sync_checkpoint, name='sync-checkpoint'),
    
    # Stats
    path('sms/stats/', message_stats, name='message-stats'),
    path('call-logs/', sync_call_logs, name='sync-call-logs'),
    # path('fcm/by-mobile/', get_fcm_by_mobile),
   path('transporter/work-history/', transporter_work_history, name='transporter-work-history'),
    
    path('', include(router.urls)),
]