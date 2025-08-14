"""
Web interface package for Temperature Monitor
Contains Flask application and web UI components
"""

from .app import create_app

__all__ = ['create_app']