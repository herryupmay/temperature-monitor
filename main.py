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
                "type": "fridge",  # fridge, room, custom
                "min_temp": 2,
                "max_temp": 8,
                "name": "Fridge Monitor"
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
        """Start background services"""

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
        
        # Start web server
        web_thread = threading.Thread(target=self.start_web_server, daemon=True)
        web_thread.start()
        
        # Start alert processor
        alert_thread = threading.Thread(target=self.process_alerts, daemon=True)
        alert_thread.start()
        
        # Start monitoring service (if configured)
        if self.config["gmail"]["connected"]:
            monitor_thread = threading.Thread(target=self.start_monitoring_service, daemon=True)
            monitor_thread.start()
    
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
        if self.tts_engine:
            try:
                self.tts_engine.say(message)
                self.tts_engine.runAndWait()
            except Exception as e:
                logger.error(f"Error with TTS: {e}")
    
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
        """Update the status display in GUI"""
        # Gmail status
        if self.config["gmail"]["connected"]:
            self.gmail_status_label.config(text="Connected", foreground="green")
        else:
            self.gmail_status_label.config(text="Not Connected", foreground="red")
        
        # Temperature type
        temp_config = self.config["temperature"]
        temp_type = temp_config["type"]
        if temp_type == "fridge":
            temp_info = "Fridge (2-8°C)"
        elif temp_type == "room":
            temp_info = "Room (>25°C)"
        else:
            temp_info = f"Custom ({temp_config['min_temp']}-{temp_config['max_temp']}°C)"
        
        # Update monitoring status
        if self.monitoring_active:
            self.monitoring_status_label.config(text=f"Active - {temp_info}", foreground="green")
        else:
            self.monitoring_status_label.config(text="Inactive", foreground="red")
    
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