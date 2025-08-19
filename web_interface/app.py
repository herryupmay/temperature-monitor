"""
Flask web interface for Temperature Monitor
Provides the setup wizard and configuration interface with real Gmail integration
"""

from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import json
import logging
from datetime import datetime
import sys
from pathlib import Path
from services.temperature_scheduler import TemperatureScheduler
from services.sheets_service import TemperatureSheetsService

# Add the project root to path so we can import our modules
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.auth_manager import GmailAuthManager
from services.gmail_service import GmailTemperatureService

logger = logging.getLogger(__name__)

def create_app(desktop_app):
    """Create Flask app instance"""
    app = Flask(__name__)
    app.secret_key = 'temperature_monitor_secret_key_change_in_production'
    
    # Store reference to desktop app
    app.desktop_app = desktop_app
    
    # Initialize Gmail services
    app.auth_manager = desktop_app.auth_manager
    app.gmail_service = desktop_app.gmail_service
    # Initialize scheduler
    
    
    app.sheets_service = desktop_app.sheets_service

    def get_scheduler():
        """Get or create the scheduler instance - always use desktop app's instance"""
        if not hasattr(desktop_app, 'scheduler') or not desktop_app.scheduler:
            from services.temperature_scheduler import TemperatureScheduler
            desktop_app.scheduler = TemperatureScheduler(desktop_app, app.gmail_service, app.sheets_service)
        return desktop_app.scheduler
    
    # Set up announcement callback
    def announcement_callback(announcement_data):
        """Handle announcement results"""
        print("🔍 DEBUG: announcement_callback called")  # DEBUG
        scheduler = get_scheduler()
        formatted = scheduler.format_announcement_summary(announcement_data)
        print(f"🔍 DEBUG: formatted success = {formatted.get('success')}")  # DEBUG
        desktop_app.add_log_message(f"📢 {formatted['title']}: {formatted['message']}")
        
        # Create custom TTS message
        if formatted['success']:
            print("🔍 DEBUG: Creating custom message...")  # DEBUG
            custom_message = create_natural_announcement(announcement_data, desktop_app.config)
            print(f"🔍 DEBUG: Custom message = {custom_message[:50]}...")  # DEBUG
            print("🔍 DEBUG: Calling speak_alert...")  # DEBUG
            desktop_app.speak_alert(custom_message)
            print("🔍 DEBUG: speak_alert call completed")  # DEBUG
        else:
            print("🔍 DEBUG: Skipping voice - formatted success is False")  # DEBUG

    # Set callback on scheduler when it's accessed
    def ensure_callback_set():
        scheduler = get_scheduler()
        scheduler.set_announcement_callback(announcement_callback)
        return scheduler

    def create_natural_announcement(announcement_data, config):
        """Create natural language temperature announcement"""
        import datetime
        
        # Time-based greeting
        hour = datetime.datetime.now().hour
        if hour < 12:
            greeting = "Good morning"
        elif hour < 17:
            greeting = "Good afternoon"  
        else:
            greeting = "Good evening"
        
        summary = announcement_data.get('summary', {})
        all_readings = summary.get('all_readings', [])
        
        if not all_readings:
            return f"{greeting}. No temperature data found today. Please check your monitoring system."
        
        # Group readings by location
        locations = {}
        for reading in all_readings:
            location = reading['location']
            if location not in locations:
                locations[location] = {'mins': [], 'maxs': []}
            
            if reading['type'] == 'minimum':
                locations[location]['mins'].append(reading['value'])
            elif reading['type'] == 'maximum':
                locations[location]['maxs'].append(reading['value'])
        
        # Build announcement
        announcement_parts = [greeting + "."]
        
        breach_found = False
        
        # Get temperature config for per-location criteria
        temp_config = config.get('temperature', {})
        global_default = temp_config.get('global_default', {
            'type': 'fridge', 'min_temp': 2.0, 'max_temp': 8.0
        })
        location_configs = temp_config.get('locations', {})
        
        for location, temps in locations.items():
            if temps['mins'] and temps['maxs']:
                min_temp = min(temps['mins'])
                max_temp = max(temps['maxs'])
                
                # Get thresholds for this specific location
                location_config = location_configs.get(location, global_default)
                location_type = location_config.get('type', 'fridge')
                
                if location_type == 'fridge':
                    min_threshold, max_threshold = 2.0, 8.0
                elif location_type == 'room':
                    min_threshold, max_threshold = 0.0, 25.0
                else:  # custom
                    min_threshold = location_config.get('min_temp', 2.0)
                    max_threshold = location_config.get('max_temp', 8.0)
                
                # Check for breaches using location-specific thresholds
                location_breach = min_temp < min_threshold or max_temp > max_threshold
                if location_breach:
                    breach_found = True
                
                # Create location announcement
                location_msg = f"Today's {location} temperature is minimum {min_temp:.1f} degrees celsius, maximum {max_temp:.1f} degrees celsius."
                
                if location_breach:
                    location_msg += " Please check logger temperature and report to manager."
                else:
                    location_msg += " No breach found."
                
                announcement_parts.append(location_msg)
        
        # Closing message
        if not breach_found:
            announcement_parts.append("Have a nice day.")
        
        return " ".join(announcement_parts)

    

    @app.route('/')
    def index():
        """Main setup wizard page"""
        try:
            # Check real Gmail authentication status
            real_gmail_connected = app.auth_manager.is_authenticated()
            real_gmail_email = app.auth_manager.get_user_email() if real_gmail_connected else None
            
            # Debug logging
            logger.info(f"Web interface debug - Real Gmail connected: {real_gmail_connected}")
            logger.info(f"Web interface debug - Real Gmail email: {real_gmail_email}")
            logger.info(f"Web interface debug - Config Gmail connected: {desktop_app.config.get('gmail', {}).get('connected', False)}")
            
            # Create display config with real status
            display_config = desktop_app.config.copy()
            
            # Force update Gmail status with real-time data
            if real_gmail_connected and real_gmail_email:
                display_config['gmail'] = {
                    'connected': True,
                    'email': real_gmail_email
                }
                # Also update the desktop app config to keep them in sync
                desktop_app.config['gmail']['connected'] = True
                desktop_app.config['gmail']['email'] = real_gmail_email
                desktop_app.save_config()
                logger.info(f"Web interface - Forcing Gmail status to connected: {real_gmail_email}")
            else:
                display_config['gmail'] = {
                    'connected': False,
                    'email': ''
                }
                logger.info("Web interface - Gmail not connected")
            
            # Debug: Print what we're sending to template
            logger.info(f"Web interface - Final config being sent to template: gmail_connected={display_config['gmail']['connected']}, email={display_config['gmail']['email']}")
            
            return render_template_string(SETUP_WIZARD_TEMPLATE, config=display_config)
            
        except Exception as e:
            logger.error(f"Error in web interface index route: {e}")
            # Fallback to basic config
            return render_template_string(SETUP_WIZARD_TEMPLATE, config=desktop_app.config)
    
    @app.route('/api/gmail/connect', methods=['POST'])
    def connect_gmail():
        """Handle Gmail connection request - REAL OAuth flow"""
        try:
            desktop_app.add_log_message("Starting Gmail authentication...")
            
            # Check if credentials.json exists
            valid, message = app.auth_manager.check_credentials_file()
            if not valid:
                return jsonify({
                    'success': False, 
                    'error': 'Credentials file missing. Please place credentials.json in the config folder.',
                    'details': message
                })
            
            # Perform OAuth authentication
            success, auth_message = app.auth_manager.authenticate()
            
            if success:
                # Get user email
                user_email = app.auth_manager.get_user_email()
                
                # Update configuration
                desktop_app.config['gmail']['connected'] = True
                desktop_app.config['gmail']['email'] = user_email or 'Connected'
                desktop_app.save_config()
                
                # Test Gmail service
                gmail_success, gmail_message = app.gmail_service.connect()
                
                if gmail_success:
                    # Update GUI status
                    desktop_app.root.after(0, desktop_app.update_status_display)
                    desktop_app.add_log_message(f"Gmail connected successfully: {user_email}")
                    
                    return jsonify({
                        'success': True, 
                        'message': f'Gmail connected successfully: {user_email}',
                        'email': user_email
                    })
                else:
                    return jsonify({
                        'success': False,
                        'error': 'Gmail service connection failed',
                        'details': gmail_message
                    })
            else:
                return jsonify({
                    'success': False,
                    'error': 'Gmail authentication failed',
                    'details': auth_message
                })
            
        except Exception as e:
            logger.error(f"Error connecting Gmail: {e}")
            desktop_app.add_log_message(f"Gmail connection error: {str(e)}")
            return jsonify({
                'success': False, 
                'error': f'Gmail connection error: {str(e)}'
            })
    
    @app.route('/api/gmail/disconnect', methods=['POST'])
    def disconnect_gmail():
        """Disconnect Gmail and revoke authentication"""
        try:
            success, message = app.auth_manager.revoke_authentication()
            
            if success:
                # Update configuration
                desktop_app.config['gmail']['connected'] = False
                desktop_app.config['gmail']['email'] = ''
                desktop_app.save_config()
                
                # Update GUI status
                desktop_app.root.after(0, desktop_app.update_status_display)
                desktop_app.add_log_message("Gmail disconnected successfully")
                
                return jsonify({'success': True, 'message': 'Gmail disconnected successfully'})
            else:
                return jsonify({'success': False, 'error': message})
                
        except Exception as e:
            logger.error(f"Error disconnecting Gmail: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/gmail/test', methods=['POST'])
    def test_gmail():
        """Test Gmail connection and search for temperature emails"""
        try:
            if not app.auth_manager.is_authenticated():
                return jsonify({
                    'success': False, 
                    'error': 'Gmail not connected. Please connect first.'
                })
            
            desktop_app.add_log_message("Testing Gmail connection...")
            
            # Get recent temperature data
            summary = app.gmail_service.get_temperature_summary(hours_back=24)
            
            desktop_app.add_log_message(f"Gmail test: {summary['message']}")
            
            return jsonify({
                'success': True,
                'message': 'Gmail test completed',
                'summary': summary
            })
            
        except Exception as e:
            logger.error(f"Error testing Gmail: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/settings/save', methods=['POST'])
    def save_settings():
        """Save temperature and TTS settings"""
        try:
            data = request.get_json()
            
            # Update configuration
            if 'temperature' in data:
                temp_settings = data['temperature']
                desktop_app.config['temperature'].update(temp_settings)
            
            if 'tts' in data:
                tts_settings = data['tts']
                desktop_app.config['tts'].update(tts_settings)
                
                # Update TTS engine settings
                if desktop_app.tts_engine:
                    volume_map = {"low": 0.3, "medium": 0.7, "high": 1.0}
                    volume = volume_map.get(tts_settings.get('volume', 'medium'), 0.7)
                    desktop_app.tts_engine.setProperty('volume', volume)
            
            # Save configuration
            desktop_app.save_config()
            
            # Update GUI
            desktop_app.root.after(0, desktop_app.update_status_display)
            desktop_app.add_log_message("Settings saved successfully")
            
            return jsonify({'success': True, 'message': 'Settings saved successfully'})
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/test-alert', methods=['POST'])
    def test_alert():
        """Test voice alert"""
        try:
            desktop_app.test_voice_alert()
            return jsonify({'success': True, 'message': 'Test alert sent'})
        except Exception as e:
            logger.error(f"Error testing alert: {e}")
            return jsonify({'success': False, 'error': str(e)})
    
    @app.route('/api/status')
    def get_status():
        """Get current application status"""
        # Check real Gmail connection status
        gmail_connected = app.auth_manager.is_authenticated()
        user_email = app.auth_manager.get_user_email() if gmail_connected else None
        
        return jsonify({
            'gmail_connected': gmail_connected,
            'gmail_email': user_email,
            'monitoring_active': desktop_app.monitoring_active,
            'temperature_type': desktop_app.config['temperature'].get('global_default', {}).get('type', 'fridge'),
            'last_update': datetime.now().isoformat()
        })
    
    @app.route('/api/config')
    def get_config():
        """Get current configuration"""
        # Return config without sensitive data
        safe_config = desktop_app.config.copy()
        # Remove any sensitive credential data
        if 'credentials' in safe_config['gmail']:
            safe_config['gmail']['credentials'] = None
        return jsonify(safe_config)
    
    @app.route('/api/gmail/save-filters', methods=['POST'])
    def save_email_filters():
        """Save email filter configuration"""
        try:
            data = request.get_json()
            email_filters = data.get('email_filters', {})
            
            # Validate the filters
            if not email_filters.get('sender_addresses'):
                return jsonify({'success': False, 'error': 'At least one sender address is required'})
            
            if not email_filters.get('subject_keywords'):
                return jsonify({'success': False, 'error': 'At least one subject keyword is required'})
            
            # Update configuration
            if 'gmail' not in desktop_app.config:
                desktop_app.config['gmail'] = {}
            
            desktop_app.config['gmail']['email_filters'] = email_filters
            desktop_app.save_config()
            
            desktop_app.add_log_message("Email filters updated successfully")
            
            return jsonify({
                'success': True, 
                'message': 'Email filters saved successfully',
                'filters': email_filters
            })
            
        except Exception as e:
            logger.error(f"Error saving email filters: {e}")
            return jsonify({'success': False, 'error': str(e)})

    @app.route('/api/gmail/test-filters', methods=['POST'])
    def test_email_filters():
        """Test email filters to see what emails would be found"""
        try:
            if not app.auth_manager.is_authenticated():
                return jsonify({
                    'success': False, 
                    'error': 'Gmail not connected. Please connect first.'
                })
            
            desktop_app.add_log_message("Testing email filters...")
            
            # Get current filter configuration
            email_filters = desktop_app.config.get('gmail', {}).get('email_filters', {})
            
            if not email_filters:
                return jsonify({
                    'success': False,
                    'error': 'No email filters configured. Please save filters first.'
                })
            
            # Test the filters by searching for emails
            emails, message = app.gmail_service.search_temperature_emails(hours_back=168)  # Last week
            
            # Get sample subjects
            sample_subjects = []
            for email in emails[:5]:  # Show first 5 subjects
                sample_subjects.append(email.get('subject', 'No subject'))
            
            desktop_app.add_log_message(f"Filter test: {message}")
            
            return jsonify({
                'success': True,
                'message': 'Email filter test completed',
                'emails_found': len(emails),
                'sample_subjects': sample_subjects,
                'filters_used': email_filters
            })
            
        except Exception as e:
            logger.error(f"Error testing email filters: {e}")
            return jsonify({'success': False, 'error': str(e)})
        
    # Add these routes before the line: return app

    @app.route('/api/scheduler/status', methods=['GET'])
    def get_scheduler_status():
        """Get current scheduler status"""
        try:
            scheduler = ensure_callback_set()  # ✅ Changed
            status = scheduler.get_scheduler_status()
            
            logger.info(f"Scheduler status check: running={status.get('running')}, enabled={status.get('enabled')}")
            
            return jsonify({
                'success': True,
                'status': status
            })
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/settings', methods=['GET'])
    def get_scheduler_settings():
        """Get current scheduler settings"""
        try:
            scheduler = get_scheduler()  # ✅ Changed
            settings = scheduler.get_schedule_settings()
            return jsonify({
                'success': True,
                'settings': settings
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/settings', methods=['POST'])
    def update_scheduler_settings():
        """Update scheduler settings"""
        try:
            data = request.get_json()
            
            # Validate required fields
            if 'announce_time' in data:
                # Validate time format (HH:MM)
                try:
                    from datetime import datetime
                    datetime.strptime(data['announce_time'], '%H:%M')
                except ValueError:
                    return jsonify({
                        'success': False,
                        'error': 'Invalid time format. Use HH:MM (24-hour format)'
                    }), 400
            
            scheduler = get_scheduler()  # ✅ Changed
            success, message = scheduler.update_schedule_settings(data)
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/start', methods=['POST'])
    def start_scheduler():
        """Start the temperature scheduler"""
        try:
            scheduler = ensure_callback_set()  # ✅ Changed
            success, message = scheduler.start_scheduler()
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/stop', methods=['POST'])
    def stop_scheduler():
        """Stop the temperature scheduler"""
        try:
            scheduler = get_scheduler()  # ✅ Changed
            success, message = scheduler.stop_scheduler()
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/scheduler/test', methods=['POST'])
    def test_announcement():
        """Run a manual temperature announcement for testing"""
        try:
            scheduler = ensure_callback_set()  # ✅ Changed
            success, result = scheduler.run_manual_announcement()
            
            if success:
                formatted_result = scheduler.format_announcement_summary(result)
                return jsonify({
                    'success': True,
                    'announcement': formatted_result,
                    'raw_data': result
                })
            else:
                return jsonify({
                    'success': False,
                    'error': result.get('error', 'Unknown error'),
                    'timestamp': result.get('timestamp', datetime.now()).isoformat()
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        
    @app.route('/api/sheets/confirm', methods=['POST'])
    def add_staff_confirmation():
        """Add staff confirmation to sheets"""
        try:
            data = request.get_json()
            
            if not data or 'staff_name' not in data or 'location' not in data:
                return jsonify({
                    'success': False,
                    'error': 'staff_name and location are required'
                }), 400
            
            staff_name = data['staff_name'].strip()
            location = data['location'].strip()
            date_str = data.get('date_str')  # Optional, defaults to today
            
            if not staff_name:
                return jsonify({
                    'success': False,
                    'error': 'Staff name cannot be empty'
                }), 400
            
            success, message = app.gmail_service.add_staff_confirmation_to_sheets(
                location, staff_name, date_str
            )
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/sheets/url', methods=['GET'])
    def get_sheets_url():
        """Get the Google Sheets URL"""
        try:
            url = app.gmail_service.get_sheets_url()
            
            if url:
                return jsonify({
                    'success': True,
                    'url': url
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'No spreadsheet available. Run a temperature check first.'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


    @app.route('/api/auto-startup/status', methods=['GET'])
    def get_auto_startup_status():
        """Get current auto-startup status"""
        try:
            status = desktop_app.get_auto_startup_status()
            return jsonify({
                'success': True,
                'status': status
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/auto-startup/enable', methods=['POST'])
    def enable_auto_startup():
        """Enable Windows auto-startup"""
        try:
            success, message = desktop_app.enable_auto_startup()
            
            if success:
                desktop_app.add_log_message(f"✅ Auto-startup enabled: {message}")
            else:
                desktop_app.add_log_message(f"❌ Auto-startup failed: {message}")
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/auto-startup/disable', methods=['POST'])
    def disable_auto_startup():
        """Disable Windows auto-startup"""
        try:
            success, message = desktop_app.disable_auto_startup()
            
            if success:
                desktop_app.add_log_message(f"✅ Auto-startup disabled: {message}")
            else:
                desktop_app.add_log_message(f"❌ Auto-startup disable failed: {message}")
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/auto-startup/validate', methods=['POST'])
    def validate_auto_startup():
        """Validate auto-startup registry entry"""
        try:
            success, message = desktop_app.validate_startup_entry()
            
            if success:
                desktop_app.add_log_message(f"✅ Auto-startup validation: {message}")
            else:
                desktop_app.add_log_message(f"⚠️ Auto-startup validation: {message}")
            
            return jsonify({
                'success': success,
                'message': message
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500    
        
    @app.route('/api/locations/settings', methods=['GET'])
    def get_location_settings():
        """Get current per-location temperature settings"""
        try:
            temp_config = desktop_app.config.get('temperature', {})
            
            # Ensure we have the new structure
            global_default = temp_config.get('global_default', {
                'type': 'fridge',
                'min_temp': 2.0,
                'max_temp': 8.0,
                'name': 'Default Monitor'
            })
            
            locations = temp_config.get('locations', {})
            
            return jsonify({
                'success': True,
                'global_default': global_default,
                'locations': locations,
                'total_locations': len(locations)
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/locations/settings', methods=['POST'])
    def save_location_settings():
        """Save per-location temperature settings"""
        try:
            data = request.get_json()
            
            if not data:
                return jsonify({
                    'success': False,
                    'error': 'No data provided'
                }), 400
            
            global_default = data.get('global_default', {})
            locations = data.get('locations', {})
            
            # Validate the data
            required_fields = ['type', 'min_temp', 'max_temp']
            
            # Validate global default
            for field in required_fields:
                if field not in global_default:
                    return jsonify({
                        'success': False,
                        'error': f'Missing required field in global_default: {field}'
                    }), 400
            
            # Validate each location
            for location_name, location_config in locations.items():
                for field in required_fields:
                    if field not in location_config:
                        return jsonify({
                            'success': False,
                            'error': f'Missing required field in {location_name}: {field}'
                        }), 400
            
            # Update configuration
            if 'temperature' not in desktop_app.config:
                desktop_app.config['temperature'] = {}
            
            desktop_app.config['temperature']['global_default'] = global_default
            desktop_app.config['temperature']['locations'] = locations
            
            # Save configuration
            desktop_app.save_config()
            
            desktop_app.add_log_message(f"✅ Updated temperature settings for {len(locations)} locations")
            
            return jsonify({
                'success': True,
                'message': f'Saved settings for {len(locations)} locations',
                'locations_updated': list(locations.keys())
            })
            
        except Exception as e:
            logger.error(f"Error saving location settings: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route('/api/locations/discover', methods=['POST'])
    def discover_locations():
        """Discover new locations from recent emails"""
        try:
            if not app.auth_manager.is_authenticated():
                return jsonify({
                    'success': False,
                    'error': 'Gmail not connected. Please connect first.'
                }), 400
            
            desktop_app.add_log_message("🔍 Discovering locations from recent emails...")
            
            # Get recent temperature data to discover locations
            summary = app.gmail_service.get_temperature_summary(
                hours_back=168, auto_log_to_sheets=False  # Last week
            )
            
            if summary.get('total_readings', 0) == 0:
                return jsonify({
                    'success': False,
                    'error': 'No temperature data found in recent emails'
                })
            
            # Use the sheets service discovery method
            app.sheets_service.discover_and_configure_locations(summary.get('all_readings', []))
            
            # Get updated location list
            temp_config = desktop_app.config.get('temperature', {})
            locations = temp_config.get('locations', {})
            location_names = list(locations.keys())
            
            desktop_app.add_log_message(f"🔍 Discovered {len(location_names)} locations: {', '.join(location_names)}")
            
            return jsonify({
                'success': True,
                'message': f'Discovered {len(location_names)} locations',
                'locations_found': len(location_names),
                'location_names': location_names,
                'locations': locations
            })
            
        except Exception as e:
            logger.error(f"Error discovering locations: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
        
    return app

# HTML template for the setup wizard (completely clean)
SETUP_WIZARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Temperature Monitor Setup</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 800px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }

        .header h1 {
            font-size: 2rem;
            margin-bottom: 10px;
        }

        .header p {
            opacity: 0.9;
            font-size: 1.1rem;
        }

        .content {
            padding: 40px;
        }

        .setup-section {
            margin-bottom: 40px;
            padding: 25px;
            border: 2px solid #f0f0f0;
            border-radius: 15px;
            transition: border-color 0.3s ease;
        }

        .setup-section:hover {
            border-color: #4facfe;
        }

        .section-title {
            font-size: 1.3rem;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
        }

        .gmail-connect {
            display: flex;
            align-items: center;
            gap: 15px;
            margin-top: 15px;
            flex-wrap: wrap;
        }

        .btn {
            padding: 12px 24px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-flex;
            align-items: center;
            gap: 8px;
        }

        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }

        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
        }

        .btn-success {
            background: #28a745;
            color: white;
        }

        .btn-warning {
            background: #ffc107;
            color: #212529;
        }

        .btn-danger {
            background: #dc3545;
            color: white;
        }

        .btn:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none !important;
        }

        .status-connected {
            background: #d4edda;
            color: #155724;
            padding: 10px 15px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
            flex: 1;
        }

        .status-disconnected {
            background: #f8d7da;
            color: #721c24;
            padding: 10px 15px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .temp-options {
            display: grid;
            gap: 20px;
            margin-top: 20px;
        }

        .temp-option {
            padding: 20px;
            border: 2px solid #e9ecef;
            border-radius: 12px;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
        }

        .temp-option:hover {
            border-color: #4facfe;
            box-shadow: 0 4px 12px rgba(79, 172, 254, 0.15);
        }

        .temp-option.selected {
            border-color: #4facfe;
            background: #f8fbff;
        }

        .temp-option input[type="radio"] {
            position: absolute;
            opacity: 0;
        }

        .option-header {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }

        .option-title {
            font-weight: 600;
            font-size: 1.1rem;
            color: #333;
        }

        .option-description {
            color: #666;
            margin-bottom: 10px;
        }

        .temp-range {
            background: #f8f9fa;
            padding: 8px 12px;
            border-radius: 6px;
            font-family: monospace;
            font-weight: 500;
            color: #495057;
        }

        .custom-inputs {
            display: none;
            margin-top: 15px;
            gap: 15px;
        }

        .custom-inputs.active {
            display: flex;
        }

        .input-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }

        .input-group label {
            font-weight: 500;
            color: #333;
            font-size: 0.9rem;
        }

        .input-group input,
        .input-group select {
            padding: 10px;
            border: 2px solid #e9ecef;
            border-radius: 6px;
            font-size: 1rem;
            transition: border-color 0.3s ease;
        }

        .input-group input:focus,
        .input-group select:focus {
            outline: none;
            border-color: #4facfe;
        }

        .tts-settings {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-top: 20px;
        }

        .save-section {
            text-align: center;
            padding-top: 20px;
            border-top: 2px solid #f0f0f0;
            margin-top: 40px;
        }

        .status-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 8px;
        }

        .status-connected .status-indicator {
            background: #28a745;
        }

        .status-disconnected .status-indicator {
            background: #dc3545;
        }

        .alert {
            padding: 15px;
            border-radius: 8px;
            margin: 15px 0;
        }

        .alert-success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }

        .alert-error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }

        .alert-info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }

        .test-results {
            margin-top: 15px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
            border-left: 4px solid #4facfe;
        }

        .test-results h4 {
            margin-bottom: 10px;
            color: #333;
        }

        .test-results ul {
            margin: 0;
            padding-left: 20px;
        }

        @media (max-width: 768px) {
            .tts-settings {
                grid-template-columns: 1fr;
            }
            
            .custom-inputs {
                flex-direction: column;
            }

            .gmail-connect {
                flex-direction: column;
                align-items: stretch;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Temperature Monitor</h1>
            <p>Set up automated temperature alerts with voice announcements</p>
        </div>

        <div class="content">
            <div id="alert-container"></div>

            <!-- Gmail Integration Section -->
            <div class="setup-section">
                <div class="section-title">Gmail Integration</div>
                <p>Connect your Gmail account to receive temperature data from your monitoring devices.</p>
                
                <div class="gmail-connect" id="gmail-section">
                    {% if config.gmail.connected %}
                    <div class="status-connected">
                        <span class="status-indicator"></span>
                        <span>Gmail connected: {{ config.gmail.email }}</span>
                    </div>
                    <button class="btn btn-warning" onclick="testGmail()">Test Gmail Connection</button>
                    <button class="btn btn-danger" onclick="disconnectGmail()">Disconnect</button>
                    {% else %}
                    <div class="status-disconnected">
                        <span class="status-indicator"></span>
                        <span>Gmail not connected</span>
                    </div>
                    <button class="btn btn-primary" id="gmail-connect-btn" onclick="connectGmail()">Connect Gmail Account</button>
                    {% endif %}
                </div>

                <div id="test-results-container"></div>
            </div>

            <!-- Email Filter Section -->
            <div class="setup-section" id="email-filter-section" {% if not config.gmail.connected %}style="display: none;"{% endif %}>
                <div class="section-title">Email Filter Settings</div>
                <p>Configure which emails to monitor for temperature reports.</p>
                
                <div class="filter-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    
                    <!-- Sender Addresses -->
                    <div class="input-group">
                        <label for="sender-addresses">Sender Email Addresses</label>
                        <textarea id="sender-addresses" rows="3" placeholder="notifications@cleverlogger.com&#10;alerts@sensaphone.net&#10;reports@temptracker.com" style="padding: 10px; border: 2px solid #e9ecef; border-radius: 6px; font-size: 1rem; resize: vertical;">{% for sender in config.gmail.get('email_filters', {}).get('sender_addresses', ['notifications@cleverlogger.com']) %}{{ sender }}{% if not loop.last %}&#10;{% endif %}{% endfor %}</textarea>
                        <small style="color: #666;">One email address per line</small>
                    </div>
                    
                    <!-- Subject Keywords -->
                    <div class="input-group">
                        <label for="subject-keywords">Required Subject Keywords</label>
                        <textarea id="subject-keywords" rows="3" placeholder="min-max&#10;temperature report&#10;daily summary" style="padding: 10px; border: 2px solid #e9ecef; border-radius: 6px; font-size: 1rem; resize: vertical;">{% for keyword in config.gmail.get('email_filters', {}).get('subject_keywords', ['min-max', 'temperature report']) %}{{ keyword }}{% if not loop.last %}&#10;{% endif %}{% endfor %}</textarea>
                        <small style="color: #666;">Email must contain at least one of these</small>
                    </div>
                    
                </div>
                
                <div class="filter-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    
                    <!-- Exclude Keywords -->
                    <div class="input-group">
                        <label for="exclude-keywords">Exclude Keywords</label>
                        <textarea id="exclude-keywords" rows="2" placeholder="test&#10;configuration&#10;welcome" style="padding: 10px; border: 2px solid #e9ecef; border-radius: 6px; font-size: 1rem; resize: vertical;">{% for keyword in config.gmail.get('email_filters', {}).get('exclude_keywords', ['test', 'configuration']) %}{{ keyword }}{% if not loop.last %}&#10;{% endif %}{% endfor %}</textarea>
                        <small style="color: #666;">Skip emails containing these words</small>
                    </div>
                    
                    <!-- Options -->
                    <div class="input-group">
                        <label>Options</label>
                        <div style="display: flex; flex-direction: column; gap: 8px; margin-top: 8px;">
                            <label style="display: flex; align-items: center; gap: 8px; font-weight: normal;">
                                <input type="checkbox" id="require-pdf" {% if config.gmail.get('email_filters', {}).get('require_pdf', True) %}checked{% endif %}>
                                Require PDF attachment
                            </label>
                            <label style="display: flex; align-items: center; gap: 8px; font-weight: normal;">
                                <input type="checkbox" id="auto-update" checked>
                                Auto-update when new emails arrive
                            </label>
                        </div>
                    </div>
                    
                </div>
                
                <div style="text-align: center; margin-top: 20px;">
                    <button class="btn btn-primary" onclick="saveEmailFilters()">Save Email Filters</button>
                    <button class="btn btn-success" onclick="testEmailFilters()" style="margin-left: 10px;">Test Filters</button>
                </div>
            </div>

            <!-- Per-Location Temperature Settings -->
            <div class="setup-section">
                <div class="section-title">📍 Temperature Settings by Location</div>
                <p>Configure temperature monitoring criteria for each discovered location.</p>
                
                <!-- Global Default Settings -->
                <div style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                    <h4 style="margin-bottom: 15px; color: #333;">🌐 Default Settings for New Locations</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 15px;">
                        <div class="input-group">
                            <label>Default Type</label>
                            <select id="global-default-type">
                                <option value="fridge" {% if config.temperature.global_default.type == 'fridge' %}selected{% endif %}>Fridge (2-8°C)</option>
                                <option value="room" {% if config.temperature.global_default.type == 'room' %}selected{% endif %}>Room (0-25°C)</option>
                                <option value="custom" {% if config.temperature.global_default.type == 'custom' %}selected{% endif %}>Custom Range</option>
                            </select>
                        </div>
                        <div class="input-group">
                            <label>Min Temp (°C)</label>
                            <input type="number" id="global-default-min" step="0.1" value="{{ config.temperature.global_default.min_temp }}">
                        </div>
                        <div class="input-group">
                            <label>Max Temp (°C)</label>
                            <input type="number" id="global-default-max" step="0.1" value="{{ config.temperature.global_default.max_temp }}">
                        </div>
                    </div>
                </div>
                
                <!-- Location-Specific Settings -->
                <div id="location-settings">
                    <h4 style="margin-bottom: 15px; color: #333;">📍 Individual Location Settings</h4>
                    <div id="location-list">
                        <!-- Will be populated by JavaScript -->
                        <div style="text-align: center; color: #666; padding: 20px;">
                            Loading location settings...
                        </div>
                    </div>
                </div>
                
                <div style="text-align: center; margin-top: 20px;">
                    <button class="btn btn-primary" onclick="saveLocationSettings()">💾 Save Location Settings</button>
                    <button class="btn btn-success" onclick="refreshLocations()" style="margin-left: 10px;">🔄 Refresh Locations</button>
                </div>
            </div>

    

           <!-- Temperature Scheduler Section -->
            <div class="setup-section" id="scheduler-section">
                <div class="section-title">📅 Temperature Scheduler</div>
                <p>Configure automated daily temperature announcements and Google Sheets logging.</p>
                
                <!-- Scheduler Status -->
                <div id="scheduler-status" style="background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; font-family: monospace; font-size: 0.9rem;">
                    Loading scheduler status...
                </div>
                
                <!-- Scheduler Settings -->
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px;">
                    <div class="input-group">
                        <label for="announce-time">Daily Announce Time</label>
                        <input type="time" id="announce-time" value="09:00">
                        <small style="color: #666;">24-hour format (e.g., 09:00 for 9:00 AM)</small>
                    </div>
                    
                    <div class="input-group">
                        <label for="search-hours">Search Hours Back</label>
                        <input type="number" id="search-hours" value="24" min="1" max="168">
                        <small style="color: #666;">How many hours back to search for emails</small>
                    </div>
                    
                    <div class="input-group">
                        <label>
                            <input type="checkbox" id="scheduler-enabled"> Enable Daily Scheduler
                        </label>
                        <small style="color: #666;">Automatically run daily temperature checks</small>
                    </div>
                    
                    <div class="input-group">
                        <label>
                            <input type="checkbox" id="auto-log-sheets" checked> Auto-log to Google Sheets
                        </label>
                        <small style="color: #666;">Automatically create/update spreadsheet</small>
                    </div>
                    
                    <div class="input-group">
                        <label>
                            <input type="checkbox" id="require-staff-confirmation" checked> Require Staff Confirmation
                        </label>
                        <small style="color: #666;">Staff must confirm temperature checks</small>
                    </div>
                </div>
                
                <!-- Scheduler Controls -->
                <div style="text-align: center; margin-bottom: 20px;">
                    <button class="btn btn-success" onclick="saveSchedulerSettings()">💾 Save Scheduler Settings</button>
                    <button class="btn btn-primary" onclick="startScheduler()" style="margin-left: 10px;">▶️ Start Scheduler</button>
                    <button class="btn btn-warning" onclick="stopScheduler()" style="margin-left: 10px;">⏸️ Stop Scheduler</button>
                </div>
                
                <!-- Test Controls -->
                <div style="text-align: center; margin-bottom: 20px; padding-top: 15px; border-top: 1px solid #eee;">
                    <button class="btn btn-warning" id="test-announcement-btn" onclick="testAnnouncement()">🧪 Test Manual Announcement</button>
                    <button class="btn btn-success" onclick="openGoogleSheets()" style="margin-left: 10px;">📊 Open Google Sheets</button>
                    
                </div>
                
                <!-- Test Results -->
                <div id="test-results" style="display: none; background: #f8f9fa; padding: 15px; border-radius: 8px; margin-top: 15px;">
                    Test results will appear here...
                </div>
            </div>

            <!-- Windows Auto-Startup Section -->
            <div class="setup-section" id="auto-startup-section">
                <div class="section-title"> Windows Auto-Startup</div>
                <p>Start Temperature Monitor automatically when Windows boots.</p>
                
                <div style="display: flex; align-items: center; gap: 20px; margin: 20px 0;">
                    <label style="display: flex; align-items: center; gap: 8px; font-weight: normal;">
                        <input type="checkbox" id="auto-startup-enabled"> 
                        Enable Auto-Startup with Windows
                    </label>
                    
                    <span id="auto-startup-status" style="padding: 5px 10px; border-radius: 5px; font-size: 0.9rem;">
                        Loading...
                    </span>
                </div>
                
                <div style="text-align: center;">
                    <button class="btn btn-primary" onclick="toggleAutoStartup()">💾 Save Auto-Startup Setting</button>
                </div>
            </div>

            

            <!-- Save Section -->
            <div class="save-section">
                <button class="btn btn-success" onclick="saveSettings()">Save Configuration & Start Monitoring</button>
                <button class="btn btn-primary" onclick="testAlert()" style="margin-left: 10px;">Test Voice Alert</button>
            </div>
        </div>
    </div>

    <script src="/static/app.js"></script>
</body>
</html>
'''