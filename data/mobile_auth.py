# core/mobile_auth.py - COMPLETE VERSION

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth.models import User
from django.views.decorators.csrf import csrf_exempt
from .models import UserProfile
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@method_decorator(csrf_exempt, name='dispatch')
@api_view(['POST'])
def mobile_login(request):
    """Mobile login endpoint"""
    try:
        print("kzjdflkgdfk")
        mobile_number = request.data.get('mobile_number', '').strip()
        full_name = request.data.get('full_name', '').strip()
        
        if not mobile_number or len(mobile_number) != 10:
            return Response(
                {'error': 'Valid 10-digit mobile number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            profile = UserProfile.objects.select_related('user').get(mobile_number=mobile_number)
            user = profile.user
            is_new_user = False
            
        except UserProfile.DoesNotExist:
            if not full_name:
                return Response(
                    {
                        'is_new': True,
                        'error': 'Full name required for new registration'
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            username = f"user_{mobile_number}"
            
            try:
                user = User.objects.get(username=username)
            except User.DoesNotExist:
                user = User.objects.create_user(username=username)
            
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'mobile_number': mobile_number,
                    'full_name': full_name,
                    'role': 'staff',
                    'is_mobile_verified': True
                }
            )
            
            if not created:
                profile.mobile_number = mobile_number
                profile.full_name = full_name
                profile.is_mobile_verified = True
                profile.save()
            
            is_new_user = True
        
        token, _ = Token.objects.get_or_create(user=user)
        
        return Response({
            'token': token.key,
            'is_new_user': is_new_user,
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': profile.full_name,
                'mobile_number': mobile_number,
                'role': profile.role
            }
        })
    except Exception as e:
        import traceback
        traceback.print_exc()


@api_view(['POST'])
@csrf_exempt
def check_mobile(request):
    """
    Check if mobile number exists in system (company team member)
    
    POST /api/auth/check-mobile/
    {
        "mobile_number": "9876543210"
    }
    """
    mobile_number = request.data.get('mobile_number', '').strip()
    
    if not mobile_number:
        return Response(
            {'error': 'Mobile number is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate mobile number format (10 digits)
    if not mobile_number.isdigit() or len(mobile_number) != 10:
        return Response(
            {'error': 'Invalid mobile number. Must be 10 digits.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        # Check if user profile exists with this mobile
        profile = UserProfile.objects.select_related('user').get(mobile_number=mobile_number)
        
        return Response({
            'exists': True,
            'can_proceed': True,
            'user_id': profile.user.id,
            'username': profile.user.username,
            'full_name': profile.full_name,
            'role': profile.role,
            'mobile_number': mobile_number
        })
        
    except UserProfile.DoesNotExist:
        # Mobile number not registered as team member
        return Response({
            'exists': False,
            'can_proceed': False,
            'message': 'This mobile number is not registered. Please contact admin.'
        })


@api_view(['POST'])
def mobile_logout(request):
    """
    Logout mobile user (delete token)
    
    POST /api/auth/logout/
    Headers: {"Authorization": "Token xyz..."}
    """
    if request.user and request.user.is_authenticated:
        try:
            # Delete user's token
            request.user.auth_token.delete()
            return Response({'message': 'Logged out successfully'})
        except Exception as e:
            print(f"Logout error: {e}")
    
    return Response({'message': 'Logged out'})


@api_view(['GET'])
def get_current_user(request):
    """
    Get current logged-in user details
    
    GET /api/auth/me/
    Headers: {"Authorization": "Token xyz..."}
    """
    if request.user and request.user.is_authenticated:
        try:
            profile = request.user.profile
            
            return Response({
                'id': request.user.id,
                'username': request.user.username,
                'full_name': profile.full_name or request.user.username,
                'mobile_number': profile.mobile_number,
                'role': profile.role,
                'is_mobile_verified': profile.is_mobile_verified
            })
        except:
            return Response({
                'id': request.user.id,
                'username': request.user.username
            })
    
    return Response(
        {'error': 'Not authenticated'},
        status=status.HTTP_401_UNAUTHORIZED
    )