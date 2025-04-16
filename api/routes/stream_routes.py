#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API endpointy pro streamy

Tyto endpointy poskytují přístup ke streamům živého vysílání a proxy pro streamy.
"""
import logging
import requests
from flask import jsonify, request, redirect, Response

from api.helpers import get_api, server_url_from_request
from cache import get_from_cache

logger = logging.getLogger(__name__)


def register_routes(api_blueprint):
    """
    Registrace routes pro streamy

    Args:
        api_blueprint (Blueprint): Flask blueprint pro API
    """

    # Stream endpoint - získání URL streamu pro kanál
    @api_blueprint.route('/stream/<channel_id>')
    def stream(channel_id):
        """
        Získání stream URL pro kanál

        S parametrem redirect=1 přesměruje přímo na stream

        Args:
            channel_id (str): ID kanálu

        Returns:
            dict/redirect: Informace o streamu nebo přesměrování na stream
        """
        client = get_api()
        if client is None:
            return jsonify({"success": False, "message": "API is not initialized"}), 500

        # Získání stream info s použitím cache
        stream_key = f"stream_{channel_id}"
        stream_info = get_from_cache(stream_key, client.get_live_stream_url, channel_id)

        if not stream_info:
            return jsonify({"success": False, "message": "Failed to get stream"}), 404

        # Přesměrování na stream nebo vrácení info
        if request.args.get('redirect', '0') == '1':
            return redirect(stream_info["url"])
        else:
            return jsonify({
                "success": True,
                "stream": stream_info
            })

    # Proxy endpoint - proxy pro streamy
    @api_blueprint.route('/proxy/<path:url>')
    def proxy(url):
        """
        Proxy pro přesměrování požadavků na stream

        Args:
            url (str): URL streamu

        Returns:
            Response: Odpověď ze streamu
        """
        if not url.startswith('http'):
            url = 'https://' + url

        # Získání parametrů z požadavku
        headers = {}
        for key, value in request.headers.items():
            if key.lower() not in ['host', 'content-length', 'connection']:
                headers[key] = value

        # Vytvoření požadavku
        try:
            response = requests.get(url, headers=headers, stream=True)

            # Vytvoření odpovědi
            flask_response = Response(
                response=response.iter_content(chunk_size=1024),
                status=response.status_code,
                headers=dict(response.headers)
            )

            return flask_response
        except Exception as e:
            logger.error(f"Error in proxy request: {e}")
            return jsonify({"success": False, "message": f"Error in proxy request: {str(e)}"}), 500

    # HLS manifest endpoint - úprava HLS manifestu pro lepší kompatibilitu
    @api_blueprint.route('/manifest/<path:url>')
    def hls_manifest(url):
        """
        Získání a úprava HLS manifestu

        Args:
            url (str): URL manifestu

        Returns:
            Response: Upravený manifest
        """
        if not url.startswith('http'):
            url = 'https://' + url

        # Získání parametrů z požadavku
        headers = {}
        for key, value in request.headers.items():
            if key.lower() not in ['host', 'content-length', 'connection']:
                headers[key] = value

        # Base URL pro relativní cesty
        base_url = "/".join(url.split('/')[:-1])
        server_url = server_url_from_request()

        try:
            # Získání manifestu
            response = requests.get(url, headers=headers)
            manifest = response.text

            # Ověření, že se jedná o HLS manifest
            if not manifest.startswith('#EXTM3U'):
                return Response(manifest, mimetype=response.headers.get('Content-Type', 'text/plain'))

            # Úprava URL v manifestu (nahrazení relativních cest za absolutní)
            lines = manifest.splitlines()
            modified_lines = []

            for line in lines:
                if line.startswith('#'):
                    # Komentáře a tagy necháme beze změny
                    modified_lines.append(line)
                elif line.strip():
                    # URL řádky - zkontrolujeme, zda jsou absolutní nebo relativní
                    if line.startswith('http'):
                        # Absolutní URL přesměrujeme přes proxy
                        modified_lines.append(f"{server_url}/api/proxy/{line}")
                    else:
                        # Relativní URL doplníme o base_url a přesměrujeme přes proxy
                        full_url = f"{base_url}/{line}" if not line.startswith('/') else f"{base_url}{line}"
                        modified_lines.append(f"{server_url}/api/proxy/{full_url}")
                else:
                    # Prázdné řádky zachováme
                    modified_lines.append(line)

            # Vrácení upraveného manifestu
            modified_manifest = '\n'.join(modified_lines)
            return Response(modified_manifest, mimetype='application/vnd.apple.mpegurl')