from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    jobs_list,
    AllocationViewSet,
     # Add this
)

router = DefaultRouter()
router.register(r'allocations', AllocationViewSet, basename='allocations')

urlpatterns = [
    path('', include(router.urls)),
    path('login/', obtain_auth_token),
    path('jobs/', jobs_list),
     # Add this
]