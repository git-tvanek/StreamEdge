#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Services module initialization

This module provides service classes that handle the core business logic of the application.
"""
from flask import Flask, current_app
import logging
import os

# Import all services
from Services.auth_service import AuthService
from Services.channel_service import ChannelService
from Services.stream_service import StreamService
from Services.epg_service import EPGService
from Services.device_service import DeviceService
from Services.playlist_service import PlaylistService
from Services.catchup_service import CatchupService
from Services.client_service import ClientService

logger = logging.getLogger(__name__)


# Lazy load the client service
def get_magenta_tv_service():
    """
    Get an instance of the MagentaTV client service

    Returns:
        ClientService: An instance of the MagentaTV client service
    """
    try:
        return ClientService(
            username=current_app.config["USERNAME"],
            password=current_app.config["PASSWORD"],
            language=current_app.config["LANGUAGE"],
            quality=current_app.config["QUALITY"]
        )
    except Exception as e:
        logger.error(f"Failed to initialize MagentaTV client service: {e}")
        return None


def create_app(config_file=None):
    """
    Factory function that creates the Flask application

    Args:
        config_file (str, optional): Path to configuration file

    Returns:
        Flask: Configured Flask application instance
    """
    # Create app instance
    app = Flask(__name__)

    # Load default configuration
    from config import load_config
    app_config = load_config(config_file)
    app.config.update(app_config)

    # Ensure data directory exists
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)

    # Initialize logging
    logging.basicConfig(
        level=logging.DEBUG if app.config["DEBUG"] else logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize cache
    from cache import init_cache
    with app.app_context():
        init_cache()

    # Register blueprints
    from api import api_bp
    app.register_blueprint(api_bp)

    logger.info(f"Application initialized with configuration: {app.config['LANGUAGE']}")
    return app


# Export all services
__all__ = [
    'AuthService',
    'ChannelService',
    'StreamService',
    'EPGService',
    'DeviceService',
    'PlaylistService',
    'CatchupService',
    'ClientService',
    'get_magenta_tv_service',
    'create_app'
]