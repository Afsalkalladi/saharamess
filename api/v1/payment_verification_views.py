"""
API Views for Manual Payment Verification System
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
import json
import logging
from core.payment_verification import payment_verification_manager
from core.models import Payment

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_payment_verification(request):
    """
    Submit payment receipt for manual verification
    
    POST /api/v1/payments/submit-verification/
    {
        "payment_id": 123,
        "amount": 1000.00,
        "payment_method": "UPI",
        "notes": "Paid via Google Pay",
        "receipt": <file>
    }
    """
    try:
        payment_id = request.data.get('payment_id')
        amount = float(request.data.get('amount', 0))
        payment_method = request.data.get('payment_method', '')
        notes = request.data.get('notes', '')
        receipt_file = request.FILES.get('receipt')
        
        if not all([payment_id, amount, payment_method, receipt_file]):
            return Response({
                'error': 'Missing required fields: payment_id, amount, payment_method, receipt'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file size
        if receipt_file.size > settings.MAX_RECEIPT_SIZE:
            return Response({
                'error': f'File size too large. Maximum {settings.MAX_RECEIPT_SIZE/1024/1024}MB allowed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Validate file format
        file_extension = receipt_file.name.split('.')[-1].lower()
        allowed_formats = settings.ALLOWED_RECEIPT_FORMATS.split(',')
        if file_extension not in allowed_formats:
            return Response({
                'error': f'Invalid file format. Allowed: {", ".join(allowed_formats)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Submit for verification
        result = payment_verification_manager.submit_payment_for_verification(
            payment_id=payment_id,
            receipt_file=receipt_file,
            student_id=request.user.id,  # Assuming user is student
            amount=amount,
            payment_method=payment_method,
            notes=notes
        )
        
        if result['status'] == 'success':
            return Response({
                'message': result['message'],
                'receipt_url': result['receipt_url'],
                'payment_id': payment_id,
                'status': 'pending_verification'
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'error': result['message']
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.error(f"Payment verification submission error: {e}")
        return Response({
            'error': 'Failed to submit payment for verification'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
def approve_payment_webhook(request, payment_id):
    """
    Webhook endpoint for approving payments (called from Google Sheets)
    
    POST /api/v1/payments/{payment_id}/approve/
    """
    try:
        # Verify webhook secret
        webhook_secret = request.headers.get('X-Webhook-Secret')
        if webhook_secret != settings.PAYMENT_VERIFICATION_WEBHOOK_SECRET:
            return JsonResponse({
                'error': 'Invalid webhook secret'
            }, status=403)
        
        # Parse request data
        data = json.loads(request.body) if request.body else {}
        admin_user_id = data.get('admin_user_id', 'sheet_admin')
        admin_comments = data.get('comments', 'Approved via Google Sheets')
        
        # Approve payment
        result = payment_verification_manager.approve_payment(
            payment_id=payment_id,
            admin_user_id=admin_user_id,
            admin_comments=admin_comments
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Payment approval webhook error: {e}")
        return JsonResponse({
            'error': 'Failed to approve payment'
        }, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def deny_payment_webhook(request, payment_id):
    """
    Webhook endpoint for denying payments (called from Google Sheets)
    
    POST /api/v1/payments/{payment_id}/deny/
    """
    try:
        # Verify webhook secret
        webhook_secret = request.headers.get('X-Webhook-Secret')
        if webhook_secret != settings.PAYMENT_VERIFICATION_WEBHOOK_SECRET:
            return JsonResponse({
                'error': 'Invalid webhook secret'
            }, status=403)
        
        # Parse request data
        data = json.loads(request.body) if request.body else {}
        admin_user_id = data.get('admin_user_id', 'sheet_admin')
        reason = data.get('reason', 'Denied via Google Sheets')
        
        # Deny payment
        result = payment_verification_manager.deny_payment(
            payment_id=payment_id,
            admin_user_id=admin_user_id,
            reason=reason
        )
        
        return JsonResponse(result)
        
    except Exception as e:
        logger.error(f"Payment denial webhook error: {e}")
        return JsonResponse({
            'error': 'Failed to deny payment'
        }, status=500)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pending_verifications(request):
    """
    Get list of pending payment verifications (admin only)
    
    GET /api/v1/payments/pending-verifications/
    """
    try:
        # Check if user is admin
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        pending = payment_verification_manager.get_pending_verifications()
        
        return Response({
            'pending_verifications': pending,
            'count': len(pending)
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Get pending verifications error: {e}")
        return Response({
            'error': 'Failed to get pending verifications'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_approve_payment(request, payment_id):
    """
    Admin endpoint to approve payment via API
    
    POST /api/v1/payments/{payment_id}/admin-approve/
    {
        "comments": "Payment verified manually"
    }
    """
    try:
        # Check if user is admin
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        comments = request.data.get('comments', '')
        
        result = payment_verification_manager.approve_payment(
            payment_id=payment_id,
            admin_user_id=str(request.user.id),
            admin_comments=comments
        )
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Admin approve payment error: {e}")
        return Response({
            'error': 'Failed to approve payment'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_deny_payment(request, payment_id):
    """
    Admin endpoint to deny payment via API
    
    POST /api/v1/payments/{payment_id}/admin-deny/
    {
        "reason": "Invalid receipt"
    }
    """
    try:
        # Check if user is admin
        if not request.user.is_staff:
            return Response({
                'error': 'Admin access required'
            }, status=status.HTTP_403_FORBIDDEN)
        
        reason = request.data.get('reason', 'Denied by admin')
        
        result = payment_verification_manager.deny_payment(
            payment_id=payment_id,
            admin_user_id=str(request.user.id),
            reason=reason
        )
        
        return Response(result)
        
    except Exception as e:
        logger.error(f"Admin deny payment error: {e}")
        return Response({
            'error': 'Failed to deny payment'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def payment_verification_status(request, payment_id):
    """
    Get payment verification status
    
    GET /api/v1/payments/{payment_id}/verification-status/
    """
    try:
        payment = Payment.objects.get(id=payment_id)
        
        return Response({
            'payment_id': payment_id,
            'status': payment.status,
            'submitted_at': payment.verification_submitted_at,
            'verified_at': payment.verified_at,
            'verified_by': payment.verified_by,
            'admin_comments': payment.admin_comments,
            'receipt_url': payment.receipt_url
        }, status=status.HTTP_200_OK)
        
    except Payment.DoesNotExist:
        return Response({
            'error': 'Payment not found'
        }, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Get payment status error: {e}")
        return Response({
            'error': 'Failed to get payment status'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
