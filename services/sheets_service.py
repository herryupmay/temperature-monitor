"""
Google Sheets Service for Temperature Monitor
Handles temperature logging with separate tabs per location
"""

import logging
from datetime import datetime, date
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class TemperatureSheetsService:
    """Service for logging temperature data to Google Sheets with separate tabs per location"""
    
    def __init__(self, auth_manager, spreadsheet_id=None, config_manager=None):
        """Initialize with authenticated Sheets service"""
        self.auth_manager = auth_manager
        self.config_manager = config_manager
        self.sheets_service = None
        self.spreadsheet_id = spreadsheet_id
        
        # Simplified headers for each location sheet
        self.headers = [
            "Date",
            "Day of Week", 
            "Min (°C)",
            "Max (°C)",
            "Logged Time",
            "Staff Name"
        ]
    
    def connect(self):
        """Connect to Google Sheets service"""
        try:
            if not self.auth_manager.is_authenticated():
                success, message = self.auth_manager.authenticate()
                if not success:
                    return False, message
            
            self.sheets_service = self.auth_manager.get_sheets_service()
            logger.info("Google Sheets service connected successfully")
            return True, "Google Sheets service connected"
            
        except Exception as e:
            error_msg = f"Error connecting Google Sheets service: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def validate_existing_spreadsheet(self):
        """Check if the current spreadsheet_id is valid and accessible"""
        try:
            if not self.spreadsheet_id:
                logger.info("No spreadsheet ID configured")
                return False, "No spreadsheet ID in settings"
            
            if not self.sheets_service:
                success, message = self.connect()
                if not success:
                    return False, f"Cannot connect to Google Sheets: {message}"
            
            # Try to access the spreadsheet metadata
            logger.info(f"Validating existing spreadsheet: {self.spreadsheet_id}")
            spreadsheet = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            title = spreadsheet.get('properties', {}).get('title', 'Unknown')
            sheet_count = len(spreadsheet.get('sheets', []))
            
            logger.info(f"✅ Found existing spreadsheet: '{title}' with {sheet_count} sheets")
            return True, f"Valid spreadsheet: {title}"
            
        except Exception as e:
            error_msg = str(e).lower()
            if 'not found' in error_msg or 'does not exist' in error_msg:
                logger.warning(f"Spreadsheet {self.spreadsheet_id} not found or deleted")
                return False, "Spreadsheet not found - may have been deleted"
            elif 'permission' in error_msg or 'access' in error_msg:
                logger.warning(f"No access to spreadsheet {self.spreadsheet_id}")
                return False, "No permission to access spreadsheet"
            else:
                logger.error(f"Error validating spreadsheet {self.spreadsheet_id}: {e}")
                return False, f"Validation error: {e}"

    def ensure_spreadsheet_exists(self, auto_discover_locations=True):
        """Ensure we have a valid spreadsheet - use existing or create new"""
        try:
            # First, try to validate existing spreadsheet
            if self.spreadsheet_id:
                valid, validation_message = self.validate_existing_spreadsheet()
                if valid:
                    logger.info(f"Using existing spreadsheet: {validation_message}")
                    return True, f"Using existing spreadsheet: {validation_message}"
                else:
                    logger.warning(f"Existing spreadsheet invalid: {validation_message}")
            
            # No valid spreadsheet - need to create one
            logger.info("Creating new spreadsheet...")
            
            # Auto-discover locations if possible
            locations = ["Main Location"]  # Default fallback
            
            if auto_discover_locations and hasattr(self, 'config_manager') and self.config_manager:
                try:
                    # Try to get recent emails to discover locations using the app's gmail service
                    if hasattr(self.config_manager, 'gmail_service') and self.config_manager.gmail_service:
                        logger.info("Attempting to auto-discover locations from recent emails...")
                        # Get temperature summary to discover locations
                        summary = self.config_manager.gmail_service.get_temperature_summary(
                            hours_back=168, auto_log_to_sheets=False  # Last week
                        )
                        
                        if summary.get('locations_found'):
                            locations = list(summary['locations_found'].keys())
                            logger.info(f"Auto-discovered locations: {locations}")
                        else:
                            logger.info("No locations discovered, using default")
                            
                except Exception as e:
                    logger.warning(f"Could not auto-discover locations: {e}")
            
            # Create new spreadsheet
            spreadsheet, create_message = self.create_temperature_spreadsheet(
                locations, "Temperature Monitor - Pharmacy"
            )
            
            if spreadsheet:
                logger.info(f"✅ New spreadsheet created: {self.spreadsheet_id}")
                return True, f"Created new spreadsheet with {len(locations)} locations"
            else:
                return False, f"Failed to create spreadsheet: {create_message}"
                
        except Exception as e:
            error_msg = f"Error ensuring spreadsheet exists: {e}"
            logger.error(error_msg)
            return False, error_msg

    def discover_and_configure_locations(self, temperature_readings):
        """Discover new locations from readings and create configs with smart defaults"""
        try:
            if not hasattr(self, 'config_manager') or not self.config_manager:
                return
            
            # Get current config
            temp_config = self.config_manager.config.get('temperature', {})
            global_default = temp_config.get('global_default', {
                'type': 'fridge', 'min_temp': 2.0, 'max_temp': 8.0, 'name': 'Default Monitor'
            })
            location_configs = temp_config.get('locations', {})
            
            # Track if we need to save config
            config_updated = False
            
            # Extract unique locations from readings
            discovered_locations = set()
            for reading in temperature_readings:
                location = reading.get('location', '').strip()
                if location:
                    discovered_locations.add(location)
            
            # Create configs for new locations with smart defaults
            for location in discovered_locations:
                if location not in location_configs:
                    # Smart default assignment based on location name
                    location_lower = location.lower()
                    
                    if any(keyword in location_lower for keyword in ['fridge', 'freezer', 'vaccine', 'insulin', 'cold']):
                        # Looks like a fridge/cold storage
                        new_config = {
                            'type': 'fridge',
                            'min_temp': 2.0,
                            'max_temp': 8.0,
                            'name': f'{location} (Fridge Monitor)'
                        }
                    elif any(keyword in location_lower for keyword in ['room', 'dispensary', 'storage', 'office', 'counter']):
                        # Looks like room temperature
                        new_config = {
                            'type': 'room', 
                            'min_temp': 0.0,
                            'max_temp': 25.0,
                            'name': f'{location} (Room Monitor)'
                        }
                    else:
                        # Unknown - use global default but let user know
                        new_config = global_default.copy()
                        new_config['name'] = f'{location} (Auto-detected)'
                    
                    # Add to config
                    location_configs[location] = new_config
                    config_updated = True
                    
                    logger.info(f"🔍 Auto-configured new location '{location}' as {new_config['type']} ({new_config['min_temp']}-{new_config['max_temp']}°C)")
            
            # Save updated config if we added any locations
            if config_updated:
                if 'temperature' not in self.config_manager.config:
                    self.config_manager.config['temperature'] = {}
                self.config_manager.config['temperature']['locations'] = location_configs
                self.config_manager.save_config()
                
                logger.info(f"✅ Updated config with {len([l for l in discovered_locations if l not in temp_config.get('locations', {})])} new locations")
        
        except Exception as e:
            logger.error(f"Error discovering and configuring locations: {e}")

    def create_temperature_spreadsheet(self, locations, title="Pharmacy Temperature Monitor"):
        """Create a new spreadsheet with separate tabs for each location"""
        try:
            if not self.sheets_service:
                success, message = self.connect()
                if not success:
                    return None, message
            
            # Create sheets for each location
            sheets = []
            for i, location in enumerate(locations):
                sheet_config = {
                    'properties': {
                        'title': location,
                        'sheetId': i,
                        'gridProperties': {
                            'rowCount': 1000,
                            'columnCount': len(self.headers)
                        }
                    }
                }
                sheets.append(sheet_config)
            
            # Create new spreadsheet with multiple sheets
            spreadsheet_body = {
                'properties': {
                    'title': title
                },
                'sheets': sheets
            }
            
            spreadsheet = self.sheets_service.spreadsheets().create(
                body=spreadsheet_body
            ).execute()
            
            self.spreadsheet_id = spreadsheet['spreadsheetId']
            logger.info(f"DEBUG: config_manager exists: {self.config_manager is not None}")
            logger.info(f"DEBUG: hasattr config_manager: {hasattr(self, 'config_manager')}")
            if self.config_manager:
                logger.info(f"DEBUG: config_manager type: {type(self.config_manager)}")
            else:
                logger.info("DEBUG: config_manager is None - this is the problem!")
            # Save to config
            if hasattr(self, 'config_manager') and self.config_manager:
                if 'sheets' not in self.config_manager.config:
                    self.config_manager.config['sheets'] = {}
                self.config_manager.config['sheets']['spreadsheet_id'] = self.spreadsheet_id
                self.config_manager.save_config()
                logger.info(f"Saved spreadsheet ID to config: {self.spreadsheet_id}")

            # Setup each location sheet
            for location in locations:
                self.setup_location_sheet(location)
            
            logger.info(f"Created temperature spreadsheet with {len(locations)} location tabs: {self.spreadsheet_id}")
            return spreadsheet, f"Created spreadsheet: {title} with {len(locations)} location tabs"
            
        except HttpError as e:
            error_msg = f"Error creating spreadsheet: {e}"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Error creating spreadsheet: {e}"
            logger.error(error_msg)
            return None, error_msg
    
    def setup_location_sheet(self, location_name):
        """Setup a single location sheet with location name at top and headers"""
        try:
            # Row 1: Location name (large, bold)
            location_range = f"{location_name}!A1:F1"
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=location_range,
                valueInputOption='RAW',
                body={'values': [[location_name, "", "", "", "", ""]]}
            ).execute()
            
            # Row 3: Headers (skip row 2 for spacing)
            header_range = f"{location_name}!A3:F3"
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=header_range,
                valueInputOption='RAW',
                body={'values': [self.headers]}
            ).execute()
            
            # Apply formatting
            self.format_location_sheet(location_name)
            
            logger.info(f"Setup sheet for location: {location_name}")
            
        except Exception as e:
            logger.error(f"Error setting up sheet for {location_name}: {e}")
    
    def format_location_sheet(self, location_name):
        """Apply formatting to a location sheet"""
        try:
            # Get sheet ID for this location
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            sheet_id = None
            for sheet in sheet_metadata['sheets']:
                if sheet['properties']['title'] == location_name:
                    sheet_id = sheet['properties']['sheetId']
                    break
            
            if sheet_id is None:
                logger.error(f"Could not find sheet ID for {location_name}")
                return
            
            requests = [
                # Freeze header rows (location name + headers)
                {
                    'updateSheetProperties': {
                        'properties': {
                            'sheetId': sheet_id,
                            'gridProperties': {
                                'frozenRowCount': 3
                            }
                        },
                        'fields': 'gridProperties.frozenRowCount'
                    }
                },
                # Format location name row (row 1) - large, bold, colored
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': {'red': 0.1, 'green': 0.4, 'blue': 0.8},
                                'textFormat': {
                                    'foregroundColor': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
                                    'bold': True,
                                    'fontSize': 16
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                    }
                },
                # Format header row (row 3) - bold, light blue
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 2,
                            'endRowIndex': 3
                        },
                        'cell': {
                            'userEnteredFormat': {
                                'backgroundColor': {'red': 0.8, 'green': 0.9, 'blue': 1.0},
                                'textFormat': {
                                    'bold': True
                                }
                            }
                        },
                        'fields': 'userEnteredFormat(backgroundColor,textFormat)'
                    }
                },
                # Auto-resize columns
                {
                    'autoResizeDimensions': {
                        'dimensions': {
                            'sheetId': sheet_id,
                            'dimension': 'COLUMNS',
                            'startIndex': 0,
                            'endIndex': len(self.headers)
                        }
                    }
                },
                # Merge cells for location name
                {
                    'mergeCells': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': 0,
                            'endRowIndex': 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': len(self.headers)
                        },
                        'mergeType': 'MERGE_ALL'
                    }
                }
            ]
            
            self.sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body={'requests': requests}
            ).execute()
            
            logger.info(f"Applied formatting to {location_name} sheet")
            
        except Exception as e:
            logger.error(f"Error formatting sheet for {location_name}: {e}")
    
    def log_temperature_readings(self, temperature_readings, staff_name=None, custom_logged_time=None):
        """Log temperature readings from Gmail parsing to appropriate location sheets"""
        try:
            if not self.sheets_service:
                success, message = self.connect()
                if not success:
                    return False, message
            
           
            spreadsheet_ready, spreadsheet_message = self.ensure_spreadsheet_exists()
            if not spreadsheet_ready:
                return False, f"Cannot prepare spreadsheet: {spreadsheet_message}"
            
            logger.info(f"Using spreadsheet for logging: {self.spreadsheet_id}")

            self.discover_and_configure_locations(temperature_readings)
            # Use custom logged time if provided, otherwise current time
            if custom_logged_time:
                logged_time = custom_logged_time.strftime("%H:%M")
            else:
                logged_time = datetime.now().strftime("%H:%M")
            
            results = []
            
            # Group readings by location
            readings_by_location = {}
            for reading in temperature_readings:
                location = reading['location']
                if location not in readings_by_location:
                    readings_by_location[location] = {'mins': [], 'maxs': []}
                
                if reading['type'] == 'minimum':
                    readings_by_location[location]['mins'].append(reading['value'])
                elif reading['type'] == 'maximum':
                    readings_by_location[location]['maxs'].append(reading['value'])
            
            # Log data for each location
            for location, temps in readings_by_location.items():
                if temps['mins'] and temps['maxs']:
                    min_temp = min(temps['mins'])
                    max_temp = max(temps['maxs'])
                    
                    success, message = self.log_location_temperature(
                        location, min_temp, max_temp, logged_time, staff_name
                    )
                    results.append((location, success, message))
            
            # Summarize results
            successful = [r for r in results if r[1]]
            failed = [r for r in results if not r[1]]
            
            if successful and not failed:
                success_msg = f"Logged temperatures for {len(successful)} locations: {', '.join([r[0] for r in successful])}"
                logger.info(success_msg)
                return True, success_msg
            elif successful and failed:
                mixed_msg = f"Partial success: {len(successful)} succeeded, {len(failed)} failed"
                logger.warning(mixed_msg)
                return True, mixed_msg
            else:
                error_msg = f"Failed to log temperatures for all {len(failed)} locations"
                logger.error(error_msg)
                return False, error_msg
            
        except Exception as e:
            error_msg = f"Error logging temperature readings: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def log_location_temperature(self, location, min_temp, max_temp, logged_time, staff_name=None):
        """Log temperature data for a specific location"""
        try:
            today = datetime.now()
            day_of_week = today.strftime("%A")
            date_str = today.strftime("%Y-%m-%d")
            
            # Prepare the data row
            row_data = [
                date_str,           # Date
                day_of_week,        # Day of Week
                f"{min_temp:.1f}",  # Min Temperature
                f"{max_temp:.1f}",  # Max Temperature
                logged_time,        # Logged Time
                staff_name or ""    # Staff Name (blank if not provided)
            ]
            
            # Check if entry for today already exists
            existing_row = self.find_todays_entry(location)
            
            if existing_row:
                # Update existing entry (preserve staff name if already filled)
                success, message = self.update_location_entry(location, existing_row, row_data, preserve_staff=True)
            else:
                # Add new entry
                success, message = self.add_location_entry(location, row_data)
            
            if success:
                logger.info(f"Temperature logged for {location}: {date_str} - Min {min_temp:.1f}°C, Max {max_temp:.1f}°C")
            
            return success, message
            
        except Exception as e:
            error_msg = f"Error logging temperature for {location}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def find_todays_entry(self, location):
        """Find if there's already an entry for today in the specified location sheet"""
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            
            # Get date column from the location sheet (starting from row 4, since rows 1-3 are headers)
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{location}!A4:A"  # Start from row 4 (after headers)
            ).execute()
            
            values = result.get('values', [])
            
            # Look for today's date
            for i, row in enumerate(values, start=4):  # Start from row 4
                if row and row[0] == today_str:
                    return i  # Return row number (1-indexed)
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding today's entry for {location}: {e}")
            return None
    
    def update_location_entry(self, location, row_number, row_data, preserve_staff=False):
        """Update an existing temperature entry for a location"""
        try:
            if preserve_staff:
                # Get existing staff name to preserve it if already filled
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{location}!F{row_number}:F{row_number}"  # Staff Name column
                ).execute()
                
                existing_staff = result.get('values', [])
                if existing_staff and existing_staff[0] and existing_staff[0][0].strip():
                    # Preserve existing staff name if it's already filled
                    row_data[5] = existing_staff[0][0]
            
            # Update the row
            range_name = f"{location}!A{row_number}:F{row_number}"
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='RAW',
                body={'values': [row_data]}
            ).execute()
            
            return True, f"Updated existing entry for {location} on {row_data[0]}"
            
        except Exception as e:
            error_msg = f"Error updating temperature entry for {location}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def add_location_entry(self, location, row_data):
        """Add a new temperature entry for a location"""
        try:
            # Append the new row (starting from row 4 since rows 1-3 are headers)
            self.sheets_service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{location}!A4:A",  # Start from row 4
                valueInputOption='RAW',
                insertDataOption='INSERT_ROWS',
                body={'values': [row_data]}
            ).execute()
            
            return True, f"Added new entry for {location} on {row_data[0]}"
            
        except Exception as e:
            error_msg = f"Error adding temperature entry for {location}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def add_staff_confirmation(self, location, staff_name, date_str=None):
        """Add staff confirmation to an existing temperature entry for a specific location"""
        try:
            if not staff_name or not staff_name.strip():
                return False, "Staff name is required"
            
            if date_str is None:
                date_str = datetime.now().strftime("%Y-%m-%d")
            
            # Find the entry for the specified date in the location sheet
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{location}!A4:A"  # Start from row 4
            ).execute()
            
            values = result.get('values', [])
            target_row = None
            
            # Look for the date
            for i, row in enumerate(values, start=4):  # Start from row 4
                if row and row[0] == date_str:
                    target_row = i
                    break
            
            if not target_row:
                return False, f"No temperature entry found for {location} on {date_str}"
            
            # Update logged time and staff name
            current_time = datetime.now().strftime("%H:%M")
            
            # Update logged time (column E) and staff name (column F)
            confirmation_range = f"{location}!E{target_row}:F{target_row}"
            
            self.sheets_service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=confirmation_range,
                valueInputOption='RAW',
                body={'values': [[current_time, staff_name.strip()]]}
            ).execute()
            
            logger.info(f"Staff confirmation added for {location}: {staff_name} on {date_str}")
            return True, f"Confirmation added for {location}: {staff_name} at {current_time}"
            
        except Exception as e:
            error_msg = f"Error adding staff confirmation for {location}: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_recent_entries(self, location, days=7):
        """Get recent temperature entries for a specific location"""
        try:
            if not self.sheets_service:
                success, message = self.connect()
                if not success:
                    return [], message
            
            # Get all data from the location sheet (starting from row 4)
            result = self.sheets_service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{location}!A4:F"  # Start from row 4, get all columns
            ).execute()
            
            values = result.get('values', [])
            
            if not values:
                return [], f"No data found in {location} sheet"
            
            # Convert to list of dictionaries
            entries = []
            for row in values:
                if len(row) >= len(self.headers):
                    entry = dict(zip(self.headers, row))
                    entry['Location'] = location  # Add location info
                    entries.append(entry)
            
            # Sort by date (most recent first) and limit to requested days
            entries.sort(key=lambda x: x.get('Date', ''), reverse=True)
            
            return entries[:days], f"Retrieved {len(entries[:days])} recent entries for {location}"
            
        except Exception as e:
            error_msg = f"Error getting recent entries for {location}: {e}"
            logger.error(error_msg)
            return [], error_msg
    
    def get_all_recent_entries(self, days=7):
        """Get recent entries from all location sheets"""
        try:
            # Get list of all sheets
            sheet_metadata = self.sheets_service.spreadsheets().get(
                spreadsheetId=self.spreadsheet_id
            ).execute()
            
            all_entries = []
            for sheet in sheet_metadata['sheets']:
                location = sheet['properties']['title']
                entries, message = self.get_recent_entries(location, days)
                all_entries.extend(entries)
            
            # Sort all entries by date
            all_entries.sort(key=lambda x: x.get('Date', ''), reverse=True)
            
            return all_entries[:days], f"Retrieved entries from all locations"
            
        except Exception as e:
            error_msg = f"Error getting all recent entries: {e}"
            logger.error(error_msg)
            return [], error_msg
    
    def get_spreadsheet_url(self):
        """Get the URL of the current spreadsheet"""
        if self.spreadsheet_id:
            return f"https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}/edit"
        return None
    
    def check_staff_confirmation_needed(self, location, require_staff_confirmation=True):
        """Check if staff confirmation is needed for today for a specific location"""
        try:
            if not require_staff_confirmation:
                return False, "Staff confirmation disabled in settings"
            
            # Check if someone already confirmed today for this location
            existing_entry = self.find_todays_entry(location)
            if existing_entry:
                # Get the existing data to check staff name
                result = self.sheets_service.spreadsheets().values().get(
                    spreadsheetId=self.spreadsheet_id,
                    range=f"{location}!F{existing_entry}:F{existing_entry}"  # Staff Name column
                ).execute()
                
                staff_values = result.get('values', [])
                if staff_values and staff_values[0] and staff_values[0][0].strip():
                    return False, f"Already confirmed by {staff_values[0][0]} for {location}"
            
            return True, f"Staff confirmation needed for {location}"
            
        except Exception as e:
            logger.error(f"Error checking staff confirmation for {location}: {e}")
            return True, "Unable to check - confirmation recommended"
