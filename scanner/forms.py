from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta
from core.models import StaffToken
from core.validators import validate_staff_token_label
import re


class StaffTokenGenerationForm(forms.Form):
    """Form for generating staff scanner tokens."""
    
    EXPIRY_CHOICES = [
        (1, '1 Hour (Testing)'),
        (4, '4 Hours (Short shift)'),
        (8, '8 Hours (Single shift)'),
        (24, '24 Hours (Full day)'),
        (72, '72 Hours (3 days)'),
        (168, '168 Hours (1 week)'),
        (720, '720 Hours (1 month)'),
        (0, 'Never expires'),
    ]
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter admin password',
            'autocomplete': 'current-password'
        }),
        label='Admin Password',
        help_text='Enter the admin password to generate scanner access tokens'
    )
    
    label = forms.CharField(
        max_length=100,
        validators=[validate_staff_token_label],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Main Counter, Breakfast Counter, Mobile Scanner'
        }),
        label='Device/Location Label',
        help_text='Descriptive name to identify this scanner device',
        initial='Scanner Device'
    )
    
    expires_hours = forms.ChoiceField(
        choices=EXPIRY_CHOICES,
        initial=24,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label='Token Validity Period',
        help_text='Choose validity period based on usage requirements'
    )
    
    def clean_password(self):
        """Validate admin password."""
        password = self.cleaned_data.get('password')
        
        if not password:
            raise ValidationError('Password is required.')
        
        # Here you would validate against your admin password
        # For now, using a simple check (in production, use proper authentication)
        from django.conf import settings
        admin_password = getattr(settings, 'STAFF_SCANNER_PASSWORD', 'admin123')
        
        if password != admin_password:
            raise ValidationError('Invalid admin password.')
        
        return password
    
    def clean_label(self):
        """Validate and clean token label."""
        label = self.cleaned_data.get('label', '').strip()
        
        if not label:
            raise ValidationError('Token label is required.')
        
        if len(label) < 3:
            raise ValidationError('Token label must be at least 3 characters long.')
        
        # Check for duplicate labels
        if StaffToken.objects.filter(label=label, active=True).exists():
            raise ValidationError(
                'A token with this label already exists. Please use a different label.'
            )
        
        return label
    
    def clean_expires_hours(self):
        """Validate expiry hours."""
        expires_hours = self.cleaned_data.get('expires_hours')
        
        try:
            expires_hours = int(expires_hours)
        except (ValueError, TypeError):
            raise ValidationError('Invalid expiry period.')
        
        if expires_hours < 0:
            raise ValidationError('Expiry period cannot be negative.')
        
        if expires_hours > 8760:  # More than 1 year
            raise ValidationError('Expiry period cannot exceed 1 year (8760 hours).')
        
        return expires_hours
    
    def generate_token(self):
        """Generate the staff token based on form data."""
        if not self.is_valid():
            return None
        
        import secrets
        import hashlib
        
        # Generate secure token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        
        # Calculate expiry date
        expires_hours = self.cleaned_data['expires_hours']
        expires_at = None
        if expires_hours > 0:
            expires_at = timezone.now() + timedelta(hours=expires_hours)
        
        # Create staff token
        staff_token = StaffToken.objects.create(
            label=self.cleaned_data['label'],
            token_hash=token_hash,
            expires_at=expires_at
        )
        
        return {
            'staff_token': staff_token,
            'raw_token': raw_token,
            'expires_hours': expires_hours
        }


class TokenRevocationForm(forms.Form):
    """Form for revoking staff tokens."""
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter admin password'
        }),
        label='Admin Password',
        help_text='Confirm admin password to revoke token'
    )
    
    token_id = forms.UUIDField(
        widget=forms.HiddenInput(),
        label='Token ID'
    )
    
    confirm_revocation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='I confirm that I want to revoke this token',
        help_text='This action cannot be undone'
    )
    
    def clean_password(self):
        """Validate admin password."""
        password = self.cleaned_data.get('password')
        
        from django.conf import settings
        admin_password = getattr(settings, 'STAFF_SCANNER_PASSWORD', 'admin123')
        
        if password != admin_password:
            raise ValidationError('Invalid admin password.')
        
        return password
    
    def clean_token_id(self):
        """Validate token exists and is active."""
        token_id = self.cleaned_data.get('token_id')
        
        try:
            token = StaffToken.objects.get(id=token_id)
            if not token.active:
                raise ValidationError('Token is already inactive.')
            return token_id
        except StaffToken.DoesNotExist:
            raise ValidationError('Token not found.')


class ScannerStatusForm(forms.Form):
    """Form for checking scanner status."""
    
    token = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter scanner token'
        }),
        label='Scanner Token',
        help_text='Enter the token from your scanner URL'
    )
    
    def clean_token(self):
        """Validate scanner token."""
        token = self.cleaned_data.get('token', '').strip()
        
        if not token:
            raise ValidationError('Scanner token is required.')
        
        # Validate token format (URL-safe base64)
        if not re.match(r'^[A-Za-z0-9_-]+$', token):
            raise ValidationError('Invalid token format.')
        
        # Check if token exists and is valid
        import hashlib
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        try:
            staff_token = StaffToken.objects.get(token_hash=token_hash, active=True)
            if not staff_token.is_valid:
                raise ValidationError('Token has expired or is inactive.')
            
            # Store the token object for later use
            self.staff_token = staff_token
            
        except StaffToken.DoesNotExist:
            raise ValidationError('Invalid token.')
        
        return token


class BulkTokenManagementForm(forms.Form):
    """Form for bulk token management operations."""
    
    ACTION_CHOICES = [
        ('activate', 'Activate selected tokens'),
        ('deactivate', 'Deactivate selected tokens'),
        ('delete_expired', 'Delete expired tokens'),
        ('extend_expiry', 'Extend expiry for selected tokens'),
    ]
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control'
        }),
        label='Admin Password'
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label='Action'
    )
    
    token_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False,
        help_text='Comma-separated list of token IDs'
    )
    
    extend_hours = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=8760,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Hours to extend'
        }),
        label='Extend by (hours)',
        help_text='Number of hours to extend expiry (required for extend_expiry action)'
    )
    
    def clean_password(self):
        """Validate admin password."""
        password = self.cleaned_data.get('password')
        
        from django.conf import settings
        admin_password = getattr(settings, 'STAFF_SCANNER_PASSWORD', 'admin123')
        
        if password != admin_password:
            raise ValidationError('Invalid admin password.')
        
        return password
    
    def clean_token_ids(self):
        """Validate token IDs."""
        token_ids_str = self.cleaned_data.get('token_ids', '')
        
        if not token_ids_str.strip():
            return []
        
        try:
            token_ids = [id.strip() for id in token_ids_str.split(',') if id.strip()]
            
            # Validate each ID is a valid UUID
            import uuid
            validated_ids = []
            for token_id in token_ids:
                try:
                    uuid.UUID(token_id)
                    validated_ids.append(token_id)
                except ValueError:
                    raise ValidationError(f'Invalid token ID: {token_id}')
            
            return validated_ids
            
        except Exception as e:
            raise ValidationError(f'Error parsing token IDs: {str(e)}')
    
    def clean(self):
        """Cross-field validation."""
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        extend_hours = cleaned_data.get('extend_hours')
        token_ids = cleaned_data.get('token_ids', [])
        
        # Check if extend_hours is required
        if action == 'extend_expiry' and not extend_hours:
            raise ValidationError('Extend hours is required for extend expiry action.')
        
        # Check if token_ids is required for certain actions
        if action in ['activate', 'deactivate', 'extend_expiry'] and not token_ids:
            raise ValidationError('No tokens selected for this action.')
        
        return cleaned_data
    
    def execute_action(self):
        """Execute the bulk action."""
        if not self.is_valid():
            return False, "Form validation failed"
        
        action = self.cleaned_data['action']
        token_ids = self.cleaned_data['token_ids']
        extend_hours = self.cleaned_data.get('extend_hours')
        
        try:
            if action == 'activate':
                count = StaffToken.objects.filter(id__in=token_ids).update(active=True)
                return True, f"Activated {count} tokens"
            
            elif action == 'deactivate':
                count = StaffToken.objects.filter(id__in=token_ids).update(active=False)
                return True, f"Deactivated {count} tokens"
            
            elif action == 'delete_expired':
                expired_tokens = StaffToken.objects.filter(
                    expires_at__lt=timezone.now(),
                    active=False
                )
                count = expired_tokens.count()
                expired_tokens.delete()
                return True, f"Deleted {count} expired tokens"
            
            elif action == 'extend_expiry':
                tokens = StaffToken.objects.filter(id__in=token_ids)
                count = 0
                
                for token in tokens:
                    if token.expires_at:
                        token.expires_at += timedelta(hours=extend_hours)
                        token.save()
                        count += 1
                
                return True, f"Extended expiry for {count} tokens by {extend_hours} hours"
            
            else:
                return False, "Unknown action"
                
        except Exception as e:
            return False, f"Error executing action: {str(e)}"


class QRScanConfigForm(forms.Form):
    """Form for configuring QR scan settings."""
    
    auto_meal_detection = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Auto-detect current meal',
        help_text='Automatically select meal based on current time'
    )
    
    sound_notifications = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Sound notifications',
        help_text='Play sound on successful/failed scans'
    )
    
    vibration_feedback = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Vibration feedback',
        help_text='Vibrate device on scan events'
    )
    
    camera_torch = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label='Camera torch',
        help_text='Enable camera torch for low-light scanning'