from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import uuid


class TimestampedModel(models.Model):
    """Abstract base model with created_at and updated_at fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True


class Student(TimestampedModel):
    """Student model for mess management."""
    
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        APPROVED = 'APPROVED', 'Approved'
        DENIED = 'DENIED', 'Denied'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tg_user_id = models.BigIntegerField(unique=True, help_text="Telegram user ID")
    name = models.CharField(max_length=100)
    roll_no = models.CharField(
        max_length=20, 
        unique=True,
        validators=[RegexValidator(r'^[A-Z0-9]+$', 'Roll number must contain only uppercase letters and numbers')]
    )
    room_no = models.CharField(max_length=20)
    phone = models.CharField(
        max_length=15,
        validators=[RegexValidator(r'^\+?[1-9]\d{1,14}$', 'Enter a valid phone number')]
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    qr_version = models.IntegerField(default=1)
    qr_nonce = models.CharField(max_length=50, blank=True)
    
    class Meta:
        db_table = 'students'
        indexes = [
            models.Index(fields=['tg_user_id']),
            models.Index(fields=['roll_no']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.roll_no})"
    
    def save(self, *args, **kwargs):
        if not self.qr_nonce:
            self.qr_nonce = uuid.uuid4().hex[:12]
        super().save(*args, **kwargs)


class Payment(TimestampedModel):
    """Payment model for tracking mess payments."""
    
    class Status(models.TextChoices):
        NONE = 'NONE', 'None'
        UPLOADED = 'UPLOADED', 'Uploaded'
        VERIFIED = 'VERIFIED', 'Verified'
        DENIED = 'DENIED', 'Denied'
    
    class Source(models.TextChoices):
        ONLINE_SCREENSHOT = 'ONLINE_SCREENSHOT', 'Online Screenshot'
        OFFLINE_MANUAL = 'OFFLINE_MANUAL', 'Offline Manual'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments')
    cycle_start = models.DateField()
    cycle_end = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    screenshot_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.NONE)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.ONLINE_SCREENSHOT)
    reviewer_admin_id = models.BigIntegerField(blank=True, null=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        db_table = 'payments'
        indexes = [
            models.Index(fields=['student', 'cycle_start', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['cycle_start', 'cycle_end']),
        ]
        unique_together = ['student', 'cycle_start']
    
    def __str__(self):
        return f"{self.student.name} - {self.cycle_start} to {self.cycle_end}"
    
    @property
    def is_valid_for_date(self):
        """Check if payment is valid for today."""
        today = timezone.now().date()
        return (
            self.status == self.Status.VERIFIED and
            self.cycle_start <= today <= self.cycle_end
        )


class MessCut(TimestampedModel):
    """Mess cut model for tracking student mess cuts."""
    
    class AppliedBy(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        ADMIN_SYSTEM = 'ADMIN_SYSTEM', 'Admin System'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='mess_cuts')
    from_date = models.DateField()
    to_date = models.DateField()
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.CharField(max_length=15, choices=AppliedBy.choices, default=AppliedBy.STUDENT)
    cutoff_ok = models.BooleanField(default=True, help_text="Whether cutoff rule was respected")
    
    class Meta:
        db_table = 'mess_cuts'
        indexes = [
            models.Index(fields=['student', 'from_date', 'to_date']),
            models.Index(fields=['from_date', 'to_date']),
        ]
    
    def __str__(self):
        return f"{self.student.name} - {self.from_date} to {self.to_date}"
    
    def is_active_for_date(self, date):
        """Check if mess cut is active for given date."""
        return self.from_date <= date <= self.to_date


class MessClosure(TimestampedModel):
    """Mess closure model for tracking mess holidays."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField(blank=True)
    created_by_admin_id = models.BigIntegerField()
    
    class Meta:
        db_table = 'mess_closures'
        indexes = [
            models.Index(fields=['from_date', 'to_date']),
        ]
    
    def __str__(self):
        return f"Closure: {self.from_date} to {self.to_date}"
    
    def is_active_for_date(self, date):
        """Check if mess closure is active for given date."""
        return self.from_date <= date <= self.to_date


class ScanEvent(TimestampedModel):
    """Scan event model for tracking QR scans."""
    
    class Meal(models.TextChoices):
        BREAKFAST = 'BREAKFAST', 'Breakfast'
        LUNCH = 'LUNCH', 'Lunch'
        DINNER = 'DINNER', 'Dinner'
    
    class Result(models.TextChoices):
        ALLOWED = 'ALLOWED', 'Allowed'
        BLOCKED_NO_PAYMENT = 'BLOCKED_NO_PAYMENT', 'Blocked - No Payment'
        BLOCKED_CUT = 'BLOCKED_CUT', 'Blocked - Mess Cut'
        BLOCKED_STATUS = 'BLOCKED_STATUS', 'Blocked - Status Issue'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scan_events')
    meal = models.CharField(max_length=10, choices=Meal.choices)
    scanned_at = models.DateTimeField(auto_now_add=True)
    staff_token = models.ForeignKey('StaffToken', on_delete=models.SET_NULL, null=True, blank=True)
    result = models.CharField(max_length=20, choices=Result.choices)
    device_info = models.TextField(blank=True)
    
    class Meta:
        db_table = 'scan_events'
        indexes = [
            models.Index(fields=['student', 'scanned_at']),
            models.Index(fields=['scanned_at']),
            models.Index(fields=['meal', 'scanned_at']),
        ]
    
    def __str__(self):
        return f"{self.student.name} - {self.meal} - {self.result}"


class StaffToken(TimestampedModel):
    """Staff token model for QR scanner access."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    label = models.CharField(max_length=100)
    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)
    token_hash = models.CharField(max_length=255, unique=True)
    
    class Meta:
        db_table = 'staff_tokens'
        indexes = [
            models.Index(fields=['token_hash']),
            models.Index(fields=['active']),
        ]
    
    def __str__(self):
        return f"Token: {self.label}"
    
    @property
    def is_valid(self):
        """Check if token is valid."""
        if not self.active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        return True


class AuditLog(models.Model):
    """Audit log model for tracking system events."""
    
    class ActorType(models.TextChoices):
        STUDENT = 'STUDENT', 'Student'
        ADMIN = 'ADMIN', 'Admin'
        STAFF = 'STAFF', 'Staff'
        SYSTEM = 'SYSTEM', 'System'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor_type = models.CharField(max_length=10, choices=ActorType.choices)
    actor_id = models.CharField(max_length=100, blank=True, null=True)
    event_type = models.CharField(max_length=50)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'audit_logs'
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['actor_type', 'actor_id']),
            models.Index(fields=['event_type']),
        ]
    
    def __str__(self):
        return f"{self.event_type} by {self.actor_type} at {self.created_at}"


class Settings(models.Model):
    """Settings model for system configuration (singleton)."""
    
    id = models.AutoField(primary_key=True)
    tz = models.CharField(max_length=50, default='Asia/Kolkata')
    cutoff_time = models.TimeField(default='23:00')
    qr_secret_version = models.IntegerField(default=1)
    qr_secret_hash = models.CharField(max_length=255)
    meals = models.JSONField(default=dict)
    
    class Meta:
        db_table = 'settings'
        verbose_name_plural = 'Settings'
    
    def save(self, *args, **kwargs):
        # Ensure only one instance exists
        self.pk = 1
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create settings instance."""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
    def __str__(self):
        return "System Settings"


class DLQLog(TimestampedModel):
    """Dead Letter Queue for failed Google Sheets operations."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation = models.CharField(max_length=50)
    payload = models.JSONField()
    error_message = models.TextField()
    retry_count = models.IntegerField(default=0)
    processed = models.BooleanField(default=False)
    
    class Meta:
        db_table = 'dlq_logs'
        indexes = [
            models.Index(fields=['processed', 'created_at']),
            models.Index(fields=['operation']),
        ]
    
    def __str__(self):
        return f"DLQ: {self.operation} - Retry {self.retry_count}"