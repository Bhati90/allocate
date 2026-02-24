from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ActivityCatalogViewSet,
    ClusterViewSet,
    JobActivityViewSet,mukkadam_settlement_detail,raise_mukkadam_payment,
    JobViewSet,
    LeaveViewSet,ExtraWorkerViewSet,
    MukkadamViewSet,cluster_payment_dashboard,
    AllocationViewSet,FarmerViewSet,mukkadam_all_settlements,mukkadam_misc_cost_delete,mukkadam_misc_costs,
    MukkadamActivityRateViewSet,add_weekly_payment,
    PlanningViewSet,search_farmers_for_cluster,search_mukkadams_for_cluster,add_farmer_plots_to_cluster,add_mukkadam_to_cluster,
    PlotViewSet,tender_dashboard,list_all_settlements,
    get_cluster_plots,get_districts,get_states,get_talukas,get_villages,
    insert_activity_between,farmer_all_jobs_billing,farmer_job_billing,record_farmer_payment,
    reset_cluster_activity_rate,get_cluster_info,global_activity_catalog,
    search_villages,farmer_work_verification_detail,
    suggest_activity_date,cluster_activity_calendar,reset_cluster_activity_override,cluster_potential_jobs
)

from .webhook import booking_webhook,run_mukkadam_sync
from .mukkadamapp import mukkadam_workbook,farmer_verify_work,mukkadam_day_end_report,mukkadam_future_work,mukkadam_settlement_history
# Create router
router = DefaultRouter()

# Register ViewSets
router.register(r'extra-workers', ExtraWorkerViewSet, basename='extra-worker')
router.register(r'job-activities', JobActivityViewSet, basename='job-activities')
router.register(r'plots', PlotViewSet, basename='plot')

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



    path('api/mukkadam/future-work/',mukkadam_future_work),
    path('api/mukkadam/settlements/',mukkadam_settlement_history),

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


    path(
        'api/mukkadam/<int:mukkadam_id>/settlement/<str:job_id>/pay/',
        raise_mukkadam_payment,
        name='mukkadam-settlement-pay'
    ),
path('api/weekly-payment/add/', add_weekly_payment),
    # List all settlements for a mukkadam (for the new tab)
    path(
        'api/mukkadam/<int:mukkadam_id>/settlements/',
        mukkadam_all_settlements,
        name='mukkadam-all-settlements'
    ),
path('api/activity-calendar/', global_activity_catalog, name='cluster-calendar'),
 
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

  path('webhook/booking/', booking_webhook, name='booking_webhook'),
  
  ]