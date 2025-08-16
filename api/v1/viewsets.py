from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import hashlib
import secrets

from core.models import StaffToken
from core.serializers import StaffTokenSerializer
from core.permissions import IsAdminUser


class StaffTokenViewSet(viewsets.ModelViewSet):
    """ViewSet for managing staff tokens."""
    
    queryset = StaffToken.objects.all()
    serializer_class = StaffTokenSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        """Filter tokens based on query parameters."""
        queryset = self.queryset
        
        # Filter by active status
        active = self.request.query_params.get('active')
        if active is not None:
            queryset = queryset.filter(active=active.lower() == 'true')
        
        # Filter by expiry status
        expired = self.request.query_params.get('expired')
        if expired is not None:
            now = timezone.now()
            if expired.lower() == 'true':
                queryset = queryset.filter(expires_at__lt=now)
            else:
                queryset = queryset.filter(
                    models.Q(expires_at__gte=now) | models.Q(expires_at__isnull=True)
                )
        
        return queryset.order_by('-created_at')
    
    def create(self, request):
        """Create a new staff token."""
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        # Generate raw token and hash
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Create token
        staff_token = serializer.save(token_hash=token_hash)
        
        # Return token data with raw token (only shown once)
        response_data = self.get_serializer(staff_token).data
        response_data['raw_token'] = raw_token
        response_data['scanner_url'] = request.build_absolute_uri(
            f'/scanner/?token={raw_token}'
        )
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def revoke(self, request, pk=None):
        """Revoke a staff token."""
        staff_token = self.get_object()
        staff_token.active = False
        staff_token.save()
        
        return Response({
            'status': 'revoked',
            'message': f'Token {staff_token.label} has been revoked'
        })
    
    @action(detail=True, methods=['post'])
    def reactivate(self, request, pk=None):
        """Reactivate a staff token."""
        staff_token = self.get_object()
        
        # Check if token is expired
        if staff_token.expires_at and staff_token.expires_at < timezone.now():
            return Response({
                'error': 'Cannot reactivate expired token'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        staff_token.active = True
        staff_token.save()
        
        return Response({
            'status': 'reactivated',
            'message': f'Token {staff_token.label} has been reactivated'
        })
    
    @action(detail=False, methods=['get'])
    def active_count(self, request):
        """Get count of active tokens."""
        active_count = StaffToken.objects.filter(active=True).count()
        total_count = StaffToken.objects.count()
        
        return Response({
            'active_tokens': active_count,
            'total_tokens': total_count,
            'inactive_tokens': total_count - active_count
        })
    
    @action(detail=False, methods=['post'])
    def bulk_revoke(self, request):
        """Bulk revoke multiple tokens."""
        token_ids = request.data.get('token_ids', [])
        
        if not token_ids:
            return Response({
                'error': 'No token IDs provided'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Revoke tokens
        updated_count = StaffToken.objects.filter(
            id__in=token_ids,
            active=True
        ).update(active=False)
        
        return Response({
            'status': 'success',
            'revoked_count': updated_count,
            'message': f'Revoked {updated_count} tokens'
        })
    
    @action(detail=False, methods=['delete'])
    def cleanup_expired(self, request):
        """Clean up expired tokens."""
        from datetime import timedelta
        
        # Delete tokens expired for more than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        deleted_count, _ = StaffToken.objects.filter(
            expires_at__lt=cutoff_date
        ).delete()
        
        return Response({
            'status': 'success',
            'deleted_count': deleted_count,
            'message': f'Cleaned up {deleted_count} expired tokens'
        })