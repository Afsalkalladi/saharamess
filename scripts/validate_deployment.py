#!/usr/bin/env python3
"""
Deployment validation script for Mess Management System.
Tests all critical endpoints and functionality.
"""
import os
import sys
import json
import requests
import time
from urllib.parse import urljoin

# Add Django to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'mess_management.settings.production')

import django
django.setup()

from django.conf import settings
from core.models import Student, StaffToken
import logging

logger = logging.getLogger(__name__)

class DeploymentValidator:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.results = []
        self.session = requests.Session()
        
    def log_result(self, test_name, success, message="", details=None):
        """Log test result."""
        result = {
            'test': test_name,
            'success': success,
            'message': message,
            'details': details or {}
        }
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        
        if not success and details:
            print(f"   Details: {details}")
    
    def test_health_check(self):
        """Test API health check endpoint."""
        try:
            url = urljoin(self.base_url, '/api/v1/health/')
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') in ['healthy', 'degraded']:
                    self.log_result('Health Check', True, f"Status: {data['status']}")
                    return True
                else:
                    self.log_result('Health Check', False, f"Unhealthy status: {data.get('status')}")
            else:
                self.log_result('Health Check', False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result('Health Check', False, f"Exception: {str(e)}")
        
        return False
    
    def test_api_info(self):
        """Test API info endpoint."""
        try:
            url = urljoin(self.base_url, '/api/v1/info/')
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'name' in data and 'version' in data:
                    self.log_result('API Info', True, f"Version: {data.get('version')}")
                    return True
                else:
                    self.log_result('API Info', False, "Missing required fields")
            else:
                self.log_result('API Info', False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result('API Info', False, f"Exception: {str(e)}")
        
        return False
    
    def test_scanner_access(self):
        """Test scanner access page."""
        try:
            url = urljoin(self.base_url, '/scanner/')
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                if 'Access token required' in response.text:
                    self.log_result('Scanner Access', True, "Token validation working")
                    return True
                else:
                    self.log_result('Scanner Access', False, "Token validation not working")
            else:
                self.log_result('Scanner Access', False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result('Scanner Access', False, f"Exception: {str(e)}")
        
        return False
    
    def test_staff_token_generation(self):
        """Test staff token generation page."""
        try:
            url = urljoin(self.base_url, '/scanner/generate/')
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                if 'Staff Access Generator' in response.text or 'password' in response.text.lower():
                    self.log_result('Staff Token Generation', True, "Page accessible")
                    return True
                else:
                    self.log_result('Staff Token Generation', False, "Unexpected page content")
            else:
                self.log_result('Staff Token Generation', False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result('Staff Token Generation', False, f"Exception: {str(e)}")
        
        return False
    
    def test_telegram_webhook_endpoint(self):
        """Test Telegram webhook endpoint."""
        try:
            url = urljoin(self.base_url, '/api/v1/telegram/webhook/')
            
            # Test with invalid data (should not crash)
            response = self.session.post(url, json={'test': 'data'}, timeout=10)
            
            # Should return 200 or handle gracefully
            if response.status_code in [200, 400, 403]:
                self.log_result('Telegram Webhook', True, f"HTTP {response.status_code}")
                return True
            else:
                self.log_result('Telegram Webhook', False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result('Telegram Webhook', False, f"Exception: {str(e)}")
        
        return False
    
    def test_static_files(self):
        """Test static file serving."""
        try:
            # Test admin static files
            url = urljoin(self.base_url, '/static/admin/css/base.css')
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                self.log_result('Static Files', True, "Admin static files accessible")
                return True
            else:
                self.log_result('Static Files', False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result('Static Files', False, f"Exception: {str(e)}")
        
        return False
    
    def test_database_connectivity(self):
        """Test database connectivity."""
        try:
            from django.db import connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                
            if result and result[0] == 1:
                self.log_result('Database Connectivity', True, "Database accessible")
                return True
            else:
                self.log_result('Database Connectivity', False, "Unexpected query result")
                
        except Exception as e:
            self.log_result('Database Connectivity', False, f"Exception: {str(e)}")
        
        return False
    
    def test_environment_variables(self):
        """Test critical environment variables."""
        required_vars = [
            'DATABASE_URL',
            'TELEGRAM_BOT_TOKEN',
            'ADMIN_TG_IDS',
            'QR_SECRET'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(settings, var, None):
                missing_vars.append(var)
        
        if not missing_vars:
            self.log_result('Environment Variables', True, "All required variables set")
            return True
        else:
            self.log_result('Environment Variables', False, f"Missing: {', '.join(missing_vars)}")
            return False
    
    def test_model_migrations(self):
        """Test that all models are properly migrated."""
        try:
            # Test creating a simple query on each model
            from core.models import Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken, AuditLog, Settings
            
            models_to_test = [Student, Payment, MessCut, MessClosure, ScanEvent, StaffToken, AuditLog, Settings]
            
            for model in models_to_test:
                try:
                    model.objects.count()
                except Exception as e:
                    self.log_result('Model Migrations', False, f"Error with {model.__name__}: {str(e)}")
                    return False
            
            self.log_result('Model Migrations', True, "All models accessible")
            return True
            
        except Exception as e:
            self.log_result('Model Migrations', False, f"Exception: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all validation tests."""
        print("🚀 Starting deployment validation...\n")
        
        tests = [
            self.test_environment_variables,
            self.test_database_connectivity,
            self.test_model_migrations,
            self.test_health_check,
            self.test_api_info,
            self.test_scanner_access,
            self.test_staff_token_generation,
            self.test_telegram_webhook_endpoint,
            self.test_static_files,
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
            time.sleep(0.5)  # Small delay between tests
        
        print(f"\n📊 Validation Results: {passed}/{total} tests passed")
        
        if passed == total:
            print("🎉 All tests passed! Deployment is ready.")
            return True
        else:
            print("⚠️  Some tests failed. Please review the issues above.")
            return False
    
    def generate_report(self):
        """Generate detailed validation report."""
        report = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'base_url': self.base_url,
            'total_tests': len(self.results),
            'passed_tests': sum(1 for r in self.results if r['success']),
            'failed_tests': sum(1 for r in self.results if not r['success']),
            'results': self.results
        }
        
        return report


def main():
    """Main validation function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate Mess Management System deployment')
    parser.add_argument('--url', default='http://localhost:8000', 
                       help='Base URL of the deployment (default: http://localhost:8000)')
    parser.add_argument('--report', help='Save detailed report to JSON file')
    
    args = parser.parse_args()
    
    validator = DeploymentValidator(args.url)
    success = validator.run_all_tests()
    
    if args.report:
        report = validator.generate_report()
        with open(args.report, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\n📄 Detailed report saved to: {args.report}")
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
