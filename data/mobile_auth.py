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
    """
    Mobile login endpoint with smart auto-generated names
    """
    try:
        print("📱 Mobile Login Request Received")
        mobile_number = request.data.get('mobile_number', '').strip()
        full_name = request.data.get('full_name', '').strip()
        
        # Validate mobile number
        if not mobile_number or len(mobile_number) != 10:
            return Response(
                {'error': 'Valid 10-digit mobile number required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not mobile_number.isdigit():
            return Response(
                {'error': 'Mobile number must contain only digits'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Existing user
            profile = UserProfile.objects.select_related('user').get(mobile_number=mobile_number)
            user = profile.user
            is_new_user = False
            
            print(f"✅ Existing user found: {profile.full_name} ({mobile_number})")
            
        except UserProfile.DoesNotExist:
            # New user registration
            print(f"🆕 New user registration for: {mobile_number}")
            
            # ✅ Smart auto-generation of full_name
            if not full_name:
                # Option 1: Simple format
                # full_name = f"User {mobile_number}"
                
                # Option 2: More friendly format with last 4 digits
                # full_name = f"User {mobile_number[-4:]}"
                
                # Option 3: Professional format
                full_name = f"Mobile User {mobile_number[-4:]}"
                
                # Option 4: Keep it minimal
                # full_name = mobile_number
                
                print(f"   📝 Auto-generated full_name: {full_name}")
            else:
                print(f"   📝 User provided full_name: {full_name}")
            
            username = f"user_{mobile_number}"
            
            # Create or get user
            try:
                user = User.objects.get(username=username)
                print(f"   Found existing User object: {username}")
            except User.DoesNotExist:
                user = User.objects.create_user(
                    username=username,
                    first_name=full_name  # Also set Django's first_name field
                )
                print(f"   ✅ Created new User object: {username}")
            
            # Create or update profile
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
                print(f"   ✅ Updated existing profile")
            else:
                print(f"   ✅ Created new profile")
            
            is_new_user = True
            print(f"✅ New user registered: {full_name} ({mobile_number})")
        
        # Generate or get auth token
        token, created = Token.objects.get_or_create(user=user)
        
        response_data = {
            'success': True,
            'token': token.key,
            'is_new_user': is_new_user,
            'message': 'Login successful' if not is_new_user else 'Registration successful',
            'user': {
                'id': user.id,
                'username': user.username,
                'full_name': profile.full_name,
                'mobile_number': mobile_number,
                'role': profile.role,
                'is_mobile_verified': profile.is_mobile_verified
            }
        }
        
        print(f"✅ Login successful for {mobile_number}")
        print("="*80)
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        import traceback
        print("❌ ERROR IN MOBILE LOGIN:")
        traceback.print_exc()
        
        return Response(
            {
                'success': False,
                'error': 'An error occurred during login',
                'details': str(e)
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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