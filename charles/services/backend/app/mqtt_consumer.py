"""
CHARLES — MQTT Consumer.

Écoute MQTT topic `bloc/+/vitals` et forward vers le handler async.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from typing import Any, Callable, Coroutine

import paho.mqtt.client as mqtt

logger = logging.getLogger("charles.mqtt")


class MQTTConsumer:
    """Thread-safe MQTT consumer qui bridge vers asyncio."""

    def __init__(
        self,
        broker: str,
        port: int,
        on_message: Callable[[str, dict], Coroutine[Any, Any, None]],
        topics: list[str] | None = None,
        username: str = "",
        password: str = "",
    ):
        self.broker = broker
        self.port = port
        self.on_message = on_message
        self.username = username
        self.password = password
        self.topics = topics or [
            "bloc/+/vitals",
            "bloc/+/ventilator",
            "bloc/+/bis",
            "bloc/+/aivoc",
            "bloc/+/full",
        ]
        self._client: mqtt.Client | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self):
        self._loop = asyncio.get_event_loop()
        self._client = mqtt.Client(
            client_id="charles-backend",
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        )
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        self._client.reconnect_delay_set(min_delay=1, max_delay=30)
        if self.username:
            self._client.username_pw_set(self.username, self.password)
        for attempt in range(1, 11):
            try:
                self._client.connect(self.broker, self.port, keepalive=60)
                break
            except Exception as e:
                logger.warning("MQTT connect attempt %d/10 failed: %s — retry in 5s", attempt, e)
                time.sleep(5)
        self._client.loop_start()

    def publish(self, topic: str, payload: dict):
        """Publie un message JSON sur un topic MQTT."""
        if self._client:
            self._client.publish(topic, json.dumps(payload), qos=1)
            logger.info("MQTT published to %s", topic)

    def stop(self):
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        logger.info("MQTT connected (rc=%s)", reason_code)
        for topic in self.topics:
            client.subscribe(topic, qos=1)
            logger.info("Subscribed to %s", topic)

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties=None):
        if reason_code != 0:
            logger.warning("MQTT disconnected unexpectedly (rc=%s) — reconnexion automatique en cours", reason_code)

    def _on_message(self, client, userdata, msg: mqtt.MQTTMessage):
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.warning("Bad MQTT payload on %s: %s", msg.topic, e)
            return

        if self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.on_message(msg.topic, payload),
                self._loop,
            )
