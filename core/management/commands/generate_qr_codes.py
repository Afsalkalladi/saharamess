from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
import os
import qrcode
from PIL import Image, ImageDraw, ImageFont
import io
import base64

from core.models import Student
from core.services import QRService


class Command(BaseCommand):
    help = 'Generate QR codes for all approved students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output-dir',
            type=str,
            default='qr_codes',
            help='Directory to save QR code images (default: qr_codes)',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['png', 'jpg', 'pdf'],
            default='png',
            help='Output format for QR codes (default: png)',
        )
        parser.add_argument(
            '--size',
            type=int,
            default=300,
            help='QR code size in pixels (default: 300)',
        )
        parser.add_argument(
            '--student-id',
            type=str,
            help='Generate QR code for specific student (roll number)',
        )
        parser.add_argument(
            '--include-info',
            action='store_true',
            help='Include student info text below QR code',
        )

    def handle(self, *args, **options):
        """Generate QR codes for students."""
        
        output_dir = options['output_dir']
        format_type = options['format']
        size = options['size']
        student_id = options['student_id']
        include_info = options['include_info']
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Initialize QR service
        qr_service = QRService()
        
        # Get students to generate QR codes for
        if student_id:
            students = Student.objects.filter(
                roll_number=student_id,
                status=Student.Status.APPROVED
            )
            if not students.exists():
                self.stdout.write(
                    self.style.ERROR(f'Student {student_id} not found or not approved')
                )
                return
        else:
            students = Student.objects.filter(status=Student.Status.APPROVED)
        
        if not students.exists():
            self.stdout.write(self.style.WARNING('No approved students found'))
            return
        
        generated_count = 0
        
        for student in students:
            try:
                # Generate QR code data
                qr_data = qr_service.generate_qr_data(student)
                
                # Create QR code
                qr = qrcode.QRCode(
                    version=1,
                    error_correction=qrcode.constants.ERROR_CORRECT_M,
                    box_size=10,
                    border=4,
                )
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                # Create QR code image
                qr_img = qr.make_image(fill_color="black", back_color="white")
                qr_img = qr_img.resize((size, size), Image.Resampling.LANCZOS)
                
                if include_info:
                    # Create image with student info
                    final_img = self.add_student_info(qr_img, student, size)
                else:
                    final_img = qr_img
                
                # Save image
                filename = f"{student.roll_number}_qr.{format_type}"
                filepath = os.path.join(output_dir, filename)
                
                if format_type == 'pdf':
                    final_img.save(filepath, 'PDF', resolution=300.0)
                else:
                    final_img.save(filepath, format_type.upper())
                
                generated_count += 1
                self.stdout.write(f"Generated QR code for {student.roll_number}")
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Failed to generate QR code for {student.roll_number}: {e}')
                )
        
        self.stdout.write(
            self.style.SUCCESS(f'Generated {generated_count} QR codes in {output_dir}')
        )

    def add_student_info(self, qr_img, student, qr_size):
        """Add student information below QR code."""
        try:
            # Calculate dimensions
            info_height = 120
            total_width = qr_size
            total_height = qr_size + info_height
            
            # Create new image
            final_img = Image.new('RGB', (total_width, total_height), 'white')
            
            # Paste QR code
            final_img.paste(qr_img, (0, 0))
            
            # Draw student info
            draw = ImageDraw.Draw(final_img)
            
            # Try to load a font, fallback to default
            try:
                font_large = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 16)
                font_small = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", 12)
            except:
                font_large = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Student info text
            info_lines = [
                f"Roll No: {student.roll_number}",
                f"Name: {student.name}",
                f"Hostel: {student.hostel or 'N/A'}",
                f"Room: {student.room_number or 'N/A'}"
            ]
            
            # Draw text
            y_offset = qr_size + 10
            for i, line in enumerate(info_lines):
                font = font_large if i == 0 else font_small
                bbox = draw.textbbox((0, 0), line, font=font)
                text_width = bbox[2] - bbox[0]
                x_pos = (total_width - text_width) // 2
                draw.text((x_pos, y_offset), line, fill='black', font=font)
                y_offset += 25 if i == 0 else 20
            
            return final_img
            
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f'Failed to add student info: {e}. Using QR code only.')
            )
            return qr_img