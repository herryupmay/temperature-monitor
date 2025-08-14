"""
Gmail OAuth Authentication Manager
Handles OAuth 2.0 flow, token storage, and re-authentication for Gmail API access
"""

import os
import json
import logging
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GmailAuthManager:
    """Handles Gmail OAuth authentication and API service creation"""
    
    # Gmail API scopes needed for reading emails
    SCOPES = [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file'
    ]
    
    def __init__(self, app_path):
        """Initialize auth manager with application path"""
        self.app_path = Path(app_path)
        self.config_path = self.app_path / "config"
        self.credentials_file = self.config_path / "credentials.json"
        self.token_file = self.config_path / "token.json"
        self.creds = None
        self.gmail_service = None
        self.sheets_service = None
        
        # Ensure config directory exists
        self.config_path.mkdir(exist_ok=True)
    
    def check_credentials_file(self):
        """Check if credentials.json file exists"""
        if not self.credentials_file.exists():
            logger.error(f"Credentials file not found: {self.credentials_file}")
            return False, f"Please place your credentials.json file in: {self.config_path}"
        return True, "Credentials file found"
    
    def authenticate(self):
        """Perform OAuth authentication flow"""
        try:
            # Check if credentials file exists
            valid, message = self.check_credentials_file()
            if not valid:
                return False, message
            
            # Load existing token if available
            if self.token_file.exists():
                try:
                    self.creds = Credentials.from_authorized_user_file(str(self.token_file), self.SCOPES)
                    logger.info("Loaded existing credentials from token file")
                except Exception as e:
                    logger.warning(f"Could not load existing token: {e}")
                    self.creds = None
            
            # If there are no (valid) credentials available, let the user log in
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    try:
                        logger.info("Refreshing expired credentials...")
                        self.creds.refresh(Request())
                        logger.info("Credentials refreshed successfully")
                    except Exception as e:
                        logger.error(f"Error refreshing credentials: {e}")
                        self.creds = None
                
                # If still no valid credentials, start OAuth flow
                if not self.creds or not self.creds.valid:
                    logger.info("Starting OAuth flow...")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(self.credentials_file), self.SCOPES)
                    
                    # Use local server for OAuth callback
                    self.creds = flow.run_local_server(port=0, open_browser=True)
                    logger.info("OAuth flow completed successfully")
                
                # Save the credentials for the next run
                with open(self.token_file, 'w') as token:
                    token.write(self.creds.to_json())
                logger.info("Credentials saved to token file")
            
            # Test the connection by building Gmail service
            self.gmail_service = build('gmail', 'v1', credentials=self.creds)
            self.sheets_service = build('sheets', 'v4', credentials=self.creds)
            
            # Test with a simple API call
            profile = self.gmail_service.users().getProfile(userId='me').execute()
            email_address = profile.get('emailAddress', 'Unknown')
            
            logger.info(f"Successfully authenticated Gmail for: {email_address}")
            return True, f"Gmail connected successfully: {email_address}"
            
        except HttpError as e:
            error_msg = f"Gmail API error: {e}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Authentication error: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_user_email(self):
        """Get the authenticated user's email address"""
        try:
            if not self.gmail_service:
                return None
            
            profile = self.gmail_service.users().getProfile(userId='me').execute()
            return profile.get('emailAddress')
        except Exception as e:
            logger.error(f"Error getting user email: {e}")
            return None
    
    def is_authenticated(self):
        """Check if user is currently authenticated"""
        return (self.creds is not None and 
                self.creds.valid and 
                self.gmail_service is not None)
    
    def revoke_authentication(self):
        """Revoke authentication and clean up tokens"""
        try:
            if self.creds and self.creds.valid:
                # Revoke the token
                self.creds.revoke(Request())
                logger.info("Authentication revoked")
            
            # Remove token file
            if self.token_file.exists():
                self.token_file.unlink()
                logger.info("Token file removed")
            
            # Clear in-memory credentials
            self.creds = None
            self.gmail_service = None
            self.sheets_service = None
            
            return True, "Authentication revoked successfully"
            
        except Exception as e:
            error_msg = f"Error revoking authentication: {e}"
            logger.error(error_msg)
            return False, error_msg
    
    def get_gmail_service(self):
        """Get authenticated Gmail service"""
        if not self.is_authenticated():
            raise Exception("Not authenticated. Call authenticate() first.")
        return self.gmail_service
    
    def get_sheets_service(self):
        """Get authenticated Google Sheets service"""
        if not self.is_authenticated():
            raise Exception("Not authenticated. Call authenticate() first.")
        return self.sheets_service