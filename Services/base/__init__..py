#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Základní třídy pro služby MagentaTV/MagioTV

Tento modul poskytuje základní třídy pro všechny služby v aplikaci.
"""

from Services.base.service_base import ServiceBase
from Services.base.authenticated_service_base import AuthenticatedServiceBase

# Export tříd
__all__ = ['ServiceBase', 'AuthenticatedServiceBase']