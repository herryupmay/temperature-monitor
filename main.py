#!/usr/bin/env python3
"""
Temperature Monitor Desktop Application
Main entry point for the desktop app with system tray and embedded web server
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import sys
import os
import json
import time
import webbrowser
from pathlib import Path
import pystray
from PIL import Image, ImageDraw
import pyttsx3
from datetime import datetime, timedelta
import queue
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

import platform
import subprocess

if platform.system() == "Windows":
    try:
        import winreg
    except ImportError:
        winreg = None
        logger.warning("winreg module not available - auto-startup will be disabled")

class ConnectionMonitor:
    """Monitor internet and Gmail connectivity with auto-recovery"""
    
    def __init__(self, desktop_app):
        self.desktop_app = desktop_app
        self.is_online = True
        self.last_internet_check = None
        self.last_gmail_check = None
        self.retry_count = 0
        self.max_retries = 5
        
        logger.info("ConnectionMonitor initialized")
    
    def check_internet_connectivity(self):
        """Check if internet is available by testing Google"""
        try:
            import urllib.request
            urllib.request.urlopen('https://www.google.com', timeout=5)
            self.last_internet_check = datetime.now()
            return True
        except Exception as e:
            logger.debug(f"Internet check failed: {e}")
            return False
    
    def check_gmail_connectivity(self):
        """Check if Gmail API is reachable and authenticated"""
        try:
            if hasattr(self.desktop_app, 'auth_manager') and self.desktop_app.auth_manager:
                is_auth = self.desktop_app.auth_manager.is_authenticated()
                self.last_gmail_check = datetime.now()
                return is_auth
            return False
        except Exception as e:
            logger.debug(f"Gmail check failed: {e}")
            return False
    
    def get_connectivity_status(self):
        """Get current connectivity status summary"""
        internet_ok = self.check_internet_connectivity()
        gmail_ok = self.check_gmail_connectivity() if internet_ok else False
        
        return {
            'internet': internet_ok,
            'gmail': gmail_ok,
            'last_internet_check': self.last_internet_check,
            'last_gmail_check': self.last_gmail_check,
            'retry_count': self.retry_count
        }

class TemperatureMonitorApp:
    def __init__(self):
        self.monitoring_active = False
        self.setup_paths()
        self.load_config()
        self.setup_tts()
        self.setup_gui()
        self.setup_system_tray()
        self.alert_queue = queue.Queue()
        self.running = True
        self.web_server = None
        self.connection_monitor = None 
        
        
        # Start background services
        self.start_services()
    
    def setup_paths(self):
        """Setup application paths for both script and bundled exe"""
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            self.app_path = Path(sys.executable).parent
        else:
            # Running as script
            self.app_path = Path(__file__).parent
        
        self.config_path = self.app_path / "config"
        self.web_path = self.app_path / "web_interface"
        
        # Create directories if they don't exist
        self.config_path.mkdir(exist_ok=True)
        self.web_path.mkdir(exist_ok=True)
        
        logger.info(f"App path: {self.app_path}")
        logger.info(f"Config path: {self.config_path}")
    
    def load_config(self):
        """Load configuration from JSON file"""
        config_file = self.config_path / "settings.json"
        self.default_config = {
            "gmail": {
                "connected": False,
                "email": "",
                "credentials": None,
                "email_filters": {
                    "sender_addresses": ["notifications@cleverlogger.com"],
                    "subject_keywords": ["min-max", "temperature report"],
                    "require_pdf": True,
                    "exclude_keywords": ["test", "configuration"]
                }
            },
            "temperature": {
                "global_default": {
                    "type": "fridge",
                    "min_temp": 2,
                    "max_temp": 8,
                    "name": "Default Monitor"
                },
                "locations": {
                    # This starts empty and gets populated automatically
                    # as locations are discovered from emails
                    # e.g. "Main Fridge": {"type": "fridge", "min_temp": 2, "max_temp": 8}
                }
            },
            "tts": {
                "enabled": True,
                "interval": "immediate",
                "volume": "medium",
                "quiet_hours_start": "22:00",
                "quiet_hours_end": "07:00"
            },
            "sheets": {
                 "spreadsheet_id": None
            },
            "web_server": {
                "port": 8080,
                "host": "localhost"
            },
              "auto_startup": {
                "enabled": True,
                "app_name": "Temperature Monitor",
                "validated": False
            },
            "scheduler": {
                "announce_time": "09:00",
                "enabled": True,
                "search_hours_back": 24,
                "auto_log_to_sheets": True,
                "require_staff_confirmation": True
            }
        }
        
        try:
            if config_file.exists():
                with open(config_file, 'r') as f:
                    self.config = json.load(f)
                logger.info("Configuration loaded successfully")
            else:
                self.config = self.default_config.copy()
                self.save_config()
                logger.info("Created default configuration")
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            self.config = self.default_config.copy()
    
    def save_config(self):
        """Save configuration to JSON file"""
        config_file = self.config_path / "settings.json"
        try:
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
    
    def setup_tts(self):
        """Initialize TTS engine"""
        try:
            self.tts_engine = pyttsx3.init()
            
            # Configure TTS settings
            voices = self.tts_engine.getProperty('voices')
            if voices:
                self.tts_engine.setProperty('voice', voices[0].id)
            
            # Set volume based on config
            volume_map = {"low": 0.3, "medium": 0.7, "high": 1.0}
            volume = volume_map.get(self.config["tts"]["volume"], 0.7)
            self.tts_engine.setProperty('volume', volume)
            
            # Set speech rate
            self.tts_engine.setProperty('rate', 150)
            
            logger.info("TTS engine initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing TTS: {e}")
            self.tts_engine = None
    
    def setup_gui(self):
        """Setup main GUI window"""
        self.root = tk.Tk()
        self.root.title("Temperature Monitor")
        self.root.geometry("500x400")
        self.root.protocol("WM_DELETE_WINDOW", self.hide_window)
        
        # Configure window icon (if available)
        try:
            icon_path = self.app_path / "icon.ico"
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
        except:
            pass
        
        self.create_main_interface()
    
    def create_main_interface(self):
        """Create the main GUI interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Title
        title_label = ttk.Label(main_frame, text="🌡️ Temperature Monitor", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Status section
        status_frame = ttk.LabelFrame(main_frame, text="Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 15))
        status_frame.columnconfigure(1, weight=1)
        
        # Gmail status
        ttk.Label(status_frame, text="Gmail:").grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.gmail_status_label = ttk.Label(status_frame, text="Not Connected", foreground="red")
        self.gmail_status_label.grid(row=0, column=1, sticky=tk.W)
        
        # Monitoring status
        ttk.Label(status_frame, text="Monitoring:").grid(row=1, column=0, sticky=tk.W, padx=(0, 10))
        self.monitoring_status_label = ttk.Label(status_frame, text="Inactive", foreground="red")
        self.monitoring_status_label.grid(row=1, column=1, sticky=tk.W)
        
        # Temperature status
        ttk.Label(status_frame, text="Temperature:").grid(row=2, column=0, sticky=tk.W, padx=(0, 10))
        self.temp_status_label = ttk.Label(status_frame, text="No data", foreground="gray")
        self.temp_status_label.grid(row=2, column=1, sticky=tk.W)
        
        # Buttons section
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(15, 0))
        
        # Open Web Interface button
        self.web_button = ttk.Button(button_frame, text="🌐 Open Setup Wizard", 
                                    command=self.open_web_interface)
        self.web_button.grid(row=0, column=0, padx=(0, 10))
        
        # Test Alert button
        self.test_button = ttk.Button(button_frame, text="🔊 Test Voice Alert", 
                                     command=self.test_voice_alert)
        self.test_button.grid(row=0, column=1, padx=(0, 10))
        
        # Toggle Monitoring button
        self.toggle_button = ttk.Button(button_frame, text="▶️ Start Monitoring", 
                                       command=self.toggle_monitoring)
        self.toggle_button.grid(row=0, column=2)
        
        # Log display
        log_frame = ttk.LabelFrame(main_frame, text="Recent Activity", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(15, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Create text widget with scrollbar
        self.log_text = tk.Text(log_frame, height=8, state=tk.DISABLED, wrap=tk.WORD)
        scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Initial log message
        self.add_log_message("Application started. Open Setup Wizard to configure Gmail integration.")
        
        # Update status display
        self.update_status_display()
    
    def create_system_tray_icon(self):
        """Create system tray icon"""
        # Create a simple icon
        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill='white')
        draw.text((20, 20), "🌡️", fill='black')
        return image
    
    def setup_system_tray(self):
        """Setup system tray functionality"""
        try:
            icon_image = self.create_system_tray_icon()
            
            menu = pystray.Menu(
                pystray.MenuItem("Show Window", self.show_window),
                pystray.MenuItem("Open Web Interface", self.open_web_interface),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Toggle Monitoring", self.toggle_monitoring),
                pystray.MenuItem("Test Voice Alert", self.test_voice_alert),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Exit", self.quit_application)
            )
            
            self.tray_icon = pystray.Icon("TemperatureMonitor", icon_image, 
                                         "Temperature Monitor", menu)
            
            # Start tray icon in background thread
            tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            tray_thread.start()
            
            logger.info("System tray icon created")
        except Exception as e:
            logger.error(f"Error creating system tray: {e}")
            self.tray_icon = None
    
    def load_discovered_locations(self):
        """Load discovered locations from configuration - required by location_manager"""
        try:
            config_file = self.config_path / "discovered_locations.json"
            if config_file.exists():
                with open(config_file, 'r') as f:
                    locations_data = json.load(f)
                logger.info(f"Loaded {len(locations_data)} discovered locations")
                return locations_data
            else:
                logger.info("No discovered locations file found - starting fresh")
                return {}
        except Exception as e:
            logger.error(f"Error loading discovered locations: {e}")
            return {}

    def save_discovered_locations(self, locations_data):
        """Save discovered locations to configuration - required by location_manager"""
        try:
            config_file = self.config_path / "discovered_locations.json"
            with open(config_file, 'w') as f:
                json.dump(locations_data, f, indent=4)
            logger.info(f"Saved {len(locations_data)} discovered locations")
        except Exception as e:
            logger.error(f"Error saving discovered locations: {e}")


    def start_services(self):
        """Start background services with automatic Gmail connection"""
        # Initialize services
        try:
            from services.auth_manager import GmailAuthManager
            from services.gmail_service import GmailTemperatureService
            from services.sheets_service import TemperatureSheetsService
            
            self.auth_manager = GmailAuthManager(self.app_path)
            self.gmail_service = GmailTemperatureService(self.auth_manager, self)
            spreadsheet_id = self.config.get("sheets", {}).get("spreadsheet_id")
            self.sheets_service = TemperatureSheetsService(self.auth_manager, spreadsheet_id, self)
            
            logger.info("Services initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing services: {e}")
            self.add_log_message(f"❌ Service initialization failed: {e}")
            return
        
        # 🔥 AUTO-CONNECT TO GMAIL ON STARTUP
        self.auto_connect_gmail()
        
        # Start web server
        web_thread = threading.Thread(target=self.start_web_server, daemon=True)
        web_thread.start()
        
        # Start alert processor
        alert_thread = threading.Thread(target=self.process_alerts, daemon=True)
        alert_thread.start()
        # Initialize and start connection monitoring
        self.connection_monitor = ConnectionMonitor(self)
        self.add_log_message("🔄 Connection monitoring started")
        self.start_auto_recovery()
        # 🔥 AUTO-START SCHEDULER IF CONFIGURED
        self.auto_start_scheduler()

    def auto_connect_gmail(self):
        """Automatically connect to Gmail on startup - RESILIENT VERSION that never crashes"""
        try:
            logger.info("🔄 Starting resilient Gmail auto-connect...")
            self.add_log_message("🔄 Checking Gmail connection...")
            
            # Use our safe connection method with timeout
            success, message = self.safe_gmail_connect(timeout_seconds=30)
            
            if success:
                logger.info(f"✅ Gmail auto-connect successful: {message}")
                self.add_log_message(f"✅ Gmail auto-connected: {message}")
                
                # Update GUI status on main thread
                self.root.after(0, self.update_status_display)
                
                # Test email search to verify everything works
                try:
                    self.test_gmail_connection()
                except Exception as e:
                    # Don't crash if test fails - just log it
                    logger.warning(f"Gmail test failed but connection succeeded: {e}")
                    self.add_log_message(f"⚠️ Gmail connected but test failed: {str(e)}")
                
                return True
            else:
                logger.warning(f"Gmail auto-connect failed: {message}")
                self.add_log_message(f"⚠️ Gmail auto-connect failed: {message}")
                self.add_log_message("ℹ️ Use web interface to connect Gmail manually")
                
                # Update GUI to show disconnected status
                self.update_gmail_status(f"Auto-connect failed: {message}")
                self.root.after(100, self.update_status_display)
                
                return False
                
        except Exception as e:
            # NEVER crash the app - just log the error
            error_msg = f"Gmail auto-connect error: {str(e)}"
            logger.error(f"❌ {error_msg}")
            self.add_log_message(f"❌ {error_msg}")
            self.add_log_message("ℹ️ App continues running - use web interface to connect Gmail")
            
            # Update GUI to show error status
            self.update_gmail_status("Auto-connect error - Use web interface")
            self.root.after(100, self.update_status_display)
            
            return False
        
    def safe_gmail_connect(self, timeout_seconds=30):
        """Safely attempt Gmail connection with timeout and error handling"""
        try:
            logger.info("🔄 Attempting safe Gmail connection...")
            self.add_log_message("🔄 Connecting to Gmail...")
            
            # Check if credentials file exists first
            if not hasattr(self, 'auth_manager') or not self.auth_manager:
                logger.warning("Auth manager not available")
                return False, "Authentication manager not initialized"
            
            valid, message = self.auth_manager.check_credentials_file()
            if not valid:
                logger.warning(f"Credentials file issue: {message}")
                self.add_log_message("⚠️ Gmail credentials not found - use web interface to connect")
                return False, f"Credentials not available: {message}"
            
            # Check if already authenticated
            if self.auth_manager.is_authenticated():
                logger.info("✅ Gmail already authenticated")
                self.add_log_message("✅ Gmail already connected")
                return True, "Already authenticated"
            
            # Attempt authentication
            success, auth_message = self.auth_manager.authenticate()
            
            if not success:
                logger.warning(f"Gmail authentication failed: {auth_message}")
                self.add_log_message(f"⚠️ Gmail authentication failed: {auth_message}")
                return False, auth_message
            
            # Test Gmail service
            gmail_success, gmail_message = self.gmail_service.connect()
            
            if gmail_success:
                user_email = self.auth_manager.get_user_email()
                logger.info(f"✅ Gmail connected successfully: {user_email}")
                self.add_log_message(f"✅ Gmail connected: {user_email}")
                
                # Update configuration
                self.config['gmail']['connected'] = True
                self.config['gmail']['email'] = user_email or 'Connected'
                self.save_config()
                
                return True, f"Connected: {user_email}"
            else:
                logger.warning(f"Gmail service failed: {gmail_message}")
                return False, gmail_message
                
        except Exception as e:
            logger.error(f"Exception during Gmail connection: {e}")
            self.add_log_message(f"⚠️ Gmail connection error: {str(e)}")
            return False, f"Connection error: {e}"

    def test_gmail_connection(self):
        """Test Gmail connection and search capability"""
        try:
            logger.info("Testing Gmail email search...")
            
            # Quick test search (last 24 hours)
            emails, message = self.gmail_service.search_temperature_emails(hours_back=24, max_results=5)
            
            if emails:
                logger.info(f"✅ Gmail test successful: Found {len(emails)} temperature emails")
                self.add_log_message(f"✅ Gmail test: Found {len(emails)} temperature emails")
            else:
                if "error" in message.lower() or "failed" in message.lower():
                    logger.warning(f"⚠️ Gmail test warning: {message}")
                    self.add_log_message(f"⚠️ Gmail test: {message}")
                else:
                    logger.info(f"✅ Gmail test: {message}")
                    self.add_log_message(f"✅ Gmail test: {message}")
            
        except Exception as e:
            logger.warning(f"Gmail test failed: {e}")
            self.add_log_message(f"⚠️ Gmail test failed: {str(e)}")

    def auto_start_scheduler(self):
        """Automatically start scheduler if configured and Gmail is connected - with resilient error handling"""
        try:
            # ✅ FIX: Check REAL auth status, not config value
            if not hasattr(self, 'auth_manager') or not self.auth_manager:
                logger.info("Scheduler not started - auth manager not available")
                self.add_log_message("⚠️ Scheduler not started - auth manager not ready")
                return
            
            # Check if Gmail is actually authenticated (not just config setting)
            if not self.auth_manager.is_authenticated():
                logger.info("Scheduler not started - Gmail not authenticated")
                self.add_log_message("ℹ️ Scheduler not started - Gmail authentication required")
                return
            
            # Check if scheduler is enabled in config
            scheduler_config = self.config.get('scheduler', {})
            if not scheduler_config.get('enabled', False):
                logger.info("Scheduler not started - disabled in settings")
                self.add_log_message("ℹ️ Scheduler disabled in settings")
                return
            
            # ✅ NEW: Add retry logic for scheduler startup
            max_retries = 3
            retry_delay = 5
            
            for attempt in range(max_retries):
                try:
                    logger.info(f"Attempting to start scheduler (attempt {attempt + 1}/{max_retries})...")
                    self.add_log_message(f"🔄 Starting scheduler (attempt {attempt + 1}/{max_retries})...")
                    
                    # Give services time to initialize if this is first attempt
                    if attempt == 0:
                        time.sleep(3)
                    
                    # Import and start scheduler
                    from services.temperature_scheduler import TemperatureScheduler
                    
                    # Initialize scheduler if not already done
                    if not hasattr(self, 'scheduler') or not self.scheduler:
                        self.scheduler = TemperatureScheduler(self, self.gmail_service, self.sheets_service)
                        logger.info("✅ Scheduler instance created")
                    
                    # ✅ FIX: Properly handle start_scheduler results
                    success, message = self.scheduler.start_scheduler()
                    
                    if success:
                        logger.info(f"✅ Scheduler started successfully: {message}")
                        self.add_log_message(f"✅ Scheduler started: {message}")
                        
                        # Get next run time
                        next_run, next_message = self.scheduler.get_next_announcement_time()
                        if next_run:
                            self.add_log_message(f"📅 {next_message}")
                            logger.info(f"📅 {next_message}")
                        
                        # Success - break out of retry loop
                        return
                    else:
                        logger.warning(f"⚠️ Scheduler start attempt {attempt + 1} failed: {message}")
                        self.add_log_message(f"⚠️ Scheduler attempt {attempt + 1} failed: {message}")
                        
                        if attempt < max_retries - 1:
                            logger.info(f"Retrying scheduler start in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                        else:
                            # Final attempt failed
                            logger.error(f"❌ Scheduler failed to start after {max_retries} attempts")
                            self.add_log_message(f"❌ Scheduler failed after {max_retries} attempts - will retry automatically")
                            
                except Exception as e:
                    logger.error(f"❌ Scheduler start attempt {attempt + 1} exception: {e}")
                    self.add_log_message(f"❌ Scheduler attempt {attempt + 1} error: {str(e)}")
                    
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying scheduler start in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                    else:
                        # Final attempt failed
                        logger.error(f"❌ Scheduler startup failed after {max_retries} attempts with exceptions")
                        self.add_log_message("❌ Scheduler startup failed - will retry in background")
            
            # Schedule a delayed retry in the background if all attempts failed
            def delayed_retry():
                time.sleep(60)  # Wait 1 minute
                logger.info("🔄 Attempting delayed scheduler retry...")
                self.add_log_message("🔄 Retrying scheduler startup...")
                self.auto_start_scheduler()
            
            retry_thread = threading.Thread(target=delayed_retry, daemon=True)
            retry_thread.start()
                            
        except Exception as e:
            logger.error(f"Critical error in auto_start_scheduler: {e}")
            self.add_log_message(f"❌ Scheduler startup error: {str(e)}")

    def update_gmail_status(self, status):
        """Update Gmail status display safely"""
        try:
            def update_ui():
                if hasattr(self, 'gmail_status_label'):
                    if "Connected:" in status:
                        self.gmail_status_label.config(text=status, foreground="green")
                    elif "Not Connected" in status or "Failed" in status:
                        self.gmail_status_label.config(text=status, foreground="red")
                    else:
                        self.gmail_status_label.config(text=status, foreground="orange")
            
            # Schedule UI update on main thread
            if hasattr(self, 'root'):
                self.root.after(0, update_ui)
                
        except Exception as e:
            logger.error(f"Error updating Gmail status display: {e}")

    def show_startup_summary(self):
        """Show a summary of startup status after all services initialize"""
        def show_summary():
            time.sleep(5)  # Wait for all services to initialize
            
            gmail_connected = self.config.get('gmail', {}).get('connected', False)
            scheduler_enabled = self.config.get('scheduler', {}).get('enabled', False)
            
            summary_parts = []
            summary_parts.append("🚀 Temperature Monitor Ready!")
            
            if gmail_connected:
                summary_parts.append("✅ Gmail connected and tested")
            else:
                summary_parts.append("⚠️ Gmail not connected - use web interface")
            
            if scheduler_enabled and gmail_connected:
                summary_parts.append("✅ Scheduler running - daily announcements active")
            elif scheduler_enabled:
                summary_parts.append("⚠️ Scheduler enabled but Gmail needed")
            else:
                summary_parts.append("ℹ️ Scheduler disabled - enable in web interface")
            
            summary_parts.append("🌐 Web interface available at localhost:8080")
            
            summary_message = "\n".join(summary_parts)
            logger.info(f"Startup Summary:\n{summary_message}")
            self.add_log_message("📋 " + summary_parts[0])
            
        # Show summary in background
        summary_thread = threading.Thread(target=show_summary, daemon=True)
        summary_thread.start()
    
    def start_web_server(self):
        """Start the embedded Flask web server"""
        try:
            from web_interface.app import create_app
            
            app = create_app(self)
            host = self.config["web_server"]["host"]
            port = self.config["web_server"]["port"]
            
            logger.info(f"Starting web server on {host}:{port}")
            app.run(host=host, port=port, debug=False, use_reloader=False)
            
        except ImportError:
            logger.error("Web interface not found. Creating basic Flask app.")
            self.create_basic_web_server()
        except Exception as e:
            logger.error(f"Error starting web server: {e}")
    
    def create_basic_web_server(self):
        """Create a basic Flask web server if web_interface module not found"""
        try:
            from flask import Flask, render_template_string
            
            app = Flask(__name__)
            
            @app.route('/')
            def index():
                return render_template_string("""
                <h1>Temperature Monitor</h1>
                <p>Web interface will be available here.</p>
                <p>Current status: {{ status }}</p>
                """, status="Running")
            
            host = self.config["web_server"]["host"]
            port = self.config["web_server"]["port"]
            
            logger.info(f"Starting basic web server on {host}:{port}")
            app.run(host=host, port=port, debug=False, use_reloader=False)
            
        except Exception as e:
            logger.error(f"Error starting basic web server: {e}")
    
    def start_monitoring_service(self):
        """Start temperature monitoring service"""
        # This will be implemented when we add Gmail integration
        logger.info("Monitoring service started (placeholder)")
    
    def process_alerts(self):
        """Process temperature alerts from queue"""
        while self.running:
            try:
                # Check for alerts in queue
                if not self.alert_queue.empty():
                    alert = self.alert_queue.get_nowait()
                    self.handle_temperature_alert(alert)
                
                time.sleep(1)  # Check every second
                
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"Error processing alerts: {e}")
    
    def handle_temperature_alert(self, alert_data):
        """Handle a temperature alert"""
        temp = alert_data.get('temperature', 'Unknown')
        location = alert_data.get('location', 'Unknown location')
        alert_type = alert_data.get('type', 'temperature')
        
        message = f"Temperature alert: {temp}°C at {location}"
        
        # Add to log
        self.add_log_message(f"ALERT: {message}")
        
        # Play voice alert if enabled and within allowed hours
        if self.config["tts"]["enabled"] and self.is_voice_allowed():
            self.speak_alert(message)
        
        # Update GUI status
        self.root.after(0, lambda: self.update_temp_status(f"{temp}°C - ALERT"))
    
    def is_voice_allowed(self):
        """Check if voice alerts are allowed based on quiet hours"""
        try:
            now = datetime.now().time()
            start_time = datetime.strptime(self.config["tts"]["quiet_hours_start"], "%H:%M").time()
            end_time = datetime.strptime(self.config["tts"]["quiet_hours_end"], "%H:%M").time()
            
            if start_time <= end_time:
                # Same day quiet hours
                return not (start_time <= now <= end_time)
            else:
                # Overnight quiet hours
                return not (now >= start_time or now <= end_time)
        except:
            return True  # Allow voice if there's an error parsing times
    
    def speak_alert(self, message):
        """Speak an alert message using TTS"""
        try:
            # Use Windows SAPI directly instead of pyttsx3
            import subprocess
            import platform
            
            if platform.system() == "Windows":
                # Escape single quotes in the message to prevent PowerShell errors
                escaped_message = message.replace("'", "''")
                # Use Windows built-in speech with female voice
                command = f'''powershell -Command "
                    Add-Type -AssemblyName System.Speech;
                    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer;
                    $femaleVoice = $synth.GetInstalledVoices() | Where-Object {{$_.VoiceInfo.Gender -eq 'Female'}} | Select-Object -First 1;
                    if ($femaleVoice) {{ $synth.SelectVoice($femaleVoice.VoiceInfo.Name) }};
                    $synth.Speak('{escaped_message}')
                "'''
                subprocess.run(command, shell=True, capture_output=True)
                logger.info("Voice alert delivered via Windows SAPI (female voice)")
            else:
                logger.warning("Voice alerts only supported on Windows")
                
    except Exception as e:
        logger.error(f"Error with TTS: {e}")
        self.add_log_message(f"Voice alert failed: {str(e)}")
            
    def test_voice_alert(self):
        """Test voice alert functionality"""
        test_message = "This is a test temperature alert. The system is working correctly."
        self.add_log_message("Testing voice alert...")
        
        if self.tts_engine:
            threading.Thread(target=lambda: self.speak_alert(test_message), daemon=True).start()
        else:
            messagebox.showwarning("TTS Error", "Text-to-speech engine not available")
    
    def toggle_monitoring(self):
        """Toggle temperature monitoring on/off"""
        self.monitoring_active = not self.monitoring_active
        
        if self.monitoring_active:
            self.toggle_button.config(text="⏸️ Stop Monitoring")
            self.monitoring_status_label.config(text="Active", foreground="green")
            self.add_log_message("Temperature monitoring started")
        else:
            self.toggle_button.config(text="▶️ Start Monitoring")
            self.monitoring_status_label.config(text="Inactive", foreground="red")
            self.add_log_message("Temperature monitoring stopped")
    
    def open_web_interface(self):
        """Open web interface in default browser"""
        try:
            url = f"http://{self.config['web_server']['host']}:{self.config['web_server']['port']}"
            webbrowser.open(url)
            self.add_log_message(f"Opened web interface: {url}")
        except Exception as e:
            logger.error(f"Error opening web interface: {e}")
            messagebox.showerror("Error", f"Could not open web interface: {e}")
    
    def update_status_display(self):
        """Update the status display in GUI with detailed error information"""
        # Gmail status - check both config and real authentication
        try:
            real_gmail_connected = self.auth_manager.is_authenticated() if hasattr(self, 'auth_manager') else False
            config_gmail_connected = self.config["gmail"]["connected"]
            
            # Use real status if available, fall back to config
            if real_gmail_connected:
                user_email = self.auth_manager.get_user_email()
                self.gmail_status_label.config(text=f"Connected: {user_email}", foreground="green")
            elif config_gmail_connected:
                # Config says connected but auth failed - show specific error
                self.gmail_status_label.config(text="❌ Auth Failed - Click 'Connect Gmail' to fix", foreground="red")
            else:
                # Check if credentials file exists to give helpful error
                creds_file = self.config_path / "credentials.json"
                if not creds_file.exists():
                    self.gmail_status_label.config(text="❌ Missing credentials.json file", foreground="red")
                else:
                    self.gmail_status_label.config(text="❌ Not Connected - Setup required", foreground="red")
        except Exception as e:
            self.gmail_status_label.config(text=f"❌ Error: {str(e)[:50]}...", foreground="red")
        
       
        # Temperature type - use global default
        temp_config = self.config["temperature"]
        global_default = temp_config.get("global_default", {"type": "fridge", "min_temp": 2, "max_temp": 8})
        temp_type = global_default["type"]
        if temp_type == "fridge":
            temp_info = "Fridge (2-8°C)"
        elif temp_type == "room":
            temp_info = "Room (>25°C)"
        else:
            temp_info = f"Custom ({global_default['min_temp']}-{global_default['max_temp']}°C)"
        # Update monitoring status - consider monitoring active if Gmail connected and scheduler running
        try:
            # Check if scheduler is running using our method
            scheduler_running = self.is_scheduler_running()
            
            # Monitoring is active if either manually toggled OR (Gmail connected AND scheduler running)
            is_monitoring_active = self.monitoring_active or (real_gmail_connected and scheduler_running)
            
            if is_monitoring_active:
                if scheduler_running:
                    # Show next announcement time if available
                    if hasattr(self, 'scheduler'):
                        next_run, next_message = self.scheduler.get_next_announcement_time()
                        if next_run:
                            next_time = next_run.strftime('%H:%M')
                            self.monitoring_status_label.config(text=f"✅ Active - {temp_info} (Next: {next_time})", foreground="green")
                        else:
                            self.monitoring_status_label.config(text=f"✅ Active - {temp_info} (Scheduled)", foreground="green")
                    else:
                        self.monitoring_status_label.config(text=f"✅ Active - {temp_info}", foreground="green")
                else:
                    self.monitoring_status_label.config(text=f"✅ Active - {temp_info}", foreground="green")
            else:
                if real_gmail_connected:
                    if hasattr(self, 'scheduler'):
                        scheduler_enabled = self.config.get('scheduler', {}).get('enabled', False)
                        if scheduler_enabled and not scheduler_running:
                            self.monitoring_status_label.config(text=f"❌ Scheduler stopped - {temp_info}", foreground="red")
                        elif not scheduler_enabled:
                            self.monitoring_status_label.config(text=f"⚠️ Ready - {temp_info} (Enable scheduler)", foreground="orange")
                        else:
                            self.monitoring_status_label.config(text=f"⚠️ Ready - {temp_info} (Start scheduler)", foreground="orange")
                    else:
                        self.monitoring_status_label.config(text=f"⚠️ Ready - {temp_info} (Start scheduler)", foreground="orange")
                else:
                    self.monitoring_status_label.config(text="❌ Inactive - Gmail connection required", foreground="red")
        except Exception as e:
            self.monitoring_status_label.config(text=f"❌ Status Error: {str(e)[:30]}...", foreground="red")
        
        # Temperature status - show last check time and data
        try:
            if hasattr(self, 'gmail_service') and real_gmail_connected:
                # Try to get recent temperature summary to show last data time
                import threading
                def update_temp_status():
                    try:
                        summary = self.gmail_service.get_temperature_summary(hours_back=24, auto_log_to_sheets=False)
                        if summary['total_readings'] > 0:
                            latest = summary.get('latest_reading')
                            if latest:
                                last_temp = f"{latest['value']}°C at {latest['location']}"
                                timestamp = latest['timestamp'].strftime('%H:%M')
                                self.temp_status_label.config(text=f"🌡️ {last_temp} (Last: {timestamp})", foreground="green")
                            else:
                                self.temp_status_label.config(text=f"📊 {summary['total_readings']} readings found", foreground="green")
                        else:
                            self.temp_status_label.config(text="⚠️ No temperature data found (24h)", foreground="orange")
                    except Exception as e:
                        self.temp_status_label.config(text=f"❌ Data check failed: {str(e)[:30]}...", foreground="red")
                
                # Run temperature check in background to avoid blocking UI
                temp_thread = threading.Thread(target=update_temp_status, daemon=True)
                temp_thread.start()
            else:
                self.temp_status_label.config(text="❌ No data - Gmail required", foreground="red")
        except Exception as e:
            self.temp_status_label.config(text=f"❌ Error: {str(e)[:30]}...", foreground="red")
        
    def update_gmail_status(self, status):
        """Update Gmail status display safely"""
        try:
            def update_ui():
                if hasattr(self, 'gmail_status_label'):
                    if "Connected:" in status:
                        self.gmail_status_label.config(text=status, foreground="green")
                    elif "Not Connected" in status or "Failed" in status or "Authentication Failed" in status:
                        self.gmail_status_label.config(text=status, foreground="red")
                    else:
                        self.gmail_status_label.config(text=status, foreground="orange")
            
            # Schedule UI update on main thread
            if hasattr(self, 'root'):
                self.root.after(0, update_ui)
                
        except Exception as e:
            logger.error(f"Error updating Gmail status display: {e}")
    
    def is_scheduler_running(self):
        """Check if the temperature scheduler is currently running"""
        try:
            if not hasattr(self, 'scheduler'):
                return False
            
            # Check if scheduler exists and has is_running attribute
            if hasattr(self.scheduler, 'is_running'):
                return self.scheduler.is_running
            
            # Fallback: check if any scheduled jobs exist and scheduler thread is alive
            import schedule
            scheduled_jobs = len(schedule.get_jobs())
            thread_alive = hasattr(self.scheduler, 'scheduler_thread') and self.scheduler.scheduler_thread and self.scheduler.scheduler_thread.is_alive()
            
            return scheduled_jobs > 0 and thread_alive
            
        except Exception as e:
            logger.error(f"Error checking scheduler status: {e}")
            return False

    def update_temp_status(self, status):
        """Update temperature status label"""
        self.temp_status_label.config(text=status)
    
    def add_log_message(self, message):
        """Add a message to the log display"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        def update_log():
            self.log_text.config(state=tk.NORMAL)
            self.log_text.insert(tk.END, log_entry)
            self.log_text.see(tk.END)
            self.log_text.config(state=tk.DISABLED)
        
        # Ensure GUI updates happen on main thread
        if threading.current_thread() == threading.main_thread():
            update_log()
        else:
            self.root.after(0, update_log)
    
    def show_window(self, icon=None, item=None):
        """Show the main window"""
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
    
    def hide_window(self):
        """Hide window to system tray"""
        self.root.withdraw()
    
    def quit_application(self, icon=None, item=None):
        """Quit the application"""
        self.running = False
        
        if self.tray_icon:
            self.tray_icon.stop()
        
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except:
                pass
        
        self.root.quit()
        sys.exit(0)
    
    def start_auto_recovery(self):
        """Start the auto-recovery background thread"""
        try:
            recovery_thread = threading.Thread(target=self.auto_recovery_loop, daemon=True)
            recovery_thread.start()
            self.add_log_message("🛡️ Auto-recovery monitoring started")
            logger.info("Auto-recovery thread started")
        except Exception as e:
            logger.error(f"Error starting auto-recovery: {e}")

    def auto_recovery_loop(self):
        """Background thread for monitoring and auto-recovery"""
        while self.running:
            try:
                # Check connectivity every 60 seconds
                time.sleep(60)
                
                if not self.connection_monitor:
                    continue
                    
                status = self.connection_monitor.get_connectivity_status()
                
                # Handle different connectivity scenarios
                if not status['internet']:
                    self.handle_internet_loss()
                elif status['internet'] and not status['gmail']:
                    self.handle_gmail_recovery()
                elif status['internet'] and status['gmail']:
                    self.handle_full_recovery()
                    
            except Exception as e:
                logger.error(f"Auto-recovery loop error: {e}")
                time.sleep(60)  # Continue even if there's an error

    def handle_internet_loss(self):
        """Handle internet connectivity loss"""
        if self.connection_monitor.is_online:
            self.connection_monitor.is_online = False
            self.add_log_message("⚠️ Internet connection lost - monitoring paused")
            self.update_gmail_status("🔴 Offline - Connection lost")
            logger.warning("Internet connection lost")

    def handle_gmail_recovery(self):
        """Attempt to recover Gmail connection"""
        try:
            if self.connection_monitor.retry_count < self.connection_monitor.max_retries:
                self.connection_monitor.retry_count += 1
                self.add_log_message(f"🔄 Attempting Gmail recovery (attempt {self.connection_monitor.retry_count})")
                
                success, message = self.auth_manager.authenticate()
                
                if success:
                    self.add_log_message("✅ Gmail connection recovered")
                    self.connection_monitor.retry_count = 0
                    
                    # Restart scheduler if it's not running
                    if not self.is_scheduler_running():
                        self.auto_start_scheduler()
                else:
                    self.add_log_message(f"❌ Gmail recovery failed: {message}")
                    
        except Exception as e:
            logger.error(f"Gmail recovery error: {e}")
            self.add_log_message(f"❌ Recovery error: {str(e)}")

    def handle_full_recovery(self):
        """Handle full system recovery after connectivity restored"""
        if not self.connection_monitor.is_online:
            self.connection_monitor.is_online = True
            self.connection_monitor.retry_count = 0
            self.add_log_message("✅ Internet connection restored")
            logger.info("Full connectivity recovered")
            
            # Update status display
            self.root.after(0, self.update_status_display)
            
            # Restart scheduler if it's not running but should be
            scheduler_enabled = self.config.get('scheduler', {}).get('enabled', False)
            if scheduler_enabled and not self.is_scheduler_running():
                self.add_log_message("🔄 Restarting scheduler after recovery")
                self.auto_start_scheduler()

    def check_auto_startup_status(self):
        """Check if auto-startup is currently enabled in Windows registry"""
        if platform.system() != "Windows" or not winreg:
            return False, "Auto-startup only available on Windows"
        
        try:
            app_name = self.config.get('auto_startup', {}).get('app_name', 'Temperature Monitor')
            
            # Open the Run registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_READ
            )
            
            try:
                # Try to read our app's entry
                value, reg_type = winreg.QueryValueEx(key, app_name)
                winreg.CloseKey(key)
                
                # Check if the path matches our current executable
                current_path = self.get_executable_path()
                if value.strip('"') == current_path:
                    return True, f"Auto-startup enabled: {app_name}"
                else:
                    return False, f"Auto-startup entry exists but path mismatch: {value}"
                    
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False, f"Auto-startup not enabled: {app_name} not found in registry"
                
        except Exception as e:
            logger.error(f"Error checking auto-startup status: {e}")
            return False, f"Error checking registry: {e}"

    def enable_auto_startup(self):
        """Enable auto-startup by adding Windows registry entry"""
        if platform.system() != "Windows" or not winreg:
            return False, "Auto-startup only available on Windows"
        
        try:
            app_name = self.config.get('auto_startup', {}).get('app_name', 'Temperature Monitor')
            executable_path = self.get_executable_path()
            
            logger.info(f"Adding auto-startup registry entry: {app_name} -> {executable_path}")
            
            # Open the Run registry key for writing
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_WRITE
            )
            
            # Add our entry - wrap path in quotes to handle spaces
            quoted_path = f'"{executable_path}"'
            winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, quoted_path)
            winreg.CloseKey(key)
            
            # Update configuration
            if 'auto_startup' not in self.config:
                self.config['auto_startup'] = {}
            self.config['auto_startup']['enabled'] = True
            self.config['auto_startup']['validated'] = True
            self.save_config()
            
            logger.info(f"Auto-startup enabled successfully: {app_name}")
            return True, f"Auto-startup enabled: {app_name} will start with Windows"
            
        except Exception as e:
            error_msg = f"Error enabling auto-startup: {e}"
            logger.error(error_msg)
            return False, error_msg

    def disable_auto_startup(self):
        """Disable auto-startup by removing Windows registry entry"""
        if platform.system() != "Windows" or not winreg:
            return False, "Auto-startup only available on Windows"
        
        try:
            app_name = self.config.get('auto_startup', {}).get('app_name', 'Temperature Monitor')
            
            logger.info(f"Removing auto-startup registry entry: {app_name}")
            
            # Open the Run registry key for writing
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_WRITE
            )
            
            try:
                # Delete our entry
                winreg.DeleteValue(key, app_name)
                winreg.CloseKey(key)
                
                # Update configuration
                if 'auto_startup' not in self.config:
                    self.config['auto_startup'] = {}
                self.config['auto_startup']['enabled'] = False
                self.config['auto_startup']['validated'] = False
                self.save_config()
                
                logger.info(f"Auto-startup disabled successfully: {app_name}")
                return True, f"Auto-startup disabled: {app_name} will not start with Windows"
                
            except FileNotFoundError:
                winreg.CloseKey(key)
                # Entry doesn't exist, consider it success
                return True, f"Auto-startup already disabled: {app_name} not found in registry"
                
        except Exception as e:
            error_msg = f"Error disabling auto-startup: {e}"
            logger.error(error_msg)
            return False, error_msg

    def validate_startup_entry(self):
        """Validate that the auto-startup registry entry is correct"""
        if platform.system() != "Windows" or not winreg:
            return False, "Auto-startup validation only available on Windows"
        
        try:
            enabled, message = self.check_auto_startup_status()
            
            if enabled:
                # Update config to reflect validated status
                if 'auto_startup' not in self.config:
                    self.config['auto_startup'] = {}
                self.config['auto_startup']['validated'] = True
                self.save_config()
                
                return True, "Auto-startup validation successful"
            else:
                return False, f"Auto-startup validation failed: {message}"
                
        except Exception as e:
            error_msg = f"Error validating auto-startup: {e}"
            logger.error(error_msg)
            return False, error_msg

    def get_executable_path(self):
        """Get the path to the current executable (works for both script and exe)"""
        if getattr(sys, 'frozen', False):
            # Running as compiled exe
            return sys.executable
        else:
            # Running as script - return python + script path
            script_path = str(Path(__file__).resolve())
            python_path = sys.executable
            return f'"{python_path}" "{script_path}"'

    def get_auto_startup_status(self):
        """Get complete auto-startup status for web interface"""
        try:
            config_enabled = self.config.get('auto_startup', {}).get('enabled', False)
            registry_enabled, registry_message = self.check_auto_startup_status()
            
            return {
                'available': platform.system() == "Windows" and winreg is not None,
                'config_enabled': config_enabled,
                'registry_enabled': registry_enabled,
                'registry_message': registry_message,
                'validated': config_enabled and registry_enabled,
                'executable_path': self.get_executable_path()
            }
        except Exception as e:
            return {
                'available': False,
                'error': str(e)
            }

    def run(self):
        """Run the application"""
        logger.info("Starting Temperature Monitor Application")
        
        # Start hidden if system tray is available
        if self.tray_icon:
            self.root.withdraw()
        
        # Start GUI event loop
        self.root.mainloop()

def main():
    """Main entry point"""
    try:
        app = TemperatureMonitorApp()
        app.run()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        if hasattr(app, 'root'):
            messagebox.showerror("Fatal Error", f"Application error: {e}")

if __name__ == "__main__":
    main()