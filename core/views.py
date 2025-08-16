from rest_framework import viewsets, status
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
import logging

from .models import Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken, AuditLog
from .serializers import (
    StudentSerializer, PaymentSerializer, MessCutSerializer, MessClosureSerializer,
    ScanEventSerializer, QRScanRequestSerializer, QRScanResponseSerializer,
    StudentSnapshotSerializer, RegistrationRequestSerializer, PaymentUploadSerializer,
    ReportFilterSerializer
)
from .services import QRService, MessService, NotificationService, SheetsService
from .authentication import StaffTokenAuthentication
from .permissions import IsAdminUser, IsStaffUser

logger = logging.getLogger(__name__)


class StudentViewSet(viewsets.ModelViewSet):
    """ViewSet for Student CRUD operations."""
    
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_permissions(self):
        """Set permissions based on action."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAdminUser]
        else:
            permission_classes = [IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Approve a student registration."""
        student = self.get_object()
        if student.status != Student.Status.PENDING:
            return Response(
                {'error': 'Student is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        student.status = Student.Status.APPROVED
        student.save()
        
        # Generate QR code
        QRService.generate_qr_for_student(student)
        
        # Send notification
        NotificationService.send_approval_notification(student)
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(request.user.id),
            event_type='STUDENT_APPROVED',
            payload={'student_id': str(student.id), 'roll_no': student.roll_no}
        )
        
        return Response({'status': 'approved'})
    
    @action(detail=True, methods=['post'])
    def deny(self, request, pk=None):
        """Deny a student registration."""
        student = self.get_object()
        if student.status != Student.Status.PENDING:
            return Response(
                {'error': 'Student is not in pending status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        student.status = Student.Status.DENIED
        student.save()
        
        # Send notification
        NotificationService.send_denial_notification(student)
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(request.user.id),
            event_type='STUDENT_DENIED',
            payload={'student_id': str(student.id), 'roll_no': student.roll_no}
        )
        
        return Response({'status': 'denied'})


class PaymentViewSet(viewsets.ModelViewSet):
    """ViewSet for Payment CRUD operations."""
    
    queryset = Payment.objects.all().select_related('student')
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter payments based on user permissions."""
        queryset = self.queryset
        
        # Filter by status if provided
        status_filter = self.request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        # Filter by date range if provided
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        if from_date:
            queryset = queryset.filter(cycle_start__gte=from_date)
        if to_date:
            queryset = queryset.filter(cycle_end__lte=to_date)
        
        return queryset.order_by('-created_at')
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """Verify a payment."""
        payment = self.get_object()
        if payment.status != Payment.Status.UPLOADED:
            return Response(
                {'error': 'Payment is not in uploaded status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.status = Payment.Status.VERIFIED
        payment.reviewer_admin_id = request.user.id
        payment.reviewed_at = timezone.now()
        payment.save()
        
        # Send notification
        NotificationService.send_payment_verified_notification(payment)
        
        # Log to sheets
        SheetsService.log_payment_event(payment, 'VERIFIED')
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(request.user.id),
            event_type='PAYMENT_VERIFIED',
            payload={'payment_id': str(payment.id), 'student_id': str(payment.student.id)}
        )
        
        return Response({'status': 'verified'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def deny(self, request, pk=None):
        """Deny a payment."""
        payment = self.get_object()
        if payment.status != Payment.Status.UPLOADED:
            return Response(
                {'error': 'Payment is not in uploaded status'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        payment.status = Payment.Status.DENIED
        payment.reviewer_admin_id = request.user.id
        payment.reviewed_at = timezone.now()
        payment.save()
        
        # Send notification
        NotificationService.send_payment_denied_notification(payment)
        
        # Log to sheets
        SheetsService.log_payment_event(payment, 'DENIED')
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(request.user.id),
            event_type='PAYMENT_DENIED',
            payload={'payment_id': str(payment.id), 'student_id': str(payment.student.id)}
        )
        
        return Response({'status': 'denied'})
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def mark_manual_paid(self, request, pk=None):
        """Mark payment as manually paid."""
        payment = self.get_object()
        
        payment.status = Payment.Status.VERIFIED
        payment.source = Payment.Source.OFFLINE_MANUAL
        payment.reviewer_admin_id = request.user.id
        payment.reviewed_at = timezone.now()
        payment.save()
        
        # Send notification
        NotificationService.send_payment_verified_notification(payment)
        
        # Log to sheets
        SheetsService.log_payment_event(payment, 'MANUAL_PAID')
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(request.user.id),
            event_type='PAYMENT_MANUAL_PAID',
            payload={'payment_id': str(payment.id), 'student_id': str(payment.student.id)}
        )
        
        return Response({'status': 'marked_paid'})


class MessCutViewSet(viewsets.ModelViewSet):
    """ViewSet for MessCut operations."""
    
    queryset = MessCut.objects.all().select_related('student')
    serializer_class = MessCutSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter mess cuts based on query parameters."""
        queryset = self.queryset
        
        from_date = self.request.query_params.get('from_date')
        to_date = self.request.query_params.get('to_date')
        student_id = self.request.query_params.get('student_id')
        
        if from_date:
            queryset = queryset.filter(from_date__gte=from_date)
        if to_date:
            queryset = queryset.filter(to_date__lte=to_date)
        if student_id:
            queryset = queryset.filter(student_id=student_id)
        
        return queryset.order_by('-created_at')
    
    def perform_create(self, serializer):
        """Create mess cut with validation."""
        mess_cut = serializer.save()
        
        # Send notification
        NotificationService.send_mess_cut_confirmation(mess_cut)
        
        # Log to sheets
        SheetsService.log_mess_cut_event(mess_cut, 'CREATED')
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.STUDENT,
            actor_id=str(mess_cut.student.tg_user_id),
            event_type='MESS_CUT_APPLIED',
            payload={
                'mess_cut_id': str(mess_cut.id),
                'from_date': str(mess_cut.from_date),
                'to_date': str(mess_cut.to_date)
            }
        )


class MessClosureViewSet(viewsets.ModelViewSet):
    """ViewSet for MessClosure operations."""
    
    queryset = MessClosure.objects.all()
    serializer_class = MessClosureSerializer
    permission_classes = [IsAdminUser]
    
    def perform_create(self, serializer):
        """Create mess closure and broadcast notification."""
        closure = serializer.save(created_by_admin_id=self.request.user.id)
        
        # Broadcast notification to all students
        NotificationService.broadcast_mess_closure(closure)
        
        # Log to sheets
        SheetsService.log_mess_closure_event(closure, 'CREATED')
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(self.request.user.id),
            event_type='MESS_CLOSURE_CREATED',
            payload={
                'closure_id': str(closure.id),
                'from_date': str(closure.from_date),
                'to_date': str(closure.to_date),
                'reason': closure.reason
            }
        )


@api_view(['POST'])
@permission_classes([IsStaffUser])
def scan_qr(request):
    """Handle QR code scanning."""
    serializer = QRScanRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    qr_data = serializer.validated_data['qr_data']
    meal = serializer.validated_data['meal']
    device_info = serializer.validated_data.get('device_info', '')
    
    try:
        # Verify QR code
        student_id = QRService.verify_qr_code(qr_data)
        if not student_id:
            return Response({
                'result': ScanEvent.Result.BLOCKED_STATUS,
                'reason': 'Invalid QR code'
            })
        
        student = get_object_or_404(Student, id=student_id)
        
        # Check access permissions
        access_result = MessService.check_meal_access(student, meal)
        
        # Create scan event
        scan_event = ScanEvent.objects.create(
            student=student,
            meal=meal,
            staff_token=getattr(request, 'staff_token', None),
            result=access_result['result'],
            device_info=device_info
        )
        
        # Prepare response
        response_data = {
            'result': access_result['result'],
            'scan_id': scan_event.id
        }
        
        if access_result['result'] == ScanEvent.Result.ALLOWED:
            # Get student snapshot
            snapshot = MessService.get_student_snapshot(student)
            response_data['student_snapshot'] = StudentSnapshotSerializer(snapshot).data
            
            # Send notification to student
            NotificationService.send_scan_notification(student, meal)
            
        else:
            response_data['reason'] = access_result.get('reason', '')
        
        # Log to sheets
        SheetsService.log_scan_event(scan_event)
        
        return Response(response_data)
        
    except Exception as e:
        logger.error(f"QR scan error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_snapshot(request, student_id):
    """Get student snapshot for display."""
    try:
        student = get_object_or_404(Student, id=student_id)
        snapshot = MessService.get_student_snapshot(student)
        serializer = StudentSnapshotSerializer(snapshot)
        return Response(serializer.data)
    except Exception as e:
        logger.error(f"Student snapshot error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAdminUser])
def regenerate_qr_codes(request):
    """Regenerate all QR codes."""
    try:
        # Update QR secret version
        from .models import Settings
        settings = Settings.get_settings()
        settings.qr_secret_version += 1
        settings.save()
        
        # Update all approved students
        approved_students = Student.objects.filter(status=Student.Status.APPROVED)
        count = 0
        
        for student in approved_students:
            student.qr_version = settings.qr_secret_version
            student.save()
            
            # Generate and send new QR
            QRService.generate_qr_for_student(student)
            count += 1
        
        # Log audit
        AuditLog.objects.create(
            actor_type=AuditLog.ActorType.ADMIN,
            actor_id=str(request.user.id),
            event_type='QR_CODES_REGENERATED',
            payload={'affected_students': count, 'new_version': settings.qr_secret_version}
        )
        
        return Response({
            'status': 'success',
            'affected_students': count,
            'new_version': settings.qr_secret_version
        })
        
    except Exception as e:
        logger.error(f"QR regeneration error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def payment_reports(request):
    """Generate payment status reports."""
    serializer = ReportFilterSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    
    try:
        report_data = MessService.generate_payment_report(filters)
        return Response(report_data)
    except Exception as e:
        logger.error(f"Payment report error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAdminUser])
def mess_cut_reports(request):
    """Generate mess cut reports."""
    serializer = ReportFilterSerializer(data=request.query_params)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    filters = serializer.validated_data
    
    try:
        report_data = MessService.generate_mess_cut_report(filters)
        return Response(report_data)
    except Exception as e:
        logger.error(f"Mess cut report error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Telegram Bot Endpoints
@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request):
    """Handle Telegram webhook."""
    try:
        from .telegram_bot import bot_instance
        data = json.loads(request.body)
        bot_instance.process_update(data)
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        logger.error(f"Telegram webhook error: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@api_view(['POST'])
@permission_classes([AllowAny])
def register_student(request):
    """Register new student from Telegram."""
    serializer = RegistrationRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Check if student already exists
        tg_user_id = serializer.validated_data['tg_user_id']
        if Student.objects.filter(tg_user_id=tg_user_id).exists():
            return Response(
                {'error': 'Student already registered'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create student
        student = Student.objects.create(**serializer.validated_data)
        
        # Notify admins
        NotificationService.notify_admins_new_registration(student)
        
        # Log to sheets
        SheetsService.log_registration_event(student, 'CREATED')
        
        return Response({
            'status': 'success',
            'student_id': student.id,
            'message': 'Registration submitted for approval'
        })
        
    except Exception as e:
        logger.error(f"Student registration error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([AllowAny])
def upload_payment(request):
    """Upload payment from Telegram."""
    serializer = PaymentUploadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        # Create payment
        payment = Payment.objects.create(
            status=Payment.Status.UPLOADED,
            **serializer.validated_data
        )
        
        # Notify admins
        NotificationService.notify_admins_payment_upload(payment)
        
        # Log to sheets
        SheetsService.log_payment_event(payment, 'UPLOADED')
        
        return Response({
            'status': 'success',
            'payment_id': payment.id,
            'message': 'Payment uploaded for verification'
        })
        
    except Exception as e:
        logger.error(f"Payment upload error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )