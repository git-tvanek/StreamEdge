#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API module initialization
"""
from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

# Create blueprint
api_bp = Blueprint('api', __name__, url_prefix='/api')

# Register routes
from api.routes import register_routes
register_routes(api_bp)

logger.info("API modul inicializován")