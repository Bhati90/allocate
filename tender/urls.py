from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ActivityCatalogViewSet,
    ClusterViewSet,
    JobActivityViewSet,
    JobViewSet,
    LeaveViewSet,ExtraWorkerViewSet,
    MukkadamViewSet,
    AllocationViewSet,FarmerViewSet,
    MukkadamActivityRateViewSet,
    PlanningViewSet,search_farmers_for_cluster,search_mukkadams_for_cluster,add_farmer_plots_to_cluster,add_mukkadam_to_cluster,
    PlotViewSet,tender_dashboard,
    get_cluster_plots,get_districts,get_states,get_talukas,get_villages,
    insert_activity_between,
    reset_cluster_activity_rate,get_cluster_info,global_activity_catalog,
    search_villages,
    suggest_activity_date,cluster_activity_calendar,reset_cluster_activity_override,cluster_potential_jobs
)

from .webhook import booking_webhook,run_mukkadam_sync

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