#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API routes initialization

Import a registrace všech API routes pro MagentaTV backend
"""
import logging

logger = logging.getLogger(__name__)


def register_routes(api_blueprint):
    """
    Registrace všech routes pro API blueprint

    Args:
        api_blueprint (Blueprint): Flask blueprint pro API
    """
    # Import jednotlivých route modulů
    from api.routes import (
        auth_routes,
        channel_routes,
        stream_routes,
        epg_routes,
        catchup_routes,
        device_routes,
        playlist_routes,
        system_routes
    )

    # Registrace všech routes v blueprintu
    auth_routes.register_routes(api_blueprint)
    channel_routes.register_routes(api_blueprint)
    stream_routes.register_routes(api_blueprint)
    epg_routes.register_routes(api_blueprint)
    catchup_routes.register_routes(api_blueprint)
    device_routes.register_routes(api_blueprint)
    playlist_routes.register_routes(api_blueprint)
    system_routes.register_routes(api_blueprint)

    logger.info("Všechny API routes byly zaregistrovány")