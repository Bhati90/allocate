from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.authtoken.views import obtain_auth_token
from .views import (
    MukkadamManagementViewSet,  # Changed
    
    AllocationViewSet
)

router = DefaultRouter()
router.register(r'mukkadam', MukkadamManagementViewSet, basename='mukkadam')
router.register(r'allocations', AllocationViewSet, basename='allocations')  # Add this
urlpatterns = [
    path('', include(router.urls)),
    path('login/', obtain_auth_token),
    
]