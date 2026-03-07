import base64
import json
import asyncio
from dataclasses import asdict
from collections.abc import Callable
from typing import Any
import logging
import uuid
from urllib.parse import unquote
import re


from webrtc_models import RTCConfiguration, RTCIceServer
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.camera import Camera as CameraEntity, CameraEntityFeature
from homeassistant.components.camera.webrtc import WebRTCClientConfiguration, WebRTCSendMessage, WebRTCAnswer, WebRTCCandidate
from webrtc_models import RTCIceCandidateInit
from wyzeapy import Wyzeapy, CameraService
from wyzeapy.services.camera_service import Camera
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from websockets.asyncio.client import connect as websocket_connect

from .const import CONF_CLIENT, DOMAIN
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

    _LOGGER.debug("""Creating new Wyze camera component""")
    client: Wyzeapy = hass.data[DOMAIN][config_entry.entry_id][CONF_CLIENT]
    camera_service = await client.camera_service
    camera_devices = await camera_service.get_cameras()

    # Create a camera entity for each camera device
    cameras = []
    for device in camera_devices:
        # Update the device to get its zones
        device = await camera_service.update(device)
        cameras.extend(
            [
                WyzeCamera(camera_service, device)
            ]
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
        self._attr_name = camera.nickname
        self._attr_unique_id = camera.mac
        self.brand = "Wyze"
        self.model = camera.product_model
        self.supported_features = CameraEntityFeature.STREAM
        self._webrtc_provider = None
        self.sessions: dict[str, WyzeCameraWebRTCSession] = {}
        # Always holds an in-flight Task[dict] for the next config fetch.
        # _async_get_webrtc_client_configuration reads the result when ready;
        # async_handle_async_webrtc_offer awaits it to guarantee a fresh config.
        self._config_task: asyncio.Task | None = None
        self._schedule_config_fetch()

    def _schedule_config_fetch(self) -> None:
        """Start a background fetch of a fresh KVS stream config."""
        self._config_task = asyncio.create_task(
            self._camera_service.get_stream_info(self._camera)
        )
        self._config_task.add_done_callback(self._on_config_fetched)

    def _on_config_fetched(self, task: asyncio.Task) -> None:
        if task.exception():
            _LOGGER.error(
                f"Failed to fetch WebRTC config for {self._attr_name}: {task.exception()}"
            )
        else:
            _LOGGER.debug(
                f"Fetched new WebRTC session configuration for camera {self._attr_name}: {task.result()}"
            )

    @property
    def is_streaming(self) -> bool:
        return self._camera.on

    @property
    def is_on(self) -> bool:
        return self._camera.on

    @property
    def motion_detection_enabled(self) -> bool:
        if isinstance(self._camera.motion, bool):
            return self._camera.motion
        raise NotImplementedError

    @property
    def is_recording(self) -> bool:
        return True

    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        # If the prefetch task isn't done yet, tell HA to retry shortly.
        if self._config_task is None or not self._config_task.done():
            if self._config_task is None:
                self._schedule_config_fetch()
            raise HomeAssistantError(
                "WebRTC session configuration not available, fetching new configuration"
            )

        # Task is done — pull the result and immediately kick off a fresh fetch
        # so the *next* call to this method (or the next stream open) is pre-warmed.
        try:
            config = self._config_task.result()
        except Exception as e:
            self._schedule_config_fetch()
            raise HomeAssistantError(f"Failed to get WebRTC config: {e}") from e

        # Kick off fresh fetch for next time (the current config will be consumed
        # by async_handle_async_webrtc_offer which awaits _config_task directly).
        self._schedule_config_fetch()

        _LOGGER.debug(f"WebRTC session configuration for camera {self._attr_name}: {config}")
        ice_servers = []
        for server in config.get("ice_servers", []):
            _LOGGER.debug(f"Adding ICE server for camera {self._attr_name}: {server}")
            ice_servers.append(RTCIceServer.from_dict({
                "urls": server['url'],
                "username": server["username"],
                "credential": server["credential"],
            }))

        _LOGGER.debug(f"ICE servers for camera {self._attr_name}: {ice_servers}")
        configuration = RTCConfiguration(ice_servers=ice_servers)
        return WebRTCClientConfiguration(configuration=configuration, data_channel="data")

    async def async_handle_async_webrtc_offer(self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage) -> None:
        _LOGGER.debug(f"Handling WebRTC offer for camera {self._attr_name} with session ID {session_id}")

        # Always fetch a truly fresh config so the signaling URL and ICE servers
        # are never stale — KVS signed URLs are single-use and short-lived.
        config = await self._camera_service.get_stream_info(self._camera)
        _LOGGER.debug(f"Fresh config for offer on camera {self._attr_name}: {config}")

        # Pre-warm the next call to _async_get_webrtc_client_configuration.
        self._schedule_config_fetch()

        self.sessions[session_id] = WyzeCameraWebRTCSession(session_id, self, send_message, config)
        await self.sessions[session_id].send_offer(offer_sdp)

    async def async_on_webrtc_candidate(self, session_id: str, candidate: RTCIceCandidateInit) -> None:
        # Implement the logic to handle the WebRTC candidate and send it to the camera's WebRTC session
        if session_id not in self.sessions:
            raise ValueError("Session ID not found")

        await self.sessions[session_id].send_candidate(candidate)

    def async_close_session(self, session_id: str) -> None:
        _LOGGER.debug(f"Closing webRTC session {session_id}")
        # Implement the logic to close the WebRTC session
        if session_id in self.sessions:
            session = self.sessions[session_id]
            session.close_connection()
            del self.sessions[session_id]


class WyzeCameraWebRTCSession:
    """Represents a WebRTC session for a Wyze camera."""
    def __init__(self, session_id: str, camera: WyzeCamera, callback: WebRTCSendMessage, config: dict):
        self.session_id = session_id
        self.camera = camera
        self.websocket = None  # This will hold the WebSocket connection
        self.camera_service = None
        self.callback = callback
        self.close = None
        self.lock = asyncio.Lock()
        self.task = None
        self.config = config
        # Set once connect() succeeds; send_candidate waits on this instead of reconnecting
        self._connected = asyncio.Event()

    async def connect(self):
        # The signaling_url from get_stream_info() is double-encoded (%253A).
        # A single unquote produces %3A, which matches the browser's working URL format
        # and preserves the SigV4 percent-encoding that AWS signature verification requires.
        signaling_url = unquote(self.config['signaling_url'])
        self.websocket = await websocket_connect(signaling_url, logger=_LOGGER)
        _LOGGER.debug(f"WebSocket connection established for camera {self.camera._attr_name} with session ID {self.session_id}")
        self._connected.set()
        asyncio.create_task(self.run_loop())

    async def send_offer(self, offer_sdp: str):
        async with self.lock:
            if self.websocket is None:
                _LOGGER.debug("Connecting to websocket from send_offer")
                await self.connect()
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")
        # Create an offer for Kinesis
        offer = {
                "type": "offer",
                "sdp": offer_sdp
                }
        payload = {
            "action": "SDP_OFFER",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": base64.b64encode(json.dumps(offer, separators=(',', ':')).encode()).decode(),
            "correlationId": str(uuid.uuid4())
        }
        str_payload = json.dumps(payload)
        _LOGGER.debug(f"Sending SDP offer for camera {self.camera._attr_name} with session ID {self.session_id}, {str_payload}")
        await self.websocket.send(str_payload)

    async def send_candidate(self, candidate: RTCIceCandidateInit):
        """{
            "action": "ICE_CANDIDATE",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": "eyJjYW5kaWRhdGUiOiJjYW5kaWRhdGU6MzI5NzAwNjk2IDEgdWRwIDE2Nzc3MzIwOTUgMjYwMToyNDY6NWI3ZjpiMTAxOjoxMGU4IDQ4OTE4IHR5cCBzcmZseCByYWRkciA6OiBycG9ydCAwIGdlbmVyYXRpb24gMCB1ZnJhZyBJZ0M1IG5ldHdvcmstY29zdCA5OTkiLCJzZHBNaWQiOiIxIiwic2RwTUxpbmVJbmRleCI6MSwidXNlcm5hbWVGcmFnbWVudCI6IklnQzUifQ=="
        }"""
        # Take RTCIceCandidateInit, convert it to the format in the messagePayload above, and send it to the client using the callback
        # Wait for send_offer to establish the connection — never reconnect (KVS URLs are single-use)
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise ConnectionError("WebSocket connection not established within timeout")
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")
        candidate_dict = asdict(candidate)
        candidate_payload = {
            "candidate": candidate_dict["candidate"],
            "sdpMid": candidate_dict['sdp_mid'],
            "sdpMLineIndex": candidate_dict["sdp_m_line_index"],
            "usernameFragment": candidate_dict["user_fragment"]
        }
        match = re.search(r"ufrag (\w{4})", candidate_payload["candidate"])
        if match is not None:
            candidate_payload['usernameFragment'] = match.group(1)
        payload = {
            "action": "ICE_CANDIDATE",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": base64.b64encode(json.dumps(candidate_payload,separators=(',', ':')).encode()).decode(),
        }
        str_payload = json.dumps(payload)
        _LOGGER.debug(f"Sending ICE candidate for camera {self.camera._attr_name} with session ID {self.session_id}: {str_payload}")
        await self.websocket.send(str_payload)

    def close_connection(self):
        if self.close is not None:
            self.close()

    async def run_loop(self):
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")

        loop = asyncio.get_running_loop()

        def close():
            if self.websocket is not None:
                return loop.create_task(self.websocket.close())
        self.close = close
        _LOGGER.debug(f"run_loop starting for camera {self.camera._attr_name} session {self.session_id}")
        try:
            async for message in self.websocket:
                if len(message) == 0:
                    _LOGGER.debug(f"Received empty message (type={type(message).__name__}) for camera {self.camera._attr_name} session {self.session_id}")
                    continue
                _LOGGER.debug(f"Received message for camera {self.camera._attr_name} with session ID {self.session_id}: {message}")
                try:
                    data = json.loads(message)
                except json.JSONDecodeError as e:
                    _LOGGER.error(f"Failed to decode JSON message for camera {self.camera._attr_name} with session ID {self.session_id}: {e}")
                    continue
                match data.get("messageType"):
                    case "ICE_CANDIDATE":
                        # Decode messagePayload (base64 JSON) → RTCIceCandidateInit → WebRTCCandidate
                        # KVS uses camelCase keys; map them to RTCIceCandidateInit's snake_case fields
                        candidate_str = base64.b64decode(data["messagePayload"]).decode()
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
                        self.callback(WebRTCAnswer(answer=sdp))
                    case "STATUS_RESPONSE" | "GO_AWAY" | "RECONNECT_ICE_SERVER":
                        _LOGGER.debug(f"KVS control message '{data.get('messageType')}' for session {self.session_id}: {data}")
                    case other:
                        _LOGGER.debug(f"Unhandled KVS message type '{other}' for session {self.session_id}: {data}")
        except Exception as e:
            _LOGGER.error(f"run_loop error for camera {self.camera._attr_name} session {self.session_id}: {e}", exc_info=True)
        _LOGGER.debug(f"run_loop exited for camera {self.camera._attr_name} session {self.session_id}")

