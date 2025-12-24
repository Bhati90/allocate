from rest_framework import viewsets, parsers, status, permissions
from rest_framework.response import Response
from .models import Mukkadam,ActivityLog,Allocation
from .serializers import MukkadamFullSerializer,MukkadamQuickRegistrationSerializer, MukkadamListSerializer,MukkadamDropdownSerializer,AllocationSerializer
from rest_framework.permissions import AllowAny
from rest_framework.decorators import action
from rest_framework.response import Response
import json

from rest_framework.parsers import JSONParser, FormParser, MultiPartParser


class MukkadamManagementViewSet(viewsets.ModelViewSet):
    queryset = Mukkadam.objects.all().order_by('-updated_at')
    permission_classes = [AllowAny]  # Make it public or use IsAuthenticated
    parser_classes = (parsers.MultiPartParser, parsers.FormParser)

    def get_serializer_class(self):
        if self.action == 'list':
            return MukkadamListSerializer
        return MukkadamFullSerializer

    def create(self, request, *args, **kwargs):
        return self.save_mukkadam(request, is_update=False)

    def update(self, request, *args, **kwargs):
        return self.save_mukkadam(request, is_update=True)

    def save_mukkadam(self, request, is_update=False):
        try:
            data_str = request.data.get('data')
            if not data_str:
                return Response({"error": "No 'data' field provided"}, status=400)

            data = json.loads(data_str)

            # Handle Files
            file_fields = ['profile_photo', 'aadhar_card', 'pan_card', 'bank_proof']
            for field in file_fields:
                if field in request.FILES:
                    data[field] = request.FILES[field]

            if is_update:
                instance = self.get_object()
                serializer = MukkadamFullSerializer(instance, data=data, partial=True)
            else:
                serializer = MukkadamFullSerializer(data=data)

            if serializer.is_valid():
                if is_update:
                    mukkadam = serializer.save()
                    
                    # --- TRACKING LOGIC STARTS HERE ---
                    # Check if availability specifically was changed
                    if 'team_availabilities' in data:
                        ActivityLog.objects.create(
                            mukkadam=mukkadam,
                            user=request.user,
                            action_type="Availability Update",
                            details=f"Updated availability slots. Total slots: {len(data['team_availabilities'])}"
                        )
                    else:
                        # Generic Profile Update
                        ActivityLog.objects.create(
                            mukkadam=mukkadam,
                            user=request.user,
                            action_type="Profile Update",
                            details="Updated general profile details"
                        )
                    # --- TRACKING LOGIC ENDS HERE ---
                    
                else:
                    # New Registration
                    mukkadam = serializer.save(created_by=request.user)
                    ActivityLog.objects.create(
                        mukkadam=mukkadam,
                        user=request.user,
                        action_type="Registration",
                        details="Created new Mukkadam profile"
                    )
                
                return Response(serializer.data, status=status.HTTP_201_CREATED if not is_update else status.HTTP_200_OK)
            
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            return Response({"error": str(e)}, status=500)
        

    @action(detail=False, methods=['get'])
    def dropdown_list(self, request):
        mukkadams = Mukkadam.objects.all().only('id', 'mukkadam_name', 'mobile_numbers', 'village')
        serializer = MukkadamDropdownSerializer(mukkadams, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], permission_classes=[AllowAny])
    def minimal_list(self, request):
        """
        Public endpoint - No authentication required
        GET /api/mukkadam/minimal_list/
        """
        mukkadams = Mukkadam.objects.all().values(
            'id', 'mukkadam_name', 'mobile_numbers', 
            'village', 'crew_size', 'has_smartphone','preferred_work_locations', 'work_mode'
        )
        return Response(list(mukkadams))
    

    @action(
    detail=False,
    methods=['post'],
    permission_classes=[AllowAny],
    parser_classes=[JSONParser]   # ✅ THIS FIXES IT
    )
    def quick_register(self, request):
        serializer = MukkadamQuickRegistrationSerializer(data=request.data)

        if serializer.is_valid():
            existing = Mukkadam.objects.filter(
                mobile_numbers=serializer.validated_data['mobile_numbers']
            ).first()

            if existing:
                return Response(
                    {
                        'error': 'Mukkadam with this mobile number already exists',
                        'existing_mukkadam': {
                            'id': existing.id,
                            'name': existing.mukkadam_name,
                            'village': existing.village
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

            mukkadam = serializer.save(
                has_smartphone='no',
                transport_mode='no_vehicle',
                work_mode='daily_up_down',
                created_by=request.user if request.user.is_authenticated else None
            )

            ActivityLog.objects.create(
                mukkadam=mukkadam,
                user=request.user if request.user.is_authenticated else None,
                action_type="Quick Registration",
                details=f"Quick registered with {mukkadam.crew_size} workers"
            )

            return Response(
                {
                    'message': 'Mukkadam registered successfully',
                    'data': serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


    

from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q, Count, Sum
from django_filters.rest_framework import DjangoFilterBackend

from .models import  Mukkadam

from rest_framework.permissions import AllowAny

class AllocationViewSet(viewsets.ModelViewSet):
    """
    API endpoint for work completion
    """
    queryset = Allocation.objects.all().select_related('job','mukkadam')
    serializer_class = AllocationSerializer
    permission_classes = [AllowAny]  # Or [IsAuthenticated] if you want
    
    def create(self, request, *args, **kwargs):
        """
        POST /api/work-completions/
        Body: {
            "farmer_work_id": "WORK-2024-001",
            "mukkadam": 2,
            "transport_provider_name": "ABC Transport",
            "mukkadam_price": 5000.00,
            "transport_price": 1500.00
        }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {
                'message': 'Allocation recorded successfully',
                'data': serializer.data
            },
            status=status.HTTP_201_CREATED
        )
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by job ID if provided
        work_id = self.request.query_params.get('work_id')
        if work_id:
            queryset = queryset.filter(farmer_work_id=work_id)
        
        # Filter by mukkadam name if provided
        mukkadam = self.request.query_params.get('mukkadam')
        if mukkadam:
            queryset = queryset.filter(mukkadam_name__icontains=mukkadam)
        
        return queryset