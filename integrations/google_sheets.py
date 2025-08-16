import json
import logging
from typing import Dict, List, Any
from datetime import datetime

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from django.conf import settings

logger = logging.getLogger(__name__)


class GoogleSheetsService:
    """Service for Google Sheets backup and logging."""
    
    def __init__(self):
        self.spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
        self.service = self._get_service()
    
    def _get_service(self):
        """Get authenticated Google Sheets service."""
        try:
            credentials_info = json.loads(settings.GOOGLE_SHEETS_CREDENTIALS)
            credentials = Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            service = build('sheets', 'v4', credentials=credentials)
            return service
        except Exception as e:
            logger.error(f"Failed to create Google Sheets service: {str(e)}")
            raise
    
    def _get_or_create_sheet(self, sheet_name: str) -> bool:
        """Get or create a sheet in the spreadsheet."""
        try:
            # Get existing sheets
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            existing_sheets = [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
            
            if sheet_name not in existing_sheets:
                # Create new sheet
                request = {
                    'addSheet': {
                        'properties': {
                            'title': sheet_name
                        }
                    }
                }
                
                self.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.spreadsheet_id,
                    body={'requests': [request]}
                ).execute()
                
                logger.info(f"Created new sheet: {sheet_name}")
                
                # Add headers
                self._add_headers(sheet_name)
            
            return True
            
        except HttpError as e:
            logger.error(f"Failed to get/create sheet {sheet_name}: {str(e)}")
            return False
    
    def _add_headers(self, sheet_name: str):
        """Add headers to a new sheet."""
        headers_map = {
            'registrations': [
                'Timestamp', 'Event Type', 'Student ID', 'Student Name', 
                'Roll Number', 'Room Number', 'Phone', 'Status', 'TG User ID'
            ],
            'payments': [
                'Timestamp', 'Event Type', 'Payment ID', 'Student ID', 'Student Name',
                'Roll Number', 'Cycle Start', 'Cycle End', 'Amount', 'Status', 
                'Source', 'Screenshot URL', 'Reviewer Admin ID'
            ],
            'mess_cuts': [
                'Timestamp', 'Event Type', 'Mess Cut ID', 'Student ID', 'Student Name',
                'Roll Number', 'From Date', 'To Date', 'Applied By', 'Applied At'
            ],
            'mess_closures': [
                'Timestamp', 'Event Type', 'Closure ID', 'From Date', 'To Date',
                'Reason', 'Created By Admin ID', 'Created At'
            ],
            'scan_events': [
                'Timestamp', 'Scan ID', 'Student ID', 'Student Name', 'Roll Number',
                'Meal', 'Result', 'Device Info', 'Staff Token ID', 'Scanned At'
            ],
            'audit_logs': [
                'Timestamp', 'Actor Type', 'Actor ID', 'Event Type', 'Payload'
            ]
        }
        
        headers = headers_map.get(sheet_name, ['Timestamp', 'Data'])
        
        try:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption='USER_ENTERED',
                body={'values': [headers]}
            ).execute()
            
            logger.info(f"Added headers to sheet: {sheet_name}")
            
        except HttpError as e:
            logger.error(f"Failed to add headers to {sheet_name}: {str(e)}")
    
    def append_data(self, sheet_name: str, data: Dict[str, Any]) -> bool:
        """Append data to a sheet."""
        try:
            # Ensure sheet exists
            if not self._get_or_create_sheet(sheet_name):
                return False
            
            # Prepare row data based on sheet type
            row_data = self._prepare_row_data(sheet_name, data)
            
            # Append to sheet
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:Z",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            logger.info(f"Appended data to {sheet_name}: {data.get('event_type', 'unknown')}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to append data to {sheet_name}: {str(e)}")
            return False
    
    def _prepare_row_data(self, sheet_name: str, data: Dict[str, Any]) -> List[str]:
        """Prepare row data for different sheet types."""
        
        if sheet_name == 'registrations':
            return [
                data.get('timestamp', ''),
                data.get('event_type', ''),
                data.get('student_id', ''),
                data.get('student_name', ''),
                data.get('roll_no', ''),
                data.get('room_no', ''),
                data.get('phone', ''),
                data.get('status', ''),
                data.get('tg_user_id', '')
            ]
        
        elif sheet_name == 'payments':
            return [
                data.get('timestamp', ''),
                data.get('event_type', ''),
                data.get('payment_id', ''),
                data.get('student_id', ''),
                data.get('student_name', ''),
                data.get('roll_no', ''),
                data.get('cycle_start', ''),
                data.get('cycle_end', ''),
                str(data.get('amount', '')),
                data.get('status', ''),
                data.get('source', ''),
                data.get('screenshot_url', ''),
                data.get('reviewer_admin_id', '')
            ]
        
        elif sheet_name == 'mess_cuts':
            return [
                data.get('timestamp', ''),
                data.get('event_type', ''),
                data.get('mess_cut_id', ''),
                data.get('student_id', ''),
                data.get('student_name', ''),
                data.get('roll_no', ''),
                data.get('from_date', ''),
                data.get('to_date', ''),
                data.get('applied_by', ''),
                data.get('applied_at', '')
            ]
        
        elif sheet_name == 'mess_closures':
            return [
                data.get('timestamp', ''),
                data.get('event_type', ''),
                data.get('closure_id', ''),
                data.get('from_date', ''),
                data.get('to_date', ''),
                data.get('reason', ''),
                data.get('created_by_admin_id', ''),
                data.get('created_at', '')
            ]
        
        elif sheet_name == 'scan_events':
            return [
                data.get('timestamp', ''),
                data.get('scan_id', ''),
                data.get('student_id', ''),
                data.get('student_name', ''),
                data.get('roll_no', ''),
                data.get('meal', ''),
                data.get('result', ''),
                data.get('device_info', ''),
                data.get('staff_token_id', ''),
                data.get('scanned_at', '')
            ]
        
        elif sheet_name == 'audit_logs':
            return [
                data.get('timestamp', ''),
                data.get('actor_type', ''),
                data.get('actor_id', ''),
                data.get('event_type', ''),
                json.dumps(data.get('payload', {}))
            ]
        
        else:
            # Generic format
            return [
                data.get('timestamp', datetime.now().isoformat()),
                json.dumps(data)
            ]
    
    def bulk_append_data(self, sheet_name: str, data_list: List[Dict[str, Any]]) -> bool:
        """Append multiple rows to a sheet."""
        try:
            if not self._get_or_create_sheet(sheet_name):
                return False
            
            # Prepare all rows
            rows = []
            for data in data_list:
                row_data = self._prepare_row_data(sheet_name, data)
                rows.append(row_data)
            
            # Bulk append
            result = self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:Z",
                valueInputOption='USER_ENTERED',
                insertDataOption='INSERT_ROWS',
                body={'values': rows}
            ).execute()
            
            logger.info(f"Bulk appended {len(rows)} rows to {sheet_name}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to bulk append to {sheet_name}: {str(e)}")
            return False
    
    def get_data(self, sheet_name: str, range_name: str = None) -> List[List[str]]:
        """Get data from a sheet."""
        try:
            range_name = range_name or f"{sheet_name}!A:Z"
            
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            values = result.get('values', [])
            logger.info(f"Retrieved {len(values)} rows from {sheet_name}")
            return values
            
        except HttpError as e:
            logger.error(f"Failed to get data from {sheet_name}: {str(e)}")
            return []
    
    def clear_sheet(self, sheet_name: str) -> bool:
        """Clear all data from a sheet (keeping headers)."""
        try:
            # Clear everything except first row (headers)
            self.service.spreadsheets().values().clear(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A2:Z",
                body={}
            ).execute()
            
            logger.info(f"Cleared data from {sheet_name}")
            return True
            
        except HttpError as e:
            logger.error(f"Failed to clear {sheet_name}: {str(e)}")
            return False
    
    def create_backup_summary(self) -> Dict[str, Any]:
        """Create a summary of backup status."""
        try:
            spreadsheet = self.service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            summary = {
                'spreadsheet_id': self.spreadsheet_id,
                'title': spreadsheet.get('properties', {}).get('title', 'Unknown'),
                'sheets': []
            }
            
            for sheet in spreadsheet.get('sheets', []):
                sheet_name = sheet['properties']['title']
                
                # Get row count
                data = self.get_data(sheet_name, f"{sheet_name}!A:A")
                row_count = len(data) - 1 if data else 0  # Subtract header row
                
                summary['sheets'].append({
                    'name': sheet_name,
                    'row_count': row_count,
                    'last_updated': datetime.now().isoformat()
                })
            
            return summary
            
        except HttpError as e:
            logger.error(f"Failed to create backup summary: {str(e)}")
            return {}


# Global instance - initialize only if not in test mode
try:
    from django.conf import settings
    if hasattr(settings, 'SHEETS_CREDENTIALS_JSON') and isinstance(settings.SHEETS_CREDENTIALS_JSON, dict):
        # Check if it's a real service account or test data
        if settings.SHEETS_CREDENTIALS_JSON.get('client_email', '').endswith('@test.iam.gserviceaccount.com'):
            sheets_service = None  # Skip initialization for test data
        else:
            sheets_service = GoogleSheetsService()
    else:
        sheets_service = None
except Exception as e:
    logger.error(f"Failed to initialize Google Sheets service: {e}")
    sheets_service = None