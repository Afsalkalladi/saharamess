from rest_framework import permissions
from django.conf import settings


class IsAdminUser(permissions.BasePermission):
    """
    Allows access only to admin users (based on Telegram ID).
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated and is admin
        if not request.user or not hasattr(request.user, 'telegram_id'):
            return False
        
        return request.user.telegram_id in settings.ADMIN_TG_IDS


class IsStaffUser(permissions.BasePermission):
    """
    Allows access only to staff users (with valid staff token).
    """
    
    def has_permission(self, request, view):
        # Check if user is authenticated with staff token
        if not request.user or not hasattr(request.user, 'staff_token'):
            return False
        
        return request.user.staff_token.is_valid


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object or admins to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Admin users can access everything
        if hasattr(request.user, 'telegram_id') and request.user.telegram_id in settings.ADMIN_TG_IDS:
            return True
        
        # Check if user owns the object
        if hasattr(obj, 'student') and hasattr(request.user, 'telegram_id'):
            return obj.student.tg_user_id == request.user.telegram_id
        
        if hasattr(obj, 'tg_user_id') and hasattr(request.user, 'telegram_id'):
            return obj.tg_user_id == request.user.telegram_id
        
        return False


class IsStudentOwner(permissions.BasePermission):
    """
    Allows access only to the student who owns the record.
    """
    
    def has_permission(self, request, view):
        return request.user and hasattr(request.user, 'telegram_id')
    
    def has_object_permission(self, request, view, obj):
        # Check if the student owns this object
        if hasattr(obj, 'student'):
            return obj.student.tg_user_id == request.user.telegram_id
        elif hasattr(obj, 'tg_user_id'):
            return obj.tg_user_id == request.user.telegram_id
        
        return False


class ReadOnlyOrAdmin(permissions.BasePermission):
    """
    Read-only permissions for anyone, write permissions only for admins.
    """
    
    def has_permission(self, request, view):
        # Read permissions for any authenticated request
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Write permissions only for admins
        if hasattr(request.user, 'telegram_id'):
            return request.user.telegram_id in settings.ADMIN_TG_IDS
        
        return False