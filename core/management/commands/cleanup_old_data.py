from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, timedelta
from django.db.models import Q

from core.models import ScanEvent, Payment, MessCut, StaffToken, AuditLog, DLQLog


class Command(BaseCommand):
    help = 'Clean up old data to maintain database performance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to keep data (default: 90)',
        )
        parser.add_argument(
            '--scan-events-days',
            type=int,
            default=30,
            help='Days to keep scan events (default: 30)',
        )
        parser.add_argument(
            '--audit-logs-days',
            type=int,
            default=180,
            help='Days to keep audit logs (default: 180)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompts',
        )

    def handle(self, *args, **options):
        """Clean up old data based on retention policies."""
        
        days = options['days']
        scan_events_days = options['scan_events_days']
        audit_logs_days = options['audit_logs_days']
        dry_run = options['dry_run']
        force = options['force']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        scan_events_cutoff = timezone.now() - timedelta(days=scan_events_days)
        audit_logs_cutoff = timezone.now() - timedelta(days=audit_logs_days)
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No data will be deleted'))
        
        # Clean up scan events (most frequent data)
        old_scan_events = ScanEvent.objects.filter(scanned_at__lt=scan_events_cutoff)
        scan_count = old_scan_events.count()
        
        if scan_count > 0:
            self.stdout.write(f"Found {scan_count} scan events older than {scan_events_days} days")
            if not dry_run and (force or self.confirm_deletion('scan events', scan_count)):
                deleted_count = old_scan_events.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} scan events'))
        
        # Clean up expired staff tokens
        expired_tokens = StaffToken.objects.filter(
            Q(expires_at__lt=timezone.now()) | Q(active=False)
        ).filter(issued_at__lt=cutoff_date)
        token_count = expired_tokens.count()
        
        if token_count > 0:
            self.stdout.write(f"Found {token_count} expired staff tokens")
            if not dry_run and (force or self.confirm_deletion('expired staff tokens', token_count)):
                deleted_count = expired_tokens.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} expired staff tokens'))
        
        # Clean up old audit logs
        old_audit_logs = AuditLog.objects.filter(created_at__lt=audit_logs_cutoff)
        audit_count = old_audit_logs.count()
        
        if audit_count > 0:
            self.stdout.write(f"Found {audit_count} audit logs older than {audit_logs_days} days")
            if not dry_run and (force or self.confirm_deletion('audit logs', audit_count)):
                deleted_count = old_audit_logs.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} audit logs'))
        
        # Clean up old DLQ logs
        old_dlq_logs = DLQLog.objects.filter(created_at__lt=audit_logs_cutoff)
        dlq_count = old_dlq_logs.count()
        
        if dlq_count > 0:
            self.stdout.write(f"Found {dlq_count} DLQ logs older than {audit_logs_days} days")
            if not dry_run and (force or self.confirm_deletion('DLQ logs', dlq_count)):
                deleted_count = old_dlq_logs.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} DLQ logs'))
        
        # Clean up old denied payments (keep verified ones)
        old_denied_payments = Payment.objects.filter(
            status=Payment.Status.DENIED,
            created_at__lt=cutoff_date
        )
        payment_count = old_denied_payments.count()
        
        if payment_count > 0:
            self.stdout.write(f"Found {payment_count} old denied payments")
            if not dry_run and (force or self.confirm_deletion('denied payments', payment_count)):
                deleted_count = old_denied_payments.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} denied payments'))
        
        # Clean up old mess cuts
        old_mess_cuts = MessCut.objects.filter(
            to_date__lt=cutoff_date.date()
        )
        mess_cut_count = old_mess_cuts.count()
        
        if mess_cut_count > 0:
            self.stdout.write(f"Found {mess_cut_count} old mess cuts")
            if not dry_run and (force or self.confirm_deletion('old mess cuts', mess_cut_count)):
                deleted_count = old_mess_cuts.delete()[0]
                self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_count} old mess cuts'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN COMPLETED - No data was actually deleted'))
        else:
            self.stdout.write(self.style.SUCCESS('Cleanup completed successfully!'))

    def confirm_deletion(self, item_type, count):
        """Ask for confirmation before deleting data."""
        response = input(f"Delete {count} {item_type}? [y/N]: ")
        return response.lower() in ['y', 'yes']