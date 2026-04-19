"""Wyze Camera integration for Home Assistant."""

import base64
import json
import asyncio
from dataclasses import asdict
from collections.abc import Callable
from typing import Any
import logging
import uuid
import re

from homeassistant.config_entries import ConfigEntry
from homeassistant.components.camera import Camera as CameraEntity, CameraEntityFeature
from homeassistant.components.camera.webrtc import (
    WebRTCClientConfiguration,
    WebRTCSendMessage,
    WebRTCAnswer,
    WebRTCCandidate,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.ssl import get_default_context
from propcache.api import cached_property
from webrtc_models import RTCConfiguration, RTCIceCandidateInit, RTCIceServer
from websockets.asyncio.client import connect as websocket_connect
from wyzeapy import Wyzeapy, CameraService
from wyzeapy.services.camera_service import Camera

from .const import CAMERA_UPDATED, CONF_CLIENT, DOMAIN
from .token_manager import token_exception_handler

_LOGGER = logging.getLogger(__name__)


@token_exception_handler
async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: Callable[[list[Any], bool], None],
) -> None:
    """This function sets up the config entry.

    :param hass: The Home Assistant Instance
    :param config_entry: The current config entry
    :param async_add_entities: This function adds entities to the config entry
    :return:
    """

    _LOGGER.debug("Creating new Wyze camera component")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service
    camera_devices = await camera_service.get_cameras()

    # Create a camera entity for each camera device
    cameras = []
    for device in camera_devices:
        # Update the device to get its zones
        device = await camera_service.update(device)
        cameras.extend([WyzeCamera(camera_service, device)])

    for camera in cameras:
        # Pre-seed the ICE server config by fetching it during setup, so the frontend can collect ICE servers before the offer
        try:
            await camera.config_fetch()
        except Exception as e:
            # Don't block startup if the config fetch fails, but log the error
            _LOGGER.warning(
                "Error fetching WebRTC session configuration for camera %s: %s",
                camera.name,
                e,
            )

    _LOGGER.debug("Wyze camera component setup complete")
    async_add_entities(cameras, True)


class WyzeCamera(CameraEntity):
    """Representation of a Wyze Camera."""

    def __init__(self, camera_service: CameraService, camera: Camera):
        """Initialize the camera."""
        super().__init__()
        self._camera_service = camera_service
        self._camera = camera
        self.name = camera.nickname
        self._attr_unique_id = camera.mac
        self.brand = "Wyze"
        self.model = camera.product_model
        self.supported_features = CameraEntityFeature.STREAM
        self._webrtc_provider = None
        self.sessions: dict[str, WyzeCameraWebRTCSession] = {}
        self._pending_candidates: dict[str, list[RTCIceCandidateInit]] = {}
        # Always holds an in-flight Task[dict] for the next config fetch.
        # _async_get_webrtc_client_configuration reads the result when ready;
        # async_handle_async_webrtc_offer awaits it to guarantee a fresh config.
        self._cached_config: dict | None = None
        self._config_task: asyncio.Task | None = None

    async def config_fetch(self) -> None:
        """Fetch the WebRTC session configuration for this camera and cache it for future use."""
        self._cached_config = await self._camera_service.get_stream_info(self._camera)
        _LOGGER.debug(
            "Initial fetch of WebRTC session configuration complete for camera %s",
            self.name,
        )

    @cached_property
    def device_info(self) -> DeviceInfo | None:
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self._camera.mac)},
            "name": self._camera.nickname,
            "manufacturer": "WyzeLabs",
            "model": self._camera.product_model,
        }

    @property
    def available(self) -> bool:
        """Return if the camera is available."""
        return self._camera.available

    @cached_property
    def is_streaming(self) -> bool:
        """Return True if the camera is currently streaming."""
        return self._camera.on

    @callback
    def handle_camera_update(self, camera: Camera) -> None:
        """Update the camera whenever there is an update."""
        self._camera = camera
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Listen for camera updates."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{CAMERA_UPDATED}-{self._camera.mac}",
                self.handle_camera_update,
            )
        )

    @property
    def is_on(self) -> bool:
        """Return True if the camera is currently on."""
        return self._camera.on

    async def async_turn_on(self) -> None:
        """Turn the camera on."""
        await self._camera_service.turn_on(self._camera)

    async def async_turn_off(self) -> None:
        """Turn the camera off."""
        await self._camera_service.turn_off(self._camera)

    async def async_disable_motion_detection(self) -> None:
        """Disable motion detection."""
        await self._camera_service.turn_off_motion_detection(self._camera)

    async def async_enable_motion_detection(self) -> None:
        """Enable motion detection."""
        await self._camera_service.turn_on_motion_detection(self._camera)

    @property
    def motion_detection_enabled(self) -> bool | None:
        """Return True if motion detection is enabled, False if disabled, or None if unknown/not supported."""
        motion = getattr(self._camera, "motion", None)
        if isinstance(motion, bool):
            return motion
        # Some Wyze camera models / API responses don't expose motion state.
        # Return None so HA omits/marks the attribute as unknown instead of crashing.
        return None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image.
        Currently not implemented"""
        return None

    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        """Return the WebRTC client configuration for this camera, including ICE servers."""
        # This shouldn't happen, but throw an error if we don't have a config ready yet
        if self._cached_config is None:
            raise HomeAssistantError("WebRTC session configuration not available yet")

        config = self._cached_config

        ice_servers = []
        for server in config.get("ice_servers", []):
            _LOGGER.debug("Adding ICE server for camera %s: %s", self.name, server)
            ice_servers.append(
                RTCIceServer.from_dict(
                    {
                        "urls": server["url"],
                        "username": server["username"],
                        "credential": server["credential"],
                    }
                )
            )

        _LOGGER.debug("ICE servers for camera %s: %s", self.name, ice_servers)
        configuration = RTCConfiguration(ice_servers=ice_servers)
        return WebRTCClientConfiguration(
            configuration=configuration, data_channel="data"
        )

    async def async_handle_async_webrtc_offer(
        self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage
    ) -> None:
        """Handle an incoming WebRTC offer from the frontend."""
        _LOGGER.debug(
            "Handling WebRTC offer for camera %s with session ID %s",
            self.name,
            session_id,
        )

        # Always fetch a truly fresh config so the signaling URL and ICE servers
        # are never stale — KVS signed URLs are single-use and short-lived.
        config = await self._camera_service.get_stream_info(self._camera)

        # Update cached config with the new ICE servers
        self._cached_config = config
        _LOGGER.debug("Fresh config for offer on camera %s: %s", self.name, config)

        self.sessions[session_id] = WyzeCameraWebRTCSession(
            session_id, self, send_message, config
        )
        await self.sessions[session_id].send_offer(offer_sdp)

        pending = self._pending_candidates.pop(session_id, None)
        if pending:
            _LOGGER.debug(
                "Flushing %d buffered ICE candidates for camera %s session %s",
                len(pending),
                self.name,
                session_id,
            )
            for cand in pending:
                await self.sessions[session_id].send_candidate(cand)

    async def async_on_webrtc_candidate(
        self, session_id: str, candidate: RTCIceCandidateInit
    ) -> None:
        """Handle an incoming ICE candidate for a WebRTC session."""
        if session_id not in self.sessions:
            self._pending_candidates.setdefault(session_id, []).append(candidate)
            _LOGGER.debug(
                "Buffered ICE candidate for camera %s session %s (session not ready yet)",
                self.name,
                session_id,
            )
            return

        await self.sessions[session_id].send_candidate(candidate)

    def close_webrtc_session(self, session_id: str) -> None:
        """Close a WebRTC session and clean up resources."""
        _LOGGER.debug("Closing WebRTC session %s", session_id)
        self._pending_candidates.pop(session_id, None)
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.close_connection()
            del self.sessions[session_id]


class WyzeCameraWebRTCSession:
    """Represents a WebRTC session for a Wyze camera."""

    def __init__(
        self,
        session_id: str,
        camera: WyzeCamera,
        callback: WebRTCSendMessage,
        config: dict,
    ):
        self.session_id = session_id
        self.camera = camera
        self.websocket = None  # This will hold the WebSocket connection
        self.camera_service = None
        self.callback = callback
        self.close = None
        self.lock = asyncio.Lock()
        self.task = None
        self.config = config
        self.sdp_offer = None
        self.sdp_answer = None
        # Set once connect() succeeds; send_candidate waits on this instead of reconnecting
        self._connected = asyncio.Event()

    async def connect(self):
        """Establish the WebSocket connection to the KVS signaling URL.
        This is called lazily from send_offer() to ensure we have the latest config
        and don't connect too early before the offer is ready."""
        # The signaling_url from get_stream_info() is often *double*-percent-encoded
        # (e.g. "%253A" instead of "%3A"). We must NOT fully URL-decode it because
        # that can change SigV4 canonical encoding and make KVS reject the handshake.
        # Instead, only "undouble" percent-escapes by converting "%25xx" -> "%xx",
        # leaving "%3A", "%2F", etc. intact.
        signaling_url = self.config["signaling_url"]
        for _ in range(3):
            if "%25" not in signaling_url:
                break
            signaling_url = signaling_url.replace("%25", "%")
        self.websocket = await websocket_connect(
            signaling_url, ssl=get_default_context(), logger=_LOGGER
        )
        _LOGGER.debug(
            "WebSocket connection established for camera %s with session ID %s",
            self.camera.name,
            self.session_id,
        )
        self._connected.set()
        asyncio.create_task(self.run_loop())

    async def send_offer(self, offer_sdp: str):
        """Send an SDP offer to the Kinesis Video Streams signaling channel."""
        async with self.lock:
            if self.websocket is None:
                _LOGGER.debug("Connecting to websocket from send_offer")
                await self.connect()
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")
        # Create an offer for Kinesis
        self.sdp_offer = offer_sdp
        offer = {"type": "offer", "sdp": offer_sdp}
        payload = {
            "action": "SDP_OFFER",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": base64.b64encode(
                json.dumps(offer, separators=(",", ":")).encode()
            ).decode(),
            "correlationId": str(uuid.uuid4()),
        }
        str_payload = json.dumps(payload)
        _LOGGER.debug(
            "Sending SDP offer for camera %s with session ID %s, %s",
            self.camera.name,
            self.session_id,
            str_payload,
        )
        await self.websocket.send(str_payload)

    async def send_candidate(self, candidate: RTCIceCandidateInit):
        """Send an ICE candidate to the Kinesis Video Streams signaling channel."""
        # Take RTCIceCandidateInit, convert it to the format in the messagePayload above, and send it to the client using the callback
        # Wait for send_offer to establish the connection — never reconnect (KVS URLs are single-use)
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
        except asyncio.TimeoutError as exc:
            raise ConnectionError(
                "WebSocket connection not established within timeout"
            ) from exc
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")
        candidate_dict = asdict(candidate)
        candidate_payload = {
            "candidate": candidate_dict["candidate"],
            "sdpMid": candidate_dict["sdp_mid"],
            "sdpMLineIndex": candidate_dict["sdp_m_line_index"],
            "usernameFragment": candidate_dict["user_fragment"],
        }
        match = re.search(r"ufrag (\w{4})", candidate_payload["candidate"])
        if match is not None:
            candidate_payload["usernameFragment"] = match.group(1)
        payload = {
            "action": "ICE_CANDIDATE",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": base64.b64encode(
                json.dumps(candidate_payload, separators=(",", ":")).encode()
            ).decode(),
        }
        str_payload = json.dumps(payload)
        _LOGGER.debug(
            "Sending ICE candidate for camera %s with session ID %s: %s",
            self.camera.name,
            self.session_id,
            str_payload,
        )
        await self.websocket.send(str_payload)

    def close_connection(self):
        """Close the WebSocket connection to the Kinesis Video Streams signaling channel."""
        if self.close is not None:
            self.close()

    def force_correct_sdp_answer(self) -> None:
        """Force the sdp response to have the valid answer.

        The Kinesis WebRTC Stream responses to certain offers do not
        follow the spec defined in https://www.ietf.org/rfc/rfc3264.txt
        An offer of recvonly must be answered with sendonly or inactive.
        """
        _LOGGER.debug("Attempt to fix sdp answer...")
        if isinstance(self.sdp_answer, str) and isinstance(self.sdp_offer, str):
            sdp_kinds = ["audio", "video", "application"]
            sdp_directions = ["sendrecv", "sendonly", "recvonly", "inactive"]
            sdp_pattern = (
                "m=(?P<kind>{})(.|\n)+?a=(?P<direction>{})(\r|\n|\r\n)".format(
                    "|".join(sdp_kinds), "|".join(sdp_directions)
                )
            )

            sdp_direction_offers = re.finditer(sdp_pattern, self.sdp_offer)

            for offer in sdp_direction_offers:
                sdp_answers = re.finditer(sdp_pattern, self.sdp_answer)
                for answer in sdp_answers:
                    if (
                        offer.group("kind") == answer.group("kind")
                        and offer.group("direction") == "recvonly"
                        and answer.group("direction") == "sendrecv"
                    ):
                        correct_answer = re.sub(
                            "a=sendrecv", "a=sendonly", answer.group(0)
                        )
                        _LOGGER.debug("Replacing answer with: %s", str(correct_answer))
                        self.sdp_answer = self.sdp_answer.replace(
                            answer.group(0), correct_answer
                        )

    async def run_loop(self):
        """Listen for messages from the Kinesis Video Streams signaling channel and handle them appropriately."""
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")

        loop = asyncio.get_running_loop()

        def close():
            if self.websocket is not None:
                return loop.create_task(self.websocket.close())
            return None

        self.close = close
        _LOGGER.debug(
            "run_loop starting for camera %s session %s",
            self.camera.name,
            self.session_id,
        )
        try:
            async for message in self.websocket:
                if len(message) == 0:
                    _LOGGER.debug(
                        "Received empty message (type=%s) for camera %s session %s",
                        type(message).__name__,
                        self.camera.name,
                        self.session_id,
                    )
                    continue
                _LOGGER.debug(
                    "Received message for camera %s with session ID %s: %s",
                    self.camera.name,
                    self.session_id,
                    message,
                )
                try:
                    data = json.loads(message)
                except json.JSONDecodeError as e:
                    _LOGGER.error(
                        "Failed to decode JSON message for camera %s with session ID %s: %s",
                        self.camera.name,
                        self.session_id,
                        e,
                    )
                    continue
                match data.get("messageType"):
                    case "ICE_CANDIDATE":
                        # Decode messagePayload (base64 JSON) → RTCIceCandidateInit → WebRTCCandidate
                        # KVS uses camelCase keys; map them to RTCIceCandidateInit's snake_case fields
                        candidate_str = base64.b64decode(
                            data["messagePayload"]
                        ).decode()
                        candidate_data = json.loads(candidate_str)
                        rtccandidate = RTCIceCandidateInit(
                            candidate=candidate_data["candidate"],
                            sdp_mid=candidate_data.get("sdpMid"),
                            sdp_m_line_index=candidate_data.get("sdpMLineIndex"),
                            user_fragment=candidate_data.get("usernameFragment"),
                        )
                        self.callback(WebRTCCandidate(candidate=rtccandidate))
                    case "SDP_ANSWER":
                        # Decode messagePayload (base64 JSON with "type"/"sdp" keys) → extract sdp string
                        answer_str = base64.b64decode(data["messagePayload"]).decode()
                        try:
                            answer_obj = json.loads(answer_str)
                            sdp = answer_obj.get("sdp", answer_str)
                        except json.JSONDecodeError:
                            sdp = answer_str
                        self.sdp_answer = sdp
                        self.force_correct_sdp_answer()
                        self.callback(WebRTCAnswer(answer=self.sdp_answer))
                    case "STATUS_RESPONSE" | "GO_AWAY" | "RECONNECT_ICE_SERVER":
                        _LOGGER.debug(
                            "KVS control message '%s' for session %s: %s",
                            data.get("messageType"),
                            self.session_id,
                            data,
                        )
                    case other:
                        _LOGGER.debug(
                            "Unhandled KVS message type '%s' for session %s: %s",
                            other,
                            self.session_id,
                            data,
                        )
        except Exception as e:
            _LOGGER.error(
                "run_loop error for camera %s session %s: %s",
                self.camera.name,
                self.session_id,
                e,
                exc_info=True,
            )
        _LOGGER.debug(
            "run_loop exited for camera %s session %s",
            self.camera.name,
            self.session_id,
        )
