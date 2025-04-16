#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API endpointy pro kanály

Tyto endpointy poskytují přístup k seznamu kanálů, detailu kanálu a skupinám kanálů.
"""
import logging
from flask import jsonify, request

from api.helpers import get_api
from cache import get_from_cache

logger = logging.getLogger(__name__)


def register_routes(api_blueprint):
    """
    Registrace routes pro kanály

    Args:
        api_blueprint (Blueprint): Flask blueprint pro API
    """

    # Channels endpoint - seznam všech kanálů
    @api_blueprint.route('/channels')
    def channels():
        """
        Získání seznamu kanálů

        Returns:
            dict: Seznam kanálů nebo chybová zpráva
        """
        client = get_api()
        if client is None:
            return jsonify({"success": False, "message": "API is not initialized"}), 500

        # Získání kanálů s použitím cache
        channels_data = get_from_cache("channels", client.get_channels)

        if not channels_data:
            return jsonify({"success": False, "message": "Failed to get channels list"}), 500

        return jsonify({
            "success": True,
            "channels": channels_data
        })

    # Channel detail endpoint - detail konkrétního kanálu
    @api_blueprint.route('/channels/<channel_id>')
    def channel_detail(channel_id):
        """
        Získání detailu kanálu

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict: Detail kanálu nebo chybová zpráva
        """
        client = get_api()
        if client is None:
            return jsonify({"success": False, "message": "API is not initialized"}), 500

        # Získání kanálu s použitím cache
        channel_key = f"channel_{channel_id}"
        channel_data = get_from_cache(channel_key, client.get_channel, channel_id)

        if not channel_data:
            return jsonify({"success": False, "message": f"Channel with ID {channel_id} not found"}), 404

        return jsonify({
            "success": True,
            "channel": channel_data
        })

    # Channel groups endpoint - seznam skupin kanálů
    @api_blueprint.route('/channel-groups')
    def channel_groups():
        """
        Získání seznamu skupin kanálů

        Returns:
            dict: Seznam skupin kanálů nebo chybová zpráva
        """
        client = get_api()
        if client is None:
            return jsonify({"success": False, "message": "API is not initialized"}), 500

        # Získání skupin kanálů s použitím cache
        groups_data = get_from_cache("channel_groups", client.get_channel_groups)

        if groups_data is None:
            return jsonify({"success": False, "message": "Failed to get channel groups"}), 500

        return jsonify({
            "success": True,
            "groups": groups_data
        })

    # Channels by group endpoint - filtrování kanálů podle skupiny
    @api_blueprint.route('/channels/group/<group_name>')
    def channels_by_group(group_name):
        """
        Získání kanálů podle skupiny

        Args:
            group_name (str): Název skupiny

        Returns:
            dict: Seznam kanálů ve skupině nebo chybová zpráva
        """
        client = get_api()
        if client is None:
            return jsonify({"success": False, "message": "API is not initialized"}), 500

        # Získání všech kanálů
        all_channels = get_from_cache("channels", client.get_channels)

        if not all_channels:
            return jsonify({"success": False, "message": "Failed to get channels list"}), 500

        # Filtrování kanálů podle skupiny
        filtered_channels = [
            channel for channel in all_channels
            if channel.get("group", "").lower() == group_name.lower()
        ]

        return jsonify({
            "success": True,
            "group": group_name,
            "channels": filtered_channels,
            "count": len(filtered_channels)
        })