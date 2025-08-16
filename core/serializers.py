from rest_framework import serializers
from django.utils import timezone
from .models import Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken
import re


class StudentSerializer(serializers.ModelSerializer):
    """Serializer for Student model."""
    
    class Meta:
        model = Student
        fields = ['id', 'name', 'roll_no', 'room_no', 'phone', 'status', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate_roll_no(self, value):
        """Validate roll number format."""
        if not re.match(r'^[A-Z0-9]+$', value):
            raise serializers.ValidationError("Roll number must contain only uppercase letters and numbers")
        return value
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if not re.match(r'^\+?[1-9]\d{1,14}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value


class PaymentSerializer(serializers.ModelSerializer):
    """Serializer for Payment model."""
    
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_roll = serializers.CharField(source='student.roll_no', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'student', 'student_name', 'student_roll',
            'cycle_start', 'cycle_end', 'amount', 'screenshot_url',
            'status', 'source', 'reviewed_at', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'reviewed_at']
    
    def validate(self, data):
        """Validate payment data."""
        if data['cycle_start'] >= data['cycle_end']:
            raise serializers.ValidationError("Cycle start date must be before end date")
        
        if data['amount'] <= 0:
            raise serializers.ValidationError("Amount must be positive")
        
        return data


class MessCutSerializer(serializers.ModelSerializer):
    """Serializer for MessCut model."""
    
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_roll = serializers.CharField(source='student.roll_no', read_only=True)
    
    class Meta:
        model = MessCut
        fields = [
            'id', 'student', 'student_name', 'student_roll',
            'from_date', 'to_date', 'applied_at', 'applied_by', 'cutoff_ok'
        ]
        read_only_fields = ['id', 'applied_at', 'cutoff_ok']
    
    def validate(self, data):
        """Validate mess cut data."""
        if data['from_date'] > data['to_date']:
            raise serializers.ValidationError("From date must be before or equal to end date")
        
        # Check cutoff rule (can only cut for tomorrow and later)
        today = timezone.now().date()
        tomorrow = today + timezone.timedelta(days=1)
        
        if data['from_date'] < tomorrow:
            raise serializers.ValidationError("Cannot apply mess cut for today or past dates")
        
        return data


class MessClosureSerializer(serializers.ModelSerializer):
    """Serializer for MessClosure model."""
    
    class Meta:
        model = MessClosure
        fields = ['id', 'from_date', 'to_date', 'reason', 'created_at']
        read_only_fields = ['id', 'created_at']
    
    def validate(self, data):
        """Validate mess closure data."""
        if data['from_date'] > data['to_date']:
            raise serializers.ValidationError("From date must be before or equal to end date")
        
        return data


class ScanEventSerializer(serializers.ModelSerializer):
    """Serializer for ScanEvent model."""
    
    student_name = serializers.CharField(source='student.name', read_only=True)
    student_roll = serializers.CharField(source='student.roll_no', read_only=True)
    
    class Meta:
        model = ScanEvent
        fields = [
            'id', 'student', 'student_name', 'student_roll',
            'meal', 'scanned_at', 'result', 'device_info'
        ]
        read_only_fields = ['id', 'scanned_at']


class StaffTokenSerializer(serializers.ModelSerializer):
    """Serializer for StaffToken model."""
    
    class Meta:
        model = StaffToken
        fields = ['id', 'label', 'issued_at', 'expires_at', 'active']
        read_only_fields = ['id', 'issued_at', 'token_hash']


class QRScanRequestSerializer(serializers.Serializer):
    """Serializer for QR scan requests."""
    
    qr_data = serializers.CharField(required=True)
    meal = serializers.ChoiceField(choices=ScanEvent.Meal.choices, required=True)
    device_info = serializers.CharField(required=False, allow_blank=True)
    
    def validate_qr_data(self, value):
        """Validate QR data format."""
        if not value or len(value.strip()) == 0:
            raise serializers.ValidationError("QR data cannot be empty")
        return value.strip()


class StudentSnapshotSerializer(serializers.Serializer):
    """Serializer for student snapshot data."""
    
    id = serializers.UUIDField()
    name = serializers.CharField()
    roll_no = serializers.CharField()
    room_no = serializers.CharField()
    status = serializers.CharField()
    payment_ok = serializers.BooleanField()
    today_cut = serializers.BooleanField()
    closure_today = serializers.BooleanField()
    overall_status = serializers.CharField()


class QRScanResponseSerializer(serializers.Serializer):
    """Serializer for QR scan responses."""
    
    result = serializers.ChoiceField(choices=ScanEvent.Result.choices)
    student_snapshot = StudentSnapshotSerializer(required=False, allow_null=True)
    reason = serializers.CharField(required=False, allow_blank=True)
    scan_id = serializers.UUIDField(required=False, allow_null=True)


class RegistrationRequestSerializer(serializers.Serializer):
    """Serializer for registration requests from Telegram."""
    
    tg_user_id = serializers.IntegerField()
    name = serializers.CharField(max_length=100)
    roll_no = serializers.CharField(max_length=20)
    room_no = serializers.CharField(max_length=20)
    phone = serializers.CharField(max_length=15)
    
    def validate_roll_no(self, value):
        """Validate roll number format."""
        if not re.match(r'^[A-Z0-9]+$', value.upper()):
            raise serializers.ValidationError("Roll number must contain only letters and numbers")
        return value.upper()
    
    def validate_phone(self, value):
        """Validate phone number format."""
        if not re.match(r'^\+?[1-9]\d{1,14}$', value):
            raise serializers.ValidationError("Enter a valid phone number")
        return value


class PaymentUploadSerializer(serializers.Serializer):
    """Serializer for payment upload from Telegram."""
    
    student_id = serializers.UUIDField()
    cycle_start = serializers.DateField()
    cycle_end = serializers.DateField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    screenshot_url = serializers.URLField()
    
    def validate(self, data):
        """Validate payment upload data."""
        if data['cycle_start'] >= data['cycle_end']:
            raise serializers.ValidationError("Cycle start date must be before end date")
        
        if data['amount'] <= 0:
            raise serializers.ValidationError("Amount must be positive")
        
        return data


class ReportFilterSerializer(serializers.Serializer):
    """Serializer for report filters."""
    
    status = serializers.ChoiceField(
        choices=[
            ('verified', 'Verified'),
            ('uploaded', 'Uploaded (Pending)'),
            ('not_uploaded', 'Not Uploaded'),
            ('denied', 'Denied'),
        ],
        required=False
    )
    from_date = serializers.DateField(required=False)
    to_date = serializers.DateField(required=False)
    student_id = serializers.UUIDField(required=False)
    
    def validate(self, data):
        """Validate report filter data."""
        if 'from_date' in data and 'to_date' in data:
            if data['from_date'] > data['to_date']:
                raise serializers.ValidationError("From date must be before or equal to end date")
        
        return data