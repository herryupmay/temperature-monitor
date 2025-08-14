"""
Gmail Service for Temperature Monitor
Clean version using dedicated PDF parser service
"""

import re
import json
import base64
import logging
from datetime import datetime, timedelta
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

# Import the clean PDF parser
try:
    from .pdf_parser import PDFTemperatureParser
    PDF_PARSER_AVAILABLE = True
except ImportError:
    PDF_PARSER_AVAILABLE = False
    PDFTemperatureParser = None

# Import the LocationManager
try:
    from .location_manager import LocationManager
    LOCATION_MANAGER_AVAILABLE = True
except ImportError:
    LOCATION_MANAGER_AVAILABLE = False
    LocationManager = None

# Import the sheets service
try:
    from .sheets_service import TemperatureSheetsService
    SHEETS_SERVICE_AVAILABLE = True
except ImportError:
    SHEETS_SERVICE_AVAILABLE = False
    TemperatureSheetsService = None

logger = logging.getLogger(__name__)

class GmailTemperatureService:
    """Service for handling temperature-related emails via Gmail API"""
    
    def __init__(self, auth_manager, config_manager=None):
        """Initialize with authenticated Gmail service"""
        self.auth_manager = auth_manager
        self.config_manager = config_manager
        self.gmail_service = None
        self.last_check_time = None
        
        # Initialize PDF parser
        if PDF_PARSER_AVAILABLE:
            self.pdf_parser = PDFTemperatureParser()
        else:
            self.pdf_parser = None
            logger.warning("PDF parser not available")
        
        # Initialize LocationManager if available
        if LOCATION_MANAGER_AVAILABLE:
            self.location_manager = LocationManager(config_manager)
        else:
            self.location_manager = None
            logger.warning("LocationManager not available - using basic location extraction")
        
        # Initialize Sheets service if available
        if SHEETS_SERVICE_AVAILABLE:
            spreadsheet_id = config_manager.config.get("sheets", {}).get("spreadsheet_id") if config_manager else None
            self.sheets_service = TemperatureSheetsService(auth_manager, spreadsheet_id, config_manager)
        else:
            self.sheets_service = None
            logger.warning("Sheets service not available")
        
        # Temperature email patterns to search for
        self.temp_keywords = [
            'temperature',
            'temp',
            'refrigerator',
            'fridge',
            'freezer',
            'monitoring',
            'sensor',
            'alert',
            'degree',
            'celsius',
            'fahrenheit',
            'clever logger',
            'min-max'
        ]
    
    def connect(self):
        """Connect to Gmail service"""
        try:
            if not self.auth_manager.is_authenticated():
                success, message = self.auth_manager.authenticate()
                if not success:
                    return False, message
            
            self.gmail_service = self.auth_manager.get_gmail_service()
            logger.info("Gmail service connected successfully")
            return True, "Gmail service connected"
            
        except Exception as e:
            error_msg = f"Error connecting Gmail service: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def search_temperature_emails(self, hours_back=24, max_results=50):
        """Search for temperature emails using user-configured filters"""
        try:
            if not self.gmail_service:
                success, message = self.connect()
                if not success:
                    return [], message
            
            # Get email filter configuration
            email_filters = self.config_manager.config.get('gmail', {}).get('email_filters', {}) if self.config_manager else {}
            
            # Default filters if not configured
            default_filters = {
                "sender_addresses": ["notifications@cleverlogger.com"],
                "subject_keywords": ["min-max", "temperature report"],
                "require_pdf": True,
                "exclude_keywords": ["test", "configuration"]
            }
            
            sender_addresses = email_filters.get('sender_addresses', default_filters['sender_addresses'])
            subject_keywords = email_filters.get('subject_keywords', default_filters['subject_keywords'])
            require_pdf = email_filters.get('require_pdf', default_filters['require_pdf'])
            exclude_keywords = email_filters.get('exclude_keywords', default_filters['exclude_keywords'])
            
            logger.info(f"Email filters - Senders: {sender_addresses}, Keywords: {subject_keywords}")
            
            # Build Gmail search query
            query_parts = []
            
            # Sender filter
            if sender_addresses:
                sender_query = ' OR '.join([f'from:{sender}' for sender in sender_addresses])
                query_parts.append(f'({sender_query})')
            
            # Subject keywords filter
            if subject_keywords:
                subject_query = ' OR '.join([f'subject:"{keyword}"' for keyword in subject_keywords])
                query_parts.append(f'({subject_query})')
            
            # Exclude keywords filter
            if exclude_keywords:
                exclude_query = ' AND '.join([f'-subject:"{keyword}"' for keyword in exclude_keywords])
                query_parts.append(exclude_query)
            
            # PDF attachment filter
            if require_pdf:
                query_parts.append('has:attachment filename:pdf')
            
            # Time filter
            if hours_back:
                if hours_back <= 24:
                    time_filter = f"newer_than:{hours_back}h"
                else:
                    days = max(1, hours_back // 24)
                    time_filter = f"newer_than:{days}d"
                query_parts.append(time_filter)
            
            # Combine query parts
            query = ' '.join(query_parts)
            logger.info(f"Gmail search query: {query}")
            
            # Search emails
            results = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            logger.info(f"Found {len(messages)} potential temperature emails")
            
            # Get detailed email data with validation
            temperature_emails = []
            for message in messages:
                try:
                    email_data = self.get_email_details(message['id'])
                    if email_data:
                        logger.info(f"📧 Email details extracted: {email_data.get('subject', 'No subject')}")
                        logger.info(f"   PDF data: {len(email_data.get('pdf_data', {}).get('temperatures', []))} temps, {len(email_data.get('pdf_data', {}).get('locations', []))} locations")
                        logger.info(f"   Body data: {len(email_data.get('temperature_data', {}).get('temperatures', []))} temps")
                        
                        if self.validate_temperature_email(email_data, email_filters):
                            temperature_emails.append(email_data)
                            logger.info(f"✅ Email accepted: {email_data.get('subject')}")
                        else:
                            logger.info(f"❌ Email rejected: {email_data.get('subject')}")
                    else:
                        logger.warning(f"Failed to extract email details for message {message['id']}")
                except Exception as e:
                    logger.warning(f"Error processing email {message['id']}: {e}")
                    continue
            
            return temperature_emails, f"Found {len(temperature_emails)} temperature reports"
            
        except HttpError as e:
            error_msg = f"Gmail API error during search: {e}"
            logger.error(error_msg)
            return [], error_msg
        except Exception as e:
            error_msg = f"Error searching temperature emails: {e}"
            logger.error(error_msg)
            return [], error_msg

    def validate_temperature_email(self, email_data, email_filters):
        """Validate that email matches user criteria and has temperature data"""
        try:
            subject = email_data.get('subject', '').lower()
            sender = email_data.get('sender', '').lower()
            
            # Check sender matches configured addresses
            sender_addresses = email_filters.get('sender_addresses', [])
            sender_match = False
            for allowed_sender in sender_addresses:
                if allowed_sender.lower() in sender:
                    sender_match = True
                    break
            
            if sender_addresses and not sender_match:
                logger.info(f"Sender not in allowed list: {sender}")
                return False
            
            # Check subject contains required keywords
            subject_keywords = email_filters.get('subject_keywords', [])
            keyword_match = False
            for keyword in subject_keywords:
                if keyword.lower() in subject:
                    keyword_match = True
                    break
            
            if subject_keywords and not keyword_match:
                logger.info(f"Subject doesn't contain required keywords: {subject}")
                return False
            
            # Check subject doesn't contain excluded keywords
            exclude_keywords = email_filters.get('exclude_keywords', [])
            for exclude_word in exclude_keywords:
                if exclude_word.lower() in subject:
                    logger.info(f"Subject contains excluded keyword '{exclude_word}': {subject}")
                    return False
            
            # Check for temperature data
            pdf_data = email_data.get('pdf_data', {})
            temp_data = email_data.get('temperature_data', {})
            
            require_pdf = email_filters.get('require_pdf', False)
            has_pdf = len(pdf_data.get('temperatures', [])) > 0  # Check for temperature data in PDF
            has_temp_data = len(pdf_data.get('temperatures', [])) > 0 or temp_data.get('has_temperature_data', False)
            
            if require_pdf and not has_pdf:
                logger.info(f"PDF required but not found: {subject}")
                return False
            
            if not has_temp_data:
                logger.info(f"No temperature data found: {subject}")
                return False
            
            logger.info(f"✅ Valid temperature email: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error validating email: {e}")
            return False

    def get_email_details(self, message_id):
        """Get detailed information from an email"""
        try:
            message = self.gmail_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            # Extract email metadata
            headers = message['payload'].get('headers', [])
            header_dict = {h['name'].lower(): h['value'] for h in headers}
            
            subject = header_dict.get('subject', '')
            sender = header_dict.get('from', '')
            date_str = header_dict.get('date', '')
            
            # Parse date
            try:
                from email.utils import parsedate_to_datetime
                email_date = parsedate_to_datetime(date_str)
            except:
                email_date = datetime.now()
            
            # Extract email body
            body_text = self.extract_email_body(message['payload'])
            
            # Extract and process PDF attachments using clean parser
            pdf_data = self.extract_pdf_attachments(message['payload'], message_id)
            
            # Determine what temperature data to use
            all_temperatures = []
            all_alerts = []
            
            if pdf_data.get('temperatures') and len(pdf_data['temperatures']) > 0:
                # Use PDF data exclusively if available
                all_temperatures = pdf_data['temperatures']
                logger.info(f"Using PDF temperature data: {len(all_temperatures)} readings")
            else:
                # Only use body parsing if PDF parsing failed
                temp_data = self.parse_body_temperature_data(body_text, subject)
                all_temperatures = temp_data.get('temperatures', [])
                all_alerts = temp_data.get('alerts', [])
                logger.info(f"Using body temperature data: {len(all_temperatures)} readings")
            
            # Process discovered locations
            if self.location_manager and pdf_data.get('locations'):
                self.process_discovered_locations(pdf_data['locations'])
            
            # Create email info
            email_info = {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'date': email_date,
                'body_preview': body_text[:200] + '...' if len(body_text) > 200 else body_text,
                'temperature_data': {
                    'temperatures': all_temperatures,
                    'alerts': all_alerts,
                    'has_temperature_data': len(all_temperatures) > 0
                },
                'pdf_data': pdf_data,
                'raw_body': body_text
            }
            
            total_readings = len(all_temperatures)
            logger.info(f"Email processed: {subject} - {total_readings} readings")
            return email_info
            
        except Exception as e:
            logger.error(f"Error getting email details for {message_id}: {e}")
            return None
    
    def extract_email_body(self, payload):
        """Extract text content from email payload"""
        body_text = ""
        
        try:
            # Handle different email structures
            if 'parts' in payload:
                # Multi-part message
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        if 'data' in part['body']:
                            body_text += base64.urlsafe_b64decode(
                                part['body']['data']).decode('utf-8')
                    elif part['mimeType'] == 'text/html' and not body_text:
                        # Fallback to HTML if no plain text
                        if 'data' in part['body']:
                            html_content = base64.urlsafe_b64decode(
                                part['body']['data']).decode('utf-8')
                            # Basic HTML stripping (for simple cases)
                            body_text = re.sub('<[^<]+?>', '', html_content)
            else:
                # Single part message
                if payload['mimeType'] == 'text/plain':
                    if 'data' in payload['body']:
                        body_text = base64.urlsafe_b64decode(
                            payload['body']['data']).decode('utf-8')
        
        except Exception as e:
            logger.error(f"Error extracting email body: {e}")
        
        return body_text.strip()
    
    def extract_pdf_attachments(self, payload, message_id=None):
        """Extract and process PDF attachments using clean parser"""
        pdf_data = {
            'attachments': [],
            'temperatures': [],
            'locations': [],
            'daily_summary': None
        }
        
        if not self.pdf_parser:
            logger.warning("PDF parser not available")
            return pdf_data
        
        try:
            # Check for attachments in message parts
            parts = payload.get('parts', [])
            if not parts:
                parts = [payload]  # Single part message
            
            for part in parts:
                # Look for PDF attachments
                if part.get('filename', '').lower().endswith('.pdf'):
                    pdf_info = self.process_pdf_attachment(part, message_id)
                    if pdf_info:
                        pdf_data['attachments'].append(pdf_info)
                        pdf_data['temperatures'].extend(pdf_info.get('temperatures', []))
                        pdf_data['locations'].extend(pdf_info.get('locations', []))
                        
                        # Set daily summary if available
                        if pdf_info.get('daily_summary'):
                            pdf_data['daily_summary'] = pdf_info['daily_summary']
                
                # Check for nested parts (multipart messages)
                if 'parts' in part:
                    nested_pdf = self.extract_pdf_attachments(part, message_id)
                    pdf_data['attachments'].extend(nested_pdf['attachments'])
                    pdf_data['temperatures'].extend(nested_pdf['temperatures'])
                    pdf_data['locations'].extend(nested_pdf['locations'])
                    if nested_pdf.get('daily_summary'):
                        pdf_data['daily_summary'] = nested_pdf['daily_summary']
            
            return pdf_data
            
        except Exception as e:
            logger.error(f"Error extracting PDF attachments: {e}")
            return pdf_data
    
    def process_pdf_attachment(self, attachment_part, message_id=None):
        """Process a single PDF attachment using clean parser"""
        try:
            filename = attachment_part.get('filename', 'attachment.pdf')
            attachment_id = attachment_part['body'].get('attachmentId')
            
            if not attachment_id:
                return None
            
            # Download the attachment
            attachment_data = self.gmail_service.users().messages().attachments().get(
                userId='me',
                messageId=message_id or 'temp',
                id=attachment_id
            ).execute()
            
            # Decode the attachment data
            pdf_data = base64.urlsafe_b64decode(attachment_data['data'])
            
            # Parse PDF content using clean parser
            if self.pdf_parser:
                parse_result = self.pdf_parser.parse_pdf_data(pdf_data, filename)
                
                if parse_result['success']:
                    return {
                        'filename': filename,
                        'size': len(pdf_data),
                        'temperatures': parse_result['temperatures'],
                        'locations': parse_result['locations'],
                        'daily_summary': parse_result['daily_summary'],
                        'parser_success': True
                    }
                else:
                    logger.error(f"PDF parsing failed for {filename}: {parse_result.get('error', 'Unknown error')}")
                    return {
                        'filename': filename,
                        'size': len(pdf_data),
                        'temperatures': [],
                        'locations': [],
                        'daily_summary': None,
                        'parser_success': False,
                        'error': parse_result.get('error')
                    }
            else:
                logger.warning(f"No PDF parser available for {filename}")
                return None
            
        except Exception as e:
            logger.error(f"Error processing PDF attachment: {e}")
            return None
    
    def parse_body_temperature_data(self, text, subject=""):
        """Parse temperature values from email body text (fallback for non-PDF emails)"""
        temperatures = []
        alerts = []
        
        try:
            # Simple patterns for email body parsing
            temp_patterns = [
                r'(\d+\.?\d*)\s*°?[CF]',  # 25.5°C or 77°F
                r'(\d+\.?\d*)\s*degrees?\s*[CF]',  # 25.5 degrees C
                r'temperature:\s*(\d+\.?\d*)',  # temperature: 25.5
                r'temp:\s*(\d+\.?\d*)',  # temp: 25.5
            ]
            
            # Combine subject and body for parsing
            full_text = f"{subject} {text}".lower()
            
            # Find all temperature values
            for pattern in temp_patterns:
                matches = re.finditer(pattern, full_text, re.IGNORECASE)
                for match in matches:
                    try:
                        temp_value = float(match.group(1))
                        
                        # Skip unrealistic temperatures
                        if temp_value < -50 or temp_value > 100:
                            continue
                        
                        # Get context around the temperature
                        start = max(0, match.start() - 50)
                        end = min(len(full_text), match.end() + 50)
                        context = full_text[start:end].strip()
                        
                        # Determine if it's Celsius or Fahrenheit
                        unit = 'C'
                        if 'f' in match.group(0).lower() or 'fahrenheit' in context:
                            unit = 'F'
                            # Convert to Celsius for standardization
                            temp_celsius = (temp_value - 32) * 5/9
                        else:
                            temp_celsius = temp_value
                        
                        # Basic location extraction from context - but don't create fake locations
                        location = self.extract_basic_location_from_context(context)
                        
                        temp_reading = {
                            'value': round(temp_celsius, 1),
                            'unit': 'C',
                            'original_value': temp_value,
                            'original_unit': unit,
                            'location': location,
                            'context': context,
                            'type': 'current',
                            'timestamp': datetime.now()
                        }
                        
                        temperatures.append(temp_reading)
                        
                    except (ValueError, IndexError):
                        continue
            
            # Look for alert keywords
            alert_keywords = ['alert', 'warning', 'critical', 'alarm', 'fault', 'error', 'problem']
            for keyword in alert_keywords:
                if keyword in full_text:
                    alerts.append(keyword)
            
            # Remove duplicate temperatures (same value and location)
            unique_temps = []
            for temp in temperatures:
                is_duplicate = False
                for existing in unique_temps:
                    if (abs(existing['value'] - temp['value']) < 0.1 and 
                        existing['location'] == temp['location']):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    unique_temps.append(temp)
            
            # Only return body temperature data if PDF parsing failed to find locations
            # This prevents conflict between PDF and body parsing
            logger.debug(f"Body parsing found {len(unique_temps)} temperature readings")
            return {
                'temperatures': unique_temps,
                'alerts': list(set(alerts)),
                'has_temperature_data': len(unique_temps) > 0
            }
            
        except Exception as e:
            logger.error(f"Error parsing body temperature data: {e}")
            return {
                'temperatures': [],
                'alerts': [],
                'has_temperature_data': False
            }
    
    def extract_basic_location_from_context(self, context):
        """Basic location extraction from text context"""
        # Common location indicators
        location_patterns = [
            r'(fridge|refrigerator|freezer)\s*([a-z0-9]*)',
            r'(room|zone|area)\s*([a-z0-9]*)',
            r'(sensor|probe|monitor)\s*([a-z0-9]*)',
            r'([a-z]+)\s*(fridge|refrigerator|freezer)',
            r'(pharmacy|storage|cold)\s*(room|area)',
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, context, re.IGNORECASE)
            if match:
                location_name = ' '.join(match.groups()).strip().title()
                return location_name or 'Main Location'
        
        return "Main Location"
    
    def process_discovered_locations(self, discovered_locations):
        """Process and register newly discovered locations"""
        if not self.location_manager or not discovered_locations:
            return
        
        for location_info in discovered_locations:
            try:
                # Convert PDF parser format to LocationManager format
                location_data = {
                    'name': location_info['name'],
                    'type': 'custom',
                    'confidence': 'high',
                    'source': 'pdf_parser',
                    'min_temp': location_info.get('min_temp_threshold'),
                    'max_temp': location_info.get('max_temp_threshold'),
                    'description': location_info.get('description'),
                    'device_info': {
                        'serial_number': location_info.get('device_sn'),
                        'model': location_info.get('device_model'),
                        'log_interval': location_info.get('log_interval')
                    }
                }
                
                location_key = self.location_manager.register_discovered_location(location_data)
                logger.info(f"Processed discovered location: {location_key}")
            except Exception as e:
                logger.error(f"Error processing discovered location {location_info.get('name', 'Unknown')}: {e}")
        
        # Save discovered locations to configuration
        try:
            self.location_manager.save_discovered_locations()
        except Exception as e:
            logger.error(f"Error saving discovered locations: {e}")
    
    def get_temperature_summary(self, hours_back=24, auto_log_to_sheets=True, custom_logged_time=None):
        """Get a summary of recent temperature data with optional sheets logging - USES ONLY MOST RECENT EMAIL"""
        try:
            emails, message = self.search_temperature_emails(hours_back)
            
            if not emails:
                return {
                    'total_emails': 0,
                    'total_readings': 0,
                    'locations': [],
                    'alerts': [],
                    'latest_reading': None,
                    'discovered_locations': self.get_location_discovery_summary(),
                    'sheets_logged': False,
                    'message': message
                }
            
            # Use only the most recent email
            logger.info(f"Found {len(emails)} temperature emails, using only the most recent")
            
            # Sort emails by date (newest first) and take only the first one
            sorted_emails = sorted(emails, key=lambda x: x['date'], reverse=True)
            most_recent_email = sorted_emails[0]
            
            logger.info(f"Using most recent email: {most_recent_email['subject']} from {most_recent_email['date']}")
            
            # Process only the most recent email
            emails_to_process = [most_recent_email]
            
            # Aggregate data from the single most recent email
            all_temperatures = []
            all_alerts = []
            locations = set()
            
            for email in emails_to_process:  # Will only be 1 email now
                temp_data = email['temperature_data']
                all_temperatures.extend(temp_data['temperatures'])
                all_alerts.extend(temp_data['alerts'])
                
                for temp in temp_data['temperatures']:
                    locations.add(temp['location'])
            
            # Get latest reading (from the single email)
            latest_reading = None
            if all_temperatures:
                latest_reading = max(all_temperatures, key=lambda x: x['timestamp'])
            
            # Auto-log to sheets if enabled and we have data
            sheets_logged = False
            sheets_message = ""
            if auto_log_to_sheets and all_temperatures and self.sheets_service:
                sheets_logged, sheets_message = self.log_temperatures_to_sheets(
                    all_temperatures, 
                    list(locations),
                    custom_logged_time=custom_logged_time
                )
            
            summary = {
                'total_emails': len(emails),  # Total found
                'emails_processed': len(emails_to_process),  # Actually processed (1)
                'most_recent_email': {
                    'subject': most_recent_email['subject'],
                    'date': most_recent_email['date'].isoformat(),
                    'sender': most_recent_email['sender']
                },
                'total_readings': len(all_temperatures),
                'locations': list(locations),
                'alerts': list(set(all_alerts)),
                'latest_reading': latest_reading,
                'all_readings': all_temperatures,
                'discovered_locations': self.get_location_discovery_summary(),
                'sheets_logged': sheets_logged,
                'sheets_message': sheets_message,
                'message': f"Found {len(emails)} emails, processed most recent: {most_recent_email['subject']}"
            }
            
            return summary
            
        except Exception as e:
            error_msg = f"Error getting temperature summary: {e}"
            logger.error(error_msg)
            return {
                'total_emails': 0,
                'total_readings': 0,
                'locations': [],
                'alerts': [],
                'latest_reading': None,
                'discovered_locations': self.get_location_discovery_summary(),
                'sheets_logged': False,
                'sheets_message': "",
                'message': error_msg
            }
    
    def log_temperatures_to_sheets(self, temperature_readings, locations, custom_logged_time=None):
        """Log temperature readings to Google Sheets with optional custom logged time"""
        try:
            if not self.sheets_service:
                return False, "Sheets service not available"
            
            # Check if we have a spreadsheet configured
            if not self.sheets_service.spreadsheet_id:
                # Create a new spreadsheet with tabs for each location
                logger.info("No spreadsheet configured, creating new one...")
                spreadsheet, create_message = self.sheets_service.create_temperature_spreadsheet(locations)
                if not spreadsheet:
                    return False, f"Failed to create spreadsheet: {create_message}"
            
            # Log the temperature readings with custom time
            success, log_message = self.sheets_service.log_temperature_readings(
                temperature_readings, 
                staff_name=None,  # Will be filled by staff confirmation
                custom_logged_time=custom_logged_time
            )
            
            if success:
                spreadsheet_url = self.sheets_service.get_spreadsheet_url()
                time_note = f" at {custom_logged_time.strftime('%H:%M')}" if custom_logged_time else ""
                logger.info(f"Temperature data logged to sheets{time_note}: {spreadsheet_url}")
                return True, f"Logged to sheets{time_note}: {log_message}"
            else:
                return False, f"Failed to log to sheets: {log_message}"
            
        except Exception as e:
            error_msg = f"Error logging to sheets: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_sheets_url(self):
        """Get the Google Sheets URL if available"""
        if self.sheets_service:
            return self.sheets_service.get_spreadsheet_url()
        return None
    
    def add_staff_confirmation_to_sheets(self, location, staff_name, date_str=None):
        """Add staff confirmation to sheets for a specific location"""
        try:
            if not self.sheets_service:
                return False, "Sheets service not available"
            
            return self.sheets_service.add_staff_confirmation(location, staff_name, date_str)
            
        except Exception as e:
            error_msg = f"Error adding staff confirmation: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_location_discovery_summary(self):
        """Get summary of discovered locations"""
        if not self.location_manager:
            return {'total_discovered': 0, 'unconfigured': []}
        
        try:
            all_locations = self.location_manager.get_discovered_locations()
            unconfigured = self.location_manager.get_unconfigured_locations()
            
            return {
                'total_discovered': len(all_locations),
                'total_unconfigured': len(unconfigured),
                'unconfigured': unconfigured,
                'all_locations': all_locations
            }
        except Exception as e:
            logger.error(f"Error getting location discovery summary: {e}")
            return {'total_discovered': 0, 'unconfigured': []}
