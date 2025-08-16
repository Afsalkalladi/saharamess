from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta

from core.models import Student, Payment, MessCut, StaffToken, Settings


class StudentApprovalForm(forms.ModelForm):
    """Form for approving student registrations."""
    
    class Meta:
        model = Student
        fields = ['status', 'hostel', 'room_number']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'hostel': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter hostel name'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter room number'}),
        }


class PaymentVerificationForm(forms.ModelForm):
    """Form for verifying payment uploads."""
    
    verification_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add verification notes (optional)'
        }),
        required=False
    )
    
    class Meta:
        model = Payment
        fields = ['status', 'verified_amount']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'verified_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'placeholder': 'Enter verified amount'
            }),
        }
    
    def clean_verified_amount(self):
        """Validate verified amount."""
        amount = self.cleaned_data.get('verified_amount')
        if amount and amount <= 0:
            raise ValidationError("Verified amount must be positive.")
        return amount


class MessCutApprovalForm(forms.ModelForm):
    """Form for approving mess cut applications."""
    
    admin_notes = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Add admin notes (optional)'
        }),
        required=False
    )
    
    class Meta:
        model = MessCut
        fields = ['status']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class StaffTokenForm(forms.ModelForm):
    """Form for creating staff tokens."""
    
    expires_hours = forms.ChoiceField(
        choices=[
            (1, '1 Hour'),
            (4, '4 Hours'),
            (8, '8 Hours'),
            (24, '24 Hours (1 Day)'),
            (72, '72 Hours (3 Days)'),
            (168, '168 Hours (1 Week)'),
        ],
        initial=24,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = StaffToken
        fields = ['label']
        widgets = {
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Main Counter, Evening Shift'
            }),
        }
    
    def save(self, commit=True):
        """Save token with calculated expiry."""
        token = super().save(commit=False)
        hours = int(self.cleaned_data['expires_hours'])
        token.expires_at = timezone.now() + timedelta(hours=hours)
        
        if commit:
            token.save()
        return token


class SettingsForm(forms.ModelForm):
    """Form for updating system settings."""
    
    class Meta:
        model = Settings
        fields = ['key', 'value', 'description']
        widgets = {
            'key': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Setting key (e.g., MESS_OPEN_TIME)'
            }),
            'value': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Setting value'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Brief description of this setting'
            }),
        }


class BulkActionForm(forms.Form):
    """Form for bulk actions on multiple objects."""
    
    ACTION_CHOICES = [
        ('approve', 'Approve Selected'),
        ('reject', 'Reject Selected'),
        ('delete', 'Delete Selected'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    selected_ids = forms.CharField(
        widget=forms.HiddenInput()
    )
    
    confirmation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I confirm this bulk action'
    )


class DateRangeFilterForm(forms.Form):
    """Form for filtering data by date range."""
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    
    def clean(self):
        """Validate date range."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date must be before end date.")
            
            if (end_date - start_date).days > 365:
                raise ValidationError("Date range cannot exceed 365 days.")
        
        return cleaned_data


class MessClosureForm(forms.Form):
    """Form for creating mess closures."""
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Reason for mess closure'
        })
    )
    
    meal_types = forms.MultipleChoiceField(
        choices=[
            ('breakfast', 'Breakfast'),
            ('lunch', 'Lunch'),
            ('dinner', 'Dinner'),
        ],
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        required=False,
        help_text='Leave empty to close for all meals'
    )
    
    def clean(self):
        """Validate closure dates."""
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date must be before end date.")
            
            if start_date < timezone.now().date():
                raise ValidationError("Start date cannot be in the past.")
        
        return cleaned_data


class SystemStatsFilterForm(forms.Form):
    """Form for filtering system statistics."""
    
    PERIOD_CHOICES = [
        ('today', 'Today'),
        ('week', 'This Week'),
        ('month', 'This Month'),
        ('quarter', 'This Quarter'),
        ('year', 'This Year'),
        ('custom', 'Custom Range'),
    ]
    
    period = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        initial='week',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        required=False
    )
    
    include_weekends = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Include weekends in statistics'
    )