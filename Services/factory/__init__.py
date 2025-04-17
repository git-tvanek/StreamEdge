#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Factory modul pro vytváření instancí služeb MagentaTV/MagioTV

Tento modul poskytuje tovární metody pro vytváření instancí služeb
s jejich správnou konfigurací a propojením.
"""

from Services.factory.service_factory import (
    ServiceFactory,
    get_magenta_tv_service,
    get_config_service,
    get_cache_service,
    get_session_service,
    get_system_service,
    initialize_services
)

# Export tříd a funkcí
__all__ = [
    'ServiceFactory',
    'get_magenta_tv_service',
    'get_config_service',
    'get_cache_service',
    'get_session_service',
    'get_system_service',
    'initialize_services'
]