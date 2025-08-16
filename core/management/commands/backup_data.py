from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.serializers import serialize
from django.db import models
import json
import os
from datetime import datetime

from core.models import Student, Payment, MessCut, ScanEvent, StaffToken, Settings


class Command(BaseCommand):
    help = 'Backup system data to JSON files'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='backups',
            help='Directory to save backup files (default: backups)',
        )
        parser.add_argument(
            '--include-scan-events',
            action='store_true',
            help='Include scan events in backup (can be large)',
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress backup files',
        )

    def handle(self, *args, **options):
        """Create backup of all system data."""
        
        output_dir = options['output_dir']
        include_scan_events = options['include_scan_events']
        compress = options['compress']
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Models to backup
        models_to_backup = [
            ('students', Student),
            ('payments', Payment),
            ('mess_cuts', MessCut),
            ('staff_tokens', StaffToken),
            ('settings', Settings),
        ]
        
        if include_scan_events:
            models_to_backup.append(('scan_events', ScanEvent))
        
        backup_files = []
        
        for name, model in models_to_backup:
            filename = f"{name}_{timestamp}.json"
            filepath = os.path.join(output_dir, filename)
            
            # Get all objects
            queryset = model.objects.all()
            count = queryset.count()
            
            if count == 0:
                self.stdout.write(f"No {name} to backup")
                continue
            
            # Serialize to JSON
            serialized_data = serialize('json', queryset, indent=2)
            
            # Write to file
            with open(filepath, 'w') as f:
                f.write(serialized_data)
            
            backup_files.append(filepath)
            self.stdout.write(f"Backed up {count} {name} to {filename}")
        
        # Create backup manifest
        manifest = {
            'backup_date': timezone.now().isoformat(),
            'files': backup_files,
            'include_scan_events': include_scan_events,
            'total_files': len(backup_files)
        }
        
        manifest_file = os.path.join(output_dir, f"backup_manifest_{timestamp}.json")
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        # Compress if requested
        if compress:
            self.compress_backup(output_dir, timestamp, backup_files + [manifest_file])
        
        self.stdout.write(
            self.style.SUCCESS(f'Backup completed successfully! Files saved to {output_dir}')
        )

    def compress_backup(self, output_dir, timestamp, files):
        """Compress backup files."""
        try:
            import tarfile
            
            archive_name = f"backup_{timestamp}.tar.gz"
            archive_path = os.path.join(output_dir, archive_name)
            
            with tarfile.open(archive_path, 'w:gz') as tar:
                for file_path in files:
                    tar.add(file_path, arcname=os.path.basename(file_path))
            
            # Remove individual files
            for file_path in files:
                os.remove(file_path)
            
            self.stdout.write(f"Compressed backup to {archive_name}")
            
        except ImportError:
            self.stdout.write(
                self.style.WARNING('tarfile not available, skipping compression')
            )