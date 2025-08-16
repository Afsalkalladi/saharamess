import django_filters
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from core.models import Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken, AuditLog


class StudentFilter(django_filters.FilterSet):
    """Filter for Student model."""
    
    name = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by student name")
    roll_no = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by roll number")
    room_no = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by room number")
    phone = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by phone number")
    status = django_filters.ChoiceFilter(choices=Student.Status.choices, help_text="Filter by status")
    
    # Date filters
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', help_text="Created after date")
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', help_text="Created before date")
    created_today = django_filters.BooleanFilter(method='filter_created_today', help_text="Created today")
    
    # Custom filters
    has_payments = django_filters.BooleanFilter(method='filter_has_payments', help_text="Has payments")
    has_valid_payment = django_filters.BooleanFilter(method='filter_has_valid_payment', help_text="Has valid payment")
    
    class Meta:
        model = Student
        fields = ['name', 'roll_no', 'room_no', 'phone', 'status']
    
    def filter_created_today(self, queryset, name, value):
        """Filter students created today."""
        if value:
            today = timezone.now().date()
            return queryset.filter(created_at__date=today)
        return queryset
    
    def filter_has_payments(self, queryset, name, value):
        """Filter students with/without payments."""
        if value is not None:
            if value:
                return queryset.filter(payments__isnull=False).distinct()
            else:
                return queryset.filter(payments__isnull=True)
        return queryset
    
    def filter_has_valid_payment(self, queryset, name, value):
        """Filter students with valid payments."""
        if value is not None:
            today = timezone.now().date()
            if value:
                return queryset.filter(
                    payments__status=Payment.Status.VERIFIED,
                    payments__cycle_start__lte=today,
                    payments__cycle_end__gte=today
                ).distinct()
            else:
                return queryset.exclude(
                    payments__status=Payment.Status.VERIFIED,
                    payments__cycle_start__lte=today,
                    payments__cycle_end__gte=today
                ).distinct()
        return queryset


class PaymentFilter(django_filters.FilterSet):
    """Filter for Payment model."""
    
    student_name = django_filters.CharFilter(field_name='student__name', lookup_expr='icontains', help_text="Filter by student name")
    student_roll = django_filters.CharFilter(field_name='student__roll_no', lookup_expr='icontains', help_text="Filter by student roll number")
    status = django_filters.ChoiceFilter(choices=Payment.Status.choices, help_text="Filter by payment status")
    source = django_filters.ChoiceFilter(choices=Payment.Source.choices, help_text="Filter by payment source")
    
    # Amount filters
    amount_min = django_filters.NumberFilter(field_name='amount', lookup_expr='gte', help_text="Minimum amount")
    amount_max = django_filters.NumberFilter(field_name='amount', lookup_expr='lte', help_text="Maximum amount")
    
    # Date filters
    cycle_start_after = django_filters.DateFilter(field_name='cycle_start', lookup_expr='gte', help_text="Cycle starts after")
    cycle_start_before = django_filters.DateFilter(field_name='cycle_start', lookup_expr='lte', help_text="Cycle starts before")
    cycle_end_after = django_filters.DateFilter(field_name='cycle_end', lookup_expr='gte', help_text="Cycle ends after")
    cycle_end_before = django_filters.DateFilter(field_name='cycle_end', lookup_expr='lte', help_text="Cycle ends before")
    
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', help_text="Created after")
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', help_text="Created before")
    
    # Custom filters
    valid_for_date = django_filters.DateFilter(method='filter_valid_for_date', help_text="Valid for specific date")
    expiring_soon = django_filters.BooleanFilter(method='filter_expiring_soon', help_text="Expiring within 7 days")
    pending_review = django_filters.BooleanFilter(method='filter_pending_review', help_text="Pending admin review")
    
    class Meta:
        model = Payment
        fields = ['status', 'source']
    
    def filter_valid_for_date(self, queryset, name, value):
        """Filter payments valid for a specific date."""
        if value:
            return queryset.filter(
                status=Payment.Status.VERIFIED,
                cycle_start__lte=value,
                cycle_end__gte=value
            )
        return queryset
    
    def filter_expiring_soon(self, queryset, name, value):
        """Filter payments expiring within 7 days."""
        if value:
            seven_days = timezone.now().date() + timedelta(days=7)
            return queryset.filter(
                status=Payment.Status.VERIFIED,
                cycle_end__lte=seven_days,
                cycle_end__gte=timezone.now().date()
            )
        return queryset
    
    def filter_pending_review(self, queryset, name, value):
        """Filter payments pending review."""
        if value:
            return queryset.filter(status=Payment.Status.UPLOADED)
        return queryset


class MessCutFilter(django_filters.FilterSet):
    """Filter for MessCut model."""
    
    student_name = django_filters.CharFilter(field_name='student__name', lookup_expr='icontains', help_text="Filter by student name")
    student_roll = django_filters.CharFilter(field_name='student__roll_no', lookup_expr='icontains', help_text="Filter by student roll number")
    applied_by = django_filters.ChoiceFilter(choices=MessCut.AppliedBy.choices, help_text="Filter by who applied")
    
    # Date filters
    from_date_after = django_filters.DateFilter(field_name='from_date', lookup_expr='gte', help_text="From date after")
    from_date_before = django_filters.DateFilter(field_name='from_date', lookup_expr='lte', help_text="From date before")
    to_date_after = django_filters.DateFilter(field_name='to_date', lookup_expr='gte', help_text="To date after")
    to_date_before = django_filters.DateFilter(field_name='to_date', lookup_expr='lte', help_text="To date before")
    
    applied_after = django_filters.DateTimeFilter(field_name='applied_at', lookup_expr='gte', help_text="Applied after")
    applied_before = django_filters.DateTimeFilter(field_name='applied_at', lookup_expr='lte', help_text="Applied before")
    
    # Custom filters
    active_for_date = django_filters.DateFilter(method='filter_active_for_date', help_text="Active for specific date")
    upcoming = django_filters.BooleanFilter(method='filter_upcoming', help_text="Upcoming mess cuts")
    current = django_filters.BooleanFilter(method='filter_current', help_text="Currently active mess cuts")
    
    class Meta:
        model = MessCut
        fields = ['applied_by']
    
    def filter_active_for_date(self, queryset, name, value):
        """Filter mess cuts active for a specific date."""
        if value:
            return queryset.filter(
                from_date__lte=value,
                to_date__gte=value
            )
        return queryset
    
    def filter_upcoming(self, queryset, name, value):
        """Filter upcoming mess cuts."""
        if value:
            today = timezone.now().date()
            return queryset.filter(from_date__gt=today)
        return queryset
    
    def filter_current(self, queryset, name, value):
        """Filter currently active mess cuts."""
        if value:
            today = timezone.now().date()
            return queryset.filter(
                from_date__lte=today,
                to_date__gte=today
            )
        return queryset


class MessClosureFilter(django_filters.FilterSet):
    """Filter for MessClosure model."""
    
    reason = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by reason")
    created_by_admin_id = django_filters.NumberFilter(help_text="Filter by admin who created")
    
    # Date filters
    from_date_after = django_filters.DateFilter(field_name='from_date', lookup_expr='gte', help_text="From date after")
    from_date_before = django_filters.DateFilter(field_name='from_date', lookup_expr='lte', help_text="From date before")
    to_date_after = django_filters.DateFilter(field_name='to_date', lookup_expr='gte', help_text="To date after")
    to_date_before = django_filters.DateFilter(field_name='to_date', lookup_expr='lte', help_text="To date before")
    
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', help_text="Created after")
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', help_text="Created before")
    
    # Custom filters
    active_for_date = django_filters.DateFilter(method='filter_active_for_date', help_text="Active for specific date")
    upcoming = django_filters.BooleanFilter(method='filter_upcoming', help_text="Upcoming closures")
    current = django_filters.BooleanFilter(method='filter_current', help_text="Currently active closures")
    
    class Meta:
        model = MessClosure
        fields = ['reason', 'created_by_admin_id']
    
    def filter_active_for_date(self, queryset, name, value):
        """Filter closures active for a specific date."""
        if value:
            return queryset.filter(
                from_date__lte=value,
                to_date__gte=value
            )
        return queryset
    
    def filter_upcoming(self, queryset, name, value):
        """Filter upcoming closures."""
        if value:
            today = timezone.now().date()
            return queryset.filter(from_date__gt=today)
        return queryset
    
    def filter_current(self, queryset, name, value):
        """Filter currently active closures."""
        if value:
            today = timezone.now().date()
            return queryset.filter(
                from_date__lte=today,
                to_date__gte=today
            )
        return queryset


class ScanEventFilter(django_filters.FilterSet):
    """Filter for ScanEvent model."""
    
    student_name = django_filters.CharFilter(field_name='student__name', lookup_expr='icontains', help_text="Filter by student name")
    student_roll = django_filters.CharFilter(field_name='student__roll_no', lookup_expr='icontains', help_text="Filter by student roll number")
    meal = django_filters.ChoiceFilter(choices=ScanEvent.Meal.choices, help_text="Filter by meal type")
    result = django_filters.ChoiceFilter(choices=ScanEvent.Result.choices, help_text="Filter by scan result")
    
    # Date filters
    scanned_after = django_filters.DateTimeFilter(field_name='scanned_at', lookup_expr='gte', help_text="Scanned after")
    scanned_before = django_filters.DateTimeFilter(field_name='scanned_at', lookup_expr='lte', help_text="Scanned before")
    scanned_today = django_filters.BooleanFilter(method='filter_scanned_today', help_text="Scanned today")
    
    # Staff token filter
    staff_token_label = django_filters.CharFilter(field_name='staff_token__label', lookup_expr='icontains', help_text="Filter by scanner label")
    
    # Custom filters
    successful_only = django_filters.BooleanFilter(method='filter_successful_only', help_text="Only successful scans")
    failed_only = django_filters.BooleanFilter(method='filter_failed_only', help_text="Only failed scans")
    
    class Meta:
        model = ScanEvent
        fields = ['meal', 'result']
    
    def filter_scanned_today(self, queryset, name, value):
        """Filter scans from today."""
        if value:
            today = timezone.now().date()
            return queryset.filter(scanned_at__date=today)
        return queryset
    
    def filter_successful_only(self, queryset, name, value):
        """Filter only successful scans."""
        if value:
            return queryset.filter(result=ScanEvent.Result.ALLOWED)
        return queryset
    
    def filter_failed_only(self, queryset, name, value):
        """Filter only failed scans."""
        if value:
            return queryset.exclude(result=ScanEvent.Result.ALLOWED)
        return queryset


class StaffTokenFilter(django_filters.FilterSet):
    """Filter for StaffToken model."""
    
    label = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by token label")
    active = django_filters.BooleanFilter(help_text="Filter by active status")
    
    # Date filters
    issued_after = django_filters.DateTimeFilter(field_name='issued_at', lookup_expr='gte', help_text="Issued after")
    issued_before = django_filters.DateTimeFilter(field_name='issued_at', lookup_expr='lte', help_text="Issued before")
    expires_after = django_filters.DateTimeFilter(field_name='expires_at', lookup_expr='gte', help_text="Expires after")
    expires_before = django_filters.DateTimeFilter(field_name='expires_at', lookup_expr='lte', help_text="Expires before")
    
    # Custom filters
    expired = django_filters.BooleanFilter(method='filter_expired', help_text="Filter expired tokens")
    expiring_soon = django_filters.BooleanFilter(method='filter_expiring_soon', help_text="Expiring within 24 hours")
    never_expires = django_filters.BooleanFilter(method='filter_never_expires', help_text="Tokens that never expire")
    
    class Meta:
        model = StaffToken
        fields = ['label', 'active']
    
    def filter_expired(self, queryset, name, value):
        """Filter expired tokens."""
        if value is not None:
            now = timezone.now()
            if value:
                return queryset.filter(expires_at__lt=now, active=True)
            else:
                return queryset.filter(
                    Q(expires_at__gte=now) | Q(expires_at__isnull=True)
                )
        return queryset
    
    def filter_expiring_soon(self, queryset, name, value):
        """Filter tokens expiring within 24 hours."""
        if value:
            now = timezone.now()
            tomorrow = now + timedelta(hours=24)
            return queryset.filter(
                expires_at__gte=now,
                expires_at__lte=tomorrow,
                active=True
            )
        return queryset
    
    def filter_never_expires(self, queryset, name, value):
        """Filter tokens that never expire."""
        if value is not None:
            if value:
                return queryset.filter(expires_at__isnull=True)
            else:
                return queryset.filter(expires_at__isnull=False)
        return queryset


class AuditLogFilter(django_filters.FilterSet):
    """Filter for AuditLog model."""
    
    actor_type = django_filters.ChoiceFilter(choices=AuditLog.ActorType.choices, help_text="Filter by actor type")
    actor_id = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by actor ID")
    event_type = django_filters.CharFilter(lookup_expr='icontains', help_text="Filter by event type")
    
    # Date filters
    created_after = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='gte', help_text="Created after")
    created_before = django_filters.DateTimeFilter(field_name='created_at', lookup_expr='lte', help_text="Created before")
    created_today = django_filters.BooleanFilter(method='filter_created_today', help_text="Created today")
    
    # Custom filters
    critical_events = django_filters.BooleanFilter(method='filter_critical_events', help_text="Only critical events")
    student_events = django_filters.BooleanFilter(method='filter_student_events', help_text="Only student-related events")
    admin_events = django_filters.BooleanFilter(method='filter_admin_events', help_text="Only admin actions")
    
    class Meta:
        model = AuditLog
        fields = ['actor_type', 'event_type']
    
    def filter_created_today(self, queryset, name, value):
        """Filter logs created today."""
        if value:
            today = timezone.now().date()
            return queryset.filter(created_at__date=today)
        return queryset
    
    def filter_critical_events(self, queryset, name, value):
        """Filter critical events."""
        if value:
            critical_events = [
                'STUDENT_APPROVED', 'STUDENT_DENIED',
                'PAYMENT_VERIFIED', 'PAYMENT_DENIED',
                'QR_CODES_REGENERATED', 'STAFF_TOKEN_CREATED',
                'MESS_CLOSURE_CREATED'
            ]
            return queryset.filter(event_type__in=critical_events)
        return queryset
    
    def filter_student_events(self, queryset, name, value):
        """Filter student-related events."""
        if value:
            student_events = [
                'STUDENT_CREATED', 'STUDENT_APPROVED', 'STUDENT_DENIED',
                'PAYMENT_CREATED', 'PAYMENT_VERIFIED', 'PAYMENT_DENIED',
                'MESS_CUT_APPLIED', 'QR_SCANNED'
            ]
            return queryset.filter(event_type__in=student_events)
        return queryset
    
    def filter_admin_events(self, queryset, name, value):
        """Filter admin actions."""
        if value:
            return queryset.filter(actor_type=AuditLog.ActorType.ADMIN)
        return queryset


# Custom ordering filters
class OrderingFilter(django_filters.OrderingFilter):
    """Custom ordering filter with predefined choices."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add common ordering options
        common_choices = [
            ('created_at', 'Created (Oldest first)'),
            ('-created_at', 'Created (Newest first)'),
            ('updated_at', 'Updated (Oldest first)'),
            ('-updated_at', 'Updated (Newest first)'),
            ('name', 'Name (A-Z)'),
            ('-name', 'Name (Z-A)'),
        ]
        
        if hasattr(self, 'choices'):
            self.choices = list(self.choices) + common_choices
        else:
            self.choices = common_choices


# Search filters
class SearchFilter(django_filters.CharFilter):
    """Custom search filter for multiple fields."""
    
    def __init__(self, search_fields, *args, **kwargs):
        self.search_fields = search_fields
        super().__init__(*args, **kwargs)
    
    def filter(self, qs, value):
        """Apply search across multiple fields."""
        if not value:
            return qs
        
        q_objects = Q()
        for field in self.search_fields:
            q_objects |= Q(**{f"{field}__icontains": value})
        
        return qs.filter(q_objects)


# Date range filters
class DateRangeFilter(django_filters.FilterSet):
    """Base class for date range filtering."""
    
    date_range = django_filters.ChoiceFilter(
        method='filter_date_range',
        choices=[
            ('today', 'Today'),
            ('yesterday', 'Yesterday'),
            ('this_week', 'This Week'),
            ('last_week', 'Last Week'),
            ('this_month', 'This Month'),
            ('last_month', 'Last Month'),
        ],
        help_text="Predefined date ranges"
    )
    
    def filter_date_range(self, queryset, name, value):
        """Filter by predefined date ranges."""
        now = timezone.now()
        today = now.date()
        
        if value == 'today':
            return queryset.filter(created_at__date=today)
        elif value == 'yesterday':
            yesterday = today - timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif value == 'this_week':
            week_start = today - timedelta(days=today.weekday())
            return queryset.filter(created_at__date__gte=week_start)
        elif value == 'last_week':
            week_start = today - timedelta(days=today.weekday() + 7)
            week_end = week_start + timedelta(days=6)
            return queryset.filter(
                created_at__date__gte=week_start,
                created_at__date__lte=week_end
            )
        elif value == 'this_month':
            month_start = today.replace(day=1)
            return queryset.filter(created_at__date__gte=month_start)
        elif value == 'last_month':
            month_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1)
            month_end = today.replace(day=1) - timedelta(days=1)
            return queryset.filter(
                created_at__date__gte=month_start,
                created_at__date__lte=month_end
            )
        
        return queryset