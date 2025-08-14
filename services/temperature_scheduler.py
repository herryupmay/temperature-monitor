"""
Temperature Scheduler Service
Handles scheduled temperature announcements and logging
"""

import logging
import schedule
import time
import threading
from datetime import datetime, timedelta
from typing import Optional, Callable

logger = logging.getLogger(__name__)

class TemperatureScheduler:
    """Service for scheduling temperature announcements"""
    
    def __init__(self, config_manager, gmail_service, sheets_service=None):
        """Initialize the scheduler"""
        self.config_manager = config_manager
        self.gmail_service = gmail_service
        self.sheets_service = sheets_service
        self.is_running = False
        self.scheduler_thread = None
        self.announcement_callback = None
        
        # Default settings
        self.default_settings = {
            'announce_time': '09:00',  # 24-hour format
            'enabled': False,
            'search_hours_back': 24,
            'auto_log_to_sheets': True,
            'require_staff_confirmation': True
        }
    
    def get_schedule_settings(self):
        """Get current schedule settings"""
        try:
            config = self.config_manager.config.get('scheduler', {})
            settings = self.default_settings.copy()
            settings.update(config)
            return settings
        except Exception as e:
            logger.error(f"Error getting schedule settings: {e}")
            return self.default_settings.copy()
    
    def update_schedule_settings(self, settings):
        """Update schedule settings"""
        try:
            if 'scheduler' not in self.config_manager.config:
                self.config_manager.config['scheduler'] = {}
            
            self.config_manager.config['scheduler'].update(settings)
            self.config_manager.save_config()
            
            # Restart scheduler if running
            if self.is_running:
                self.stop_scheduler()
                self.start_scheduler()
            
            logger.info(f"Schedule settings updated: {settings}")
            return True, "Settings updated successfully"
            
        except Exception as e:
            error_msg = f"Error updating schedule settings: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def set_announcement_callback(self, callback: Callable):
        """Set callback function to call when announcement is triggered"""
        self.announcement_callback = callback
    
    def start_scheduler(self):
        """Start the temperature announcement scheduler"""
        try:
            settings = self.get_schedule_settings()
            
            if not settings['enabled']:
                return False, "Scheduler is disabled in settings"
            
            if self.is_running:
                return False, "Scheduler is already running"
            
            # Clear any existing scheduled jobs
            schedule.clear()
            
            # Schedule the daily announcement
            announce_time = settings['announce_time']
            schedule.every().day.at(announce_time).do(self._run_daily_announcement)
            
            # Start the scheduler thread
            self.is_running = True
            self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
            self.scheduler_thread.start()
            
            logger.info(f"Temperature scheduler started - daily announcements at {announce_time}")
            return True, f"Scheduler started - daily announcements at {announce_time}"
            
        except Exception as e:
            error_msg = f"Error starting scheduler: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def stop_scheduler(self):
        """Stop the temperature announcement scheduler"""
        try:
            if not self.is_running:
                return False, "Scheduler is not running"
            
            self.is_running = False
            schedule.clear()
            
            # Wait for thread to finish
            if self.scheduler_thread and self.scheduler_thread.is_alive():
                self.scheduler_thread.join(timeout=5)
            
            logger.info("Temperature scheduler stopped")
            return True, "Scheduler stopped successfully"
            
        except Exception as e:
            error_msg = f"Error stopping scheduler: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def _scheduler_loop(self):
        """Main scheduler loop"""
        while self.is_running:
            try:
                schedule.run_pending()
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in scheduler loop: {e}")
                time.sleep(60)
    
    def _run_daily_announcement(self):
        """Run the daily temperature announcement"""
        try:
            settings = self.get_schedule_settings()
            announce_time = datetime.now().replace(second=0, microsecond=0)  # Current announcement time
            
            logger.info(f"Running daily temperature announcement at {announce_time.strftime('%H:%M')}...")
            
            # Search emails from past 24 hours
            hours_back = settings['search_hours_back']
            summary = self.gmail_service.get_temperature_summary(
                hours_back=hours_back,
                auto_log_to_sheets=settings['auto_log_to_sheets'],
                custom_logged_time=announce_time  # Use announce time as logged time
            )
            
            # Prepare announcement data
            announcement_data = {
                'timestamp': announce_time,
                'summary': summary,
                'settings': settings,
                'announcement_type': 'scheduled'
            }
            
            # Call the announcement callback if set
            if self.announcement_callback:
                self.announcement_callback(announcement_data)
            
            # Log the announcement
            self._log_announcement_result(announcement_data)
            
        except Exception as e:
            error_msg = f"Error running daily announcement: {e}"
            logger.error(error_msg)
            
            # Still call callback with error info
            if self.announcement_callback:
                error_data = {
                    'timestamp': datetime.now(),
                    'error': error_msg,
                    'announcement_type': 'scheduled_error'
                }
                self.announcement_callback(error_data)
    
    def _log_announcement_result(self, announcement_data):
        """Log the results of an announcement"""
        try:
            summary = announcement_data['summary']
            timestamp = announcement_data['timestamp']
            
            if summary['total_emails'] > 0:
                logger.info(
                    f"Daily announcement completed at {timestamp.strftime('%H:%M')}: "
                    f"{summary['total_emails']} emails, {summary['total_readings']} readings, "
                    f"locations: {', '.join(summary['locations'])}"
                )
                
                if summary.get('sheets_logged'):
                    logger.info(f"Data logged to sheets: {summary.get('sheets_message', '')}")
            else:
                logger.info(f"Daily announcement at {timestamp.strftime('%H:%M')}: No new temperature data found")
            
        except Exception as e:
            logger.error(f"Error logging announcement result: {e}")
    
    def run_manual_announcement(self):
        """Run a manual temperature announcement (for testing)"""
        try:
            settings = self.get_schedule_settings()
            manual_time = datetime.now().replace(second=0, microsecond=0)  # Current time for manual run
            
            logger.info(f"Running manual temperature announcement at {manual_time.strftime('%H:%M')}...")
            
            # Search emails from past 24 hours
            hours_back = settings['search_hours_back']
            summary = self.gmail_service.get_temperature_summary(
                hours_back=hours_back,
                auto_log_to_sheets=settings['auto_log_to_sheets'],
                custom_logged_time=manual_time  # Use current time as logged time for manual runs
            )
            
            # Prepare announcement data
            announcement_data = {
                'timestamp': manual_time,
                'summary': summary,
                'settings': settings,
                'announcement_type': 'manual'
            }
            
            # Call the announcement callback if set
            if self.announcement_callback:
                self.announcement_callback(announcement_data)
            
            # Log the announcement
            self._log_announcement_result(announcement_data)
            
            return True, announcement_data
            
        except Exception as e:
            error_msg = f"Error running manual announcement: {e}"
            logger.error(error_msg)
            return False, {'error': error_msg, 'timestamp': datetime.now()}
    
    def get_next_announcement_time(self):
        """Get the time of the next scheduled announcement"""
        try:
            if not self.is_running:
                return None, "Scheduler is not running"
            
            jobs = schedule.get_jobs()
            if not jobs:
                return None, "No scheduled jobs found"
            
            next_run = min(job.next_run for job in jobs)
            return next_run, f"Next announcement: {next_run.strftime('%Y-%m-%d %H:%M')}"
            
        except Exception as e:
            logger.error(f"Error getting next announcement time: {e}")
            return None, f"Error: {e}"
    
    def get_scheduler_status(self):
        """Get current status of the scheduler"""
        try:
            settings = self.get_schedule_settings()
            next_run, next_message = self.get_next_announcement_time()
            
            status = {
                'enabled': settings['enabled'],
                'running': self.is_running,
                'announce_time': settings['announce_time'],
                'search_hours_back': settings['search_hours_back'],
                'auto_log_to_sheets': settings['auto_log_to_sheets'],
                'require_staff_confirmation': settings['require_staff_confirmation'],
                'next_run': next_run,
                'next_run_message': next_message,
                'jobs_count': len(schedule.get_jobs()) if self.is_running else 0
            }
            
            return status
            
        except Exception as e:
            logger.error(f"Error getting scheduler status: {e}")
            return {
                'enabled': False,
                'running': False,
                'error': str(e)
            }
    
    def format_announcement_summary(self, announcement_data):
        """Format announcement data for display"""
        try:
            summary = announcement_data.get('summary', {})
            timestamp = announcement_data.get('timestamp', datetime.now())
            announcement_type = announcement_data.get('announcement_type', 'unknown')
            
            if 'error' in announcement_data:
                return {
                    'title': f"Temperature Announcement Error ({announcement_type})",
                    'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                    'message': f"Error: {announcement_data['error']}",
                    'success': False
                }
            
            # Format successful announcement
            if summary.get('total_emails', 0) > 0:
                locations_text = ", ".join(summary.get('locations', []))
                latest = summary.get('latest_reading')
                latest_text = f" Latest: {latest['value']}°C at {latest['location']}" if latest else ""
                
                message = (
                    f"Found {summary['total_emails']} email(s) with {summary['total_readings']} temperature readings. "
                    f"Locations: {locations_text}.{latest_text}"
                )
                
                if summary.get('sheets_logged'):
                    message += f" ✅ Logged to Google Sheets."
                else:
                    message += " ⚠️ Not logged to sheets."
            else:
                message = "No new temperature data found in the past 24 hours."
            
            return {
                'title': f"Temperature Announcement ({announcement_type})",
                'time': timestamp.strftime('%Y-%m-%d %H:%M'),
                'message': message,
                'success': summary.get('total_emails', 0) > 0,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error formatting announcement summary: {e}")
            return {
                'title': "Temperature Announcement",
                'time': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'message': f"Error formatting summary: {e}",
                'success': False
            }
