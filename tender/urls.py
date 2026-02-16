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
    PlanningViewSet,
    PlotViewSet,
    get_cluster_plots,get_districts,get_states,get_talukas,get_villages,
    reset_cluster_activity_rate,get_cluster_info,
    suggest_activity_date,cluster_activity_calendar,reset_cluster_activity_override,cluster_potential_jobs
)

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

    path('locations/states/', get_states, name='get-states'),
    path('locations/districts/', get_districts, name='get-districts'),
    path('locations/talukas/', get_talukas, name='get-talukas'),
    path('api/clusters/<int:cluster_id>/info/', get_cluster_info, name='cluster-info'),
    path('locations/villages/', get_villages, name='get-villages'),
path('api/activity-schedule/suggest-date/', suggest_activity_date, name='suggest-date'),
path('api/clusters/<int:cluster_id>/activity-calendar/', cluster_activity_calendar, name='cluster-calendar'),
    path('api/clusters/<int:cluster_id>/activity-calendar/<int:activity_id>/reset/', reset_cluster_activity_override, name='reset-override'),
        path('api/clusters/<int:cluster_id>/activity-calendar/<int:activity_id>/reset-rate/', reset_cluster_activity_rate, name='reset-rate'),
    path('api/clusters/<int:cluster_id>/plots/', get_cluster_plots, name='cluster-plots'),
        path( "api/clusters/<int:cluster_id>/potential_jobs/",
  cluster_potential_jobs,
  name="cluster-potential-jobs")
  
  ]