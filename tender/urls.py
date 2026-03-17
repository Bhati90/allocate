from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token

from .views import (
    ActivityCatalogViewSet,
    ClusterViewSet,
    JobActivityViewSet,mukkadam_settlement_detail,raise_mukkadam_payment,
    JobViewSet,MakeCallViews,send_farmer_otp,verify_farmer_otp,
    LeaveViewSet,ExtraWorkerViewSet,send_start_otp,verify_start_otp,submit_day_end_report,verify_end_otp,resolve_dispute,
    MukkadamViewSet,cluster_payment_dashboard,get_payment_proof_presign,save_payment_proof,
    AllocationViewSet,FarmerViewSet,mukkadam_all_settlements,mukkadam_misc_cost_delete,mukkadam_misc_costs,
    MukkadamActivityRateViewSet,add_weekly_payment,UserProfileView,UserListAPIView,mukkadam_payment_overview,verify_misc_cost,
    PlanningViewSet,search_farmers_for_cluster,search_mukkadams_for_cluster,add_farmer_plots_to_cluster,add_mukkadam_to_cluster,
    PlotViewSet,tender_dashboard,list_all_settlements,pay_mukkadam_settlement,add_misc_cost,
    get_cluster_plots,get_districts,get_states,get_talukas,get_villages,UserSearchView,cluster_insights,
    insert_activity_between,farmer_all_jobs_billing,farmer_job_billing,record_farmer_payment,payment_overview,
    reset_cluster_activity_rate,get_cluster_info,global_activity_catalog,JobNoteViewSet,activity_dashboard,
    search_villages,farmer_work_verification_detail,tender_activity_count_from_api,mark_allocation_complete,
    suggest_activity_date,cluster_activity_calendar,reset_cluster_activity_override,cluster_potential_jobs
)

from .webhook import booking_webhook,run_mukkadam_sync,send_farmer_bill_to_webhook,farmer_payment_webhook
from .mukkadamapp import mukkadam_workbook,farmer_verify_work,mukkadam_day_end_report,mukkadam_future_work,mukkadam_settlement_history,mukkadam_earnings
# Create router
from django.views.decorators.csrf import csrf_exempt
from .insight import ClusterInsightsView,GlobalInsightsView,GlobalDayInsightsView
router = DefaultRouter()


from .updown import updown_allocation_list,updown_complete_allocation
# Register ViewSets
router.register(r'extra-workers', ExtraWorkerViewSet, basename='extra-worker')
router.register(r'job-activities', JobActivityViewSet, basename='job-activities')
router.register(r'plots', PlotViewSet, basename='plot')
router.register(r'job-notes', JobNoteViewSet, basename='job-notes')
#
router.register(r'activities', ActivityCatalogViewSet, basename='activity')
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'mukkadams', MukkadamViewSet, basename='mukkadam')
router.register(r'allocations', AllocationViewSet, basename='allocation')
router.register(r'mukkadam-rates', MukkadamActivityRateViewSet, basename='mukkadam-rate')
router.register(r'farmers', FarmerViewSet, basename='farmer')


# urls.py

router.register(r'mukkadam-rates', MukkadamActivityRateViewSet, basename='mukkadam-rates')


router.register(r'clusters', ClusterViewSet, basename='cluster')
router.register(r'leaves', LeaveViewSet, basename='leave')
router.register(r'planning', PlanningViewSet, basename='planning')
urlpatterns = [
    path('api/', include(router.urls)),

    path('api/tender-activity-count/', tender_activity_count_from_api, name='tender_activity_count_from_api'),
path('api/payment-overview/', payment_overview, name='payment_overview'),
# path('api/activities/insert_between/', insert_activity_between, name='insert_activity_between'),
path('locations/search_villages/', search_villages),
    path('locations/states/', get_states, name='get-states'),
    path('locations/districts/', get_districts, name='get-districts'),
    path('locations/talukas/', get_talukas, name='get-talukas'),
    path('api/clusters/<int:cluster_id>/info/', get_cluster_info, name='cluster-info'),
    path('locations/villages/', get_villages, name='get-villages'),
path('api/activity-schedule/suggest-date/', suggest_activity_date, name='suggest-date'),
path('api/clusters/<int:cluster_id>/activity-calendar/', cluster_activity_calendar, name='cluster-calendar'),
path('api/settlements/', list_all_settlements, name='list-settlements'),
    path(
        'api/mukkadam/<int:mukkadam_id>/settlement/<str:job_id>/',
        mukkadam_settlement_detail,
        name='mukkadam-settlement-detail'
    ),


   
path('api/mukkadam/<int:mukkadam_id>/updown-allocations/',
       updown_allocation_list, name='updown-allocation-list'),
  path('api/mukkadam/<int:mukkadam_id>/updown-allocations/<int:allocation_id>/complete/',
       updown_complete_allocation, name='updown-complete-allocation'),
path('api/farmer-payment/webhook/', farmer_payment_webhook),



path('api/attendance/send-start-otp/',       send_start_otp,       name='send-start-otp'),
    path('api/attendance/verify-start-otp/',     verify_start_otp,     name='verify-start-otp'),
    path('api/attendance/submit-day-end-report/', submit_day_end_report, name='submit-day-end-report'),
    path('api/attendance/verify-end-otp/',       verify_end_otp,       name='verify-end-otp'),
    path('api/attendance/resolve-dispute/',      resolve_dispute,      name='resolve-dispute'),
    path('api/payments/proof-presign/',          get_payment_proof_presign, name='proof-presign'),
    path('api/payments/save-proof/',            save_payment_proof,   name='save-proof'),

path('api/attendance/send-farmer-otp/', send_farmer_otp),
path('api/attendance/verify-farmer-otp/', verify_farmer_otp),
    # path('api/attendance/send-otp/',send_otp),

    #     path('api/attendance/end/send-otp/',send_otp_simple),
    #     path('api/attendance/end/verify-otp/',verify_otp_simple),

    # path('api/attendance/verify-otp/',verify_otp),
path('api/mukkadams/<int:mukkadam_id>/earnings/', mukkadam_earnings),


    path('ap/calls/make/web/', MakeCallViews.as_view(), name='make-call'),



    path('api/mukkadam/future-work/',mukkadam_future_work),
    # path('api/mukkadam/settlements/',mukkadam_settlement_history),
path('api/mukkadams/<int:mukkadam_id>/settlement-history/',mukkadam_settlement_history),
path('api/mukkadam/workbook/', mukkadam_workbook, name='mukkadam_workbook'),

path ('api/mukkadam/day-end-report/',mukkadam_day_end_report ),

path('api/mukkadam/farmer-verify-work/',farmer_verify_work,name = 'farmer_response'),
path('api/mukkadam/<int:mukkadam_id>/job/<str:job_id>/misc/', mukkadam_misc_costs),
path('api/mukkadam/<int:mukkadam_id>/job/<str:job_id>/misc/<int:cost_id>/', mukkadam_misc_cost_delete),
    path('api/farmer/<str:farmer_id>/billing/', farmer_all_jobs_billing),
path('api/farmer/<str:farmer_id>/job/<str:job_id>/billing/', farmer_job_billing),
path('api/farmer/<str:farmer_id>/job/<str:job_id>/payment/', record_farmer_payment),

path('api/farmer/verify-work/', farmer_verify_work, name='farmer_verify_work'),           # POST
path('api/farmer/work-reports/', farmer_work_verification_detail, name='farmer_work_reports'),  # GET

path('api/cluster/<int:cluster_id>/payment-dashboard/', cluster_payment_dashboard),

path('api/insights/', cluster_insights, name='cluster_insights'),

path('api/farmer-bill/send-webhook/', send_farmer_bill_to_webhook),
path('api/allocations/<int:allocation_id>/mark_complete/', mark_allocation_complete),

path('api/activity-dashboard/', activity_dashboard, name='activity-dashboard'),

    path('api/mukkadam/<int:mukkadam_id>/settlement/<str:job_id>/pay/',
     pay_mukkadam_settlement),

# ── Weekly payment (UPDATE — needs mode/notes/proof_s3_key) ─────────────────
path('api/weekly-payment/add/',                  add_weekly_payment),           # already exists, update view

path('api/mukkadam-payment-overview/', mukkadam_payment_overview, name='mukkadam_payment_overview'),
path('api/mukkadam-weekly-payment/',  add_weekly_payment,          name='add_weekly_payment'),
path('api/mukkadam-misc-cost/<int:cost_id>/verify/',verify_misc_cost, name='verify_misc_cost'),


# ── Misc costs (UPDATE — needs proof_s3_key) ────────────────────────────────
path('api/mukkadam/<int:mukkadam_id>/job/<str:job_id>/misc/',     add_misc_cost),
# path('api/mukkadam/<int:mukkadam_id>/job/<str:job_id>/misc/<int:cost_id>/', delete_misc_cost),

# path('api/weekly-payment/add/', add_weekly_payment),
    # List all settlements for a mukkadam (for the new tab)
    path(
        'api/mukkadam/<int:mukkadam_id>/settlements/',
        mukkadam_all_settlements,
        name='mukkadam-all-settlements'
    ),
path('api/activity-calendar/', global_activity_catalog, name='cluster-calendar'),
     path('ap/login/', csrf_exempt(obtain_auth_token), name='api-token-auth'),
    path('api/clusters/<int:cluster_id>/activity-calendar/<int:activity_id>/reset/', reset_cluster_activity_override, name='reset-override'),
        path('api/clusters/<int:cluster_id>/activity-calendar/<int:activity_id>/reset-rate/', reset_cluster_activity_rate, name='reset-rate'),
    path('api/clusters/<int:cluster_id>/plots/', get_cluster_plots, name='cluster-plots'),
        path( "api/clusters/<int:cluster_id>/potential_jobs/",
  cluster_potential_jobs,
  name="cluster-potential-jobs"),

  path('api/tender-dashboard/', tender_dashboard, name='tender-dashboard'),

path('api/sync/mukkadams/', run_mukkadam_sync),


path('api/cluster/<int:cluster_id>/search_farmers/', search_farmers_for_cluster),
path('api/cluster/<int:cluster_id>/add_farmer/', add_farmer_plots_to_cluster),
path('api/cluster/<int:cluster_id>/search_mukkadams/', search_mukkadams_for_cluster),
path('api/cluster/<int:cluster_id>/add_mukkadam/', add_mukkadam_to_cluster),


path('api/clusters/<int:cluster_id>/insights/', ClusterInsightsView.as_view(),
         name='cluster-insights'),

path('api/tender-global-insights/', GlobalInsightsView.as_view(),
         name='global-insights'),


    path('auth/me/', UserProfileView.as_view(), name='user-profile'),
    
        path('users/all/', UserListAPIView.as_view(), name='user-list-api'),


path('api/users/search/', UserSearchView.as_view(), name='user-search'),


path('api/tender-global-day-insights/', GlobalDayInsightsView.as_view(),
         name='global-insights'),


  path('webhook/booking/', booking_webhook, name='booking_webhook'),
  
  ]