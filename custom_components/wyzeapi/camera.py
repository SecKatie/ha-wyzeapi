import base64
import json
import asyncio
from dataclasses import asdict
from collections.abc import Callable
from typing import Any
import logging
from urllib.parse import unquote


from webrtc_models import RTCConfiguration, RTCIceServer
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.camera import Camera as CameraEntity, CameraEntityFeature
from homeassistant.components.camera.webrtc import WebRTCClientConfiguration, WebRTCSendMessage, WebRTCAnswer, WebRTCCandidate, async_register_webrtc_provider
from webrtc_models import RTCIceCandidateInit
from wyzeapy import Wyzeapy, CameraService
from wyzeapy.services.camera_service import Camera
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from websockets.asyncio.client import connect as websocket_connect

from .const import CONF_CLIENT, DOMAIN, RESET_BUTTON_PRESSED
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

    _LOGGER.warning("Wyze camera component setup complete")
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
        self.next_config = None
        asyncio.create_task(self.get_config())

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

    async def get_config(self):
        self.next_config = await self._camera_service.get_stream_info(self._camera)
        _LOGGER.warning(f"Fetched new WebRTC session configuration for camera {self._attr_name}: {self.next_config}")


    def _async_get_webrtc_client_configuration(self) -> WebRTCClientConfiguration:
        if self.next_config is None:
            asyncio.create_task(self.get_config())
            raise HomeAssistantError("WebRTC session configuration not available, fetching new configuration")
        config = self.next_config
        

        _LOGGER.warning(f"WebRTC session configuration for camera {self._attr_name}: {config}")
        ice_servers = []

        for server in config.get("ice_servers", []):
            _LOGGER.warning(f"Adding ICE server for camera {self._attr_name}: {server}")
            ice_servers.append(RTCIceServer.from_dict({
                "urls": server['url'],
                "username": server["username"],
                "credential": server["password"],
            }))

        _LOGGER.warning(f"ICE servers for camera {self._attr_name}: {ice_servers}")
        configuration = RTCConfiguration(ice_servers=ice_servers)
        webrtc_config = WebRTCClientConfiguration(
            configuration=configuration
        )
        return webrtc_config

    async def async_handle_async_webrtc_offer(self, offer_sdp: str, session_id: str, send_message: WebRTCSendMessage) -> None:

        _LOGGER.debug(f"Handling WebRTC offer for camera {self._attr_name} with session ID {session_id}")
        # Implement the logic to handle the WebRTC offer and send the answer back using send_message
        config = self.next_config
        self.next_config = None

        if config is None:
            config = await self._camera_service.get_stream_info(self._camera)

        self.sessions[session_id] = WyzeCameraWebRTCSession(session_id, self, send_message, config)

        await self.sessions[session_id].send_offer(offer_sdp)

    async def async_on_webrtc_candidate(self, session_id: str, candidate: RTCIceCandidateInit) -> None:
        # Implement the logic to handle the WebRTC candidate and send it to the camera's WebRTC session
        if session_id not in self.sessions:
            raise ValueError("Session ID not found")

        await self.sessions[session_id].send_candidate(candidate)

    def async_close_session(self, session_id: str) -> None:
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

    async def connect(self):
        self.websocket = await websocket_connect(unquote(self.config['signaling_url']), logger=_LOGGER)
        _LOGGER.warning(f"WebSocket connection established for camera {self.camera._attr_name} with session ID {self.session_id}")
        asyncio.create_task(self.run_loop())

    async def send_offer(self, offer_sdp: str):
        async with self.lock:
            if self.websocket is None:
                _LOGGER.warning("Conecting to websocket from send_offer")
                await self.connect()
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")
        # Create an offer for Kinesis
        payload = {
            "action": "SDP_OFFER",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": base64.b64encode(offer_sdp.encode()).decode(),
        }
        _LOGGER.warning(f"Sending SDP offer for camera {self.camera._attr_name} with session ID {self.session_id}")
        await self.websocket.send(json.dumps(payload), text=True)

    async def send_candidate(self, candidate: RTCIceCandidateInit):
        """{
            "action": "ICE_CANDIDATE",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": "eyJjYW5kaWRhdGUiOiJjYW5kaWRhdGU6MzI5NzAwNjk2IDEgdWRwIDE2Nzc3MzIwOTUgMjYwMToyNDY6NWI3ZjpiMTAxOjoxMGU4IDQ4OTE4IHR5cCBzcmZseCByYWRkciA6OiBycG9ydCAwIGdlbmVyYXRpb24gMCB1ZnJhZyBJZ0M1IG5ldHdvcmstY29zdCA5OTkiLCJzZHBNaWQiOiIxIiwic2RwTUxpbmVJbmRleCI6MSwidXNlcm5hbWVGcmFnbWVudCI6IklnQzUifQ=="
        }"""
        # Take RTCIceCandidateInit, convert it to the format in the messagePayload above, and send it to the client using the callback
        async with self.lock:
            if self.websocket is None:
                _LOGGER.warning("Conecting to websocket from send_candidate")
                await self.connect()
        if self.websocket is None:
            raise ConnectionError("WebSocket connection not established")
        candidate_dict = asdict(candidate)
        payload = {
            "action": "ICE_CANDIDATE",
            "recipientClientId": "ada06f08-87f4-4e13-b699-e82db8517ae5",
            "messagePayload": base64.b64encode(json.dumps(candidate_dict).encode()).decode(),
        }
        _LOGGER.warning(f"Sending ICE candidate for camera {self.camera._attr_name} with session ID {self.session_id}")
        await self.websocket.send(json.dumps(payload), text=True)

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
        async for message in self.websocket:
            if len(message) == 0:
                _LOGGER.warning(f"Received empty message for camera {self.camera._attr_name} with session ID {self.session_id}")
                continue
            _LOGGER.warning(f"Received message for camera {self.camera._attr_name} with session ID {self.session_id}: {message}")
            try:
                data = json.loads(message)
            except json.JSONDecodeError as e:
                _LOGGER.error(f"Failed to decode JSON message for camera {self.camera._attr_name} with session ID {self.session_id}: {e}")
                continue
            _LOGGER.warning(f"Received message for camera {self.camera._attr_name} with session ID {self.session_id}: {data}")
            match data.get("messageType"):
                case "ICE_CANDIDATE":
                    """
                    {
                        "messagePayload": "eyJjYW5kaWRhdGUiOiJjYW5kaWRhdGU6MCAxIHVkcCAyMTMwNzA2NDMxIDEwLjI1NC4wLjE3MyAzNjg1MyB0eXAgaG9zdCByYWRkciAwLjAuMC4wIHJwb3J0IDAgZ2VuZXJhdGlvbiAwIG5ldHdvcmstY29zdCA5OTkiLCJzZHBNaWQiOiIwIiwic2RwTUxpbmVJbmRleCI6MH0=",
                        "messageType": "ICE_CANDIDATE"
                    }
                    """
                    # Pass the candidate from messagePayload to a RTCIceCandidateInit and then to WebRTCCandidate, and send it back to the client using the callback
                    candidate = base64.b64decode(data["messagePayload"]).decode()
                    data = json.loads(candidate)
                    rtccandidate = RTCIceCandidateInit(**data)
                    wrtccandidate = WebRTCCandidate(candidate=rtccandidate)
                    self.callback(wrtccandidate)
                    break
                case "SDP_ANSWER":
                    """
                    {
                        "messagePayload": "eyJ0eXBlIjogImFuc3dlciIsICJzZHAiOiAidj0wXHJcbm89LSAxMTEyMDE2NzU5IDIgSU4gSVA0IDEyNy4wLjAuMVxyXG5zPS1cclxudD0wIDBcclxuYT1ncm91cDpCVU5ETEUgMCAxIDJcclxuYT1tc2lkLXNlbWFudGljOiBXTVMgbXlLdnNWaWRlb1N0cmVhbVxyXG5tPXZpZGVvIDkgVURQL1RMUy9SVFAvU0FWUEYgMTA5IDExNFxyXG5jPUlOIElQNCAxMjcuMC4wLjFcclxuYT1jYW5kaWRhdGU6MCAxIHVkcCAyMTMwNzA2NDMxIDEwLjI1NC4wLjE3MyAzNjg1MyB0eXAgaG9zdCByYWRkciAwLjAuMC4wIHJwb3J0IDAgZ2VuZXJhdGlvbiAwIG5ldHdvcmstY29zdCA5OTlcclxuYT1tc2lkOm15S3ZzVmlkZW9TdHJlYW0gbXlWaWRlb1RyYWNrUlRYXHJcbmE9c3NyYy1ncm91cDpGSUQgNjcyOTE3OTE2IDE5NzU0Njc3ODhcclxuYT1zc3JjOjY3MjkxNzkxNiBjbmFtZTpPcUxpRVZRUlh3blNreGtkXHJcbmE9c3NyYzo2NzI5MTc5MTYgbXNpZDpteUt2c1ZpZGVvU3RyZWFtIG15VmlkZW9UcmFja1xyXG5hPXNzcmM6NjcyOTE3OTE2IG1zbGFiZWw6bXlLdnNWaWRlb1N0cmVhbVxyXG5hPXNzcmM6NjcyOTE3OTE2IGxhYmVsOm15VmlkZW9UcmFja1xyXG5hPXNzcmM6MTk3NTQ2Nzc4OCBjbmFtZTpPcUxpRVZRUlh3blNreGtkXHJcbmE9c3NyYzoxOTc1NDY3Nzg4IG1zaWQ6bXlLdnNWaWRlb1N0cmVhbSBteVZpZGVvVHJhY2tSVFhcclxuYT1zc3JjOjE5NzU0Njc3ODggbXNsYWJlbDpteUt2c1ZpZGVvU3RyZWFtUlRYXHJcbmE9c3NyYzoxOTc1NDY3Nzg4IGxhYmVsOm15VmlkZW9UcmFja1JUWFxyXG5hPXJ0Y3A6OSBJTiBJUDQgMC4wLjAuMFxyXG5hPWljZS11ZnJhZzpLUDlrXHJcbmE9aWNlLXB3ZDpEMldNeHFBSXZDdWNNSGxMVUY0QXROeDlcclxuYT1pY2Utb3B0aW9uczp0cmlja2xlXHJcbmE9ZmluZ2VycHJpbnQ6c2hhLTI1NiAzMDpCMToxMToxMzpCMDpBRTpGRTpDMjozMDo2OToxNTpGNjpGRDo3Qzo2QTpFNDo2RToyODo2NDo1ODpFODpERDoyOTo3QjpBRjpBNDpGMDpFQzpCMjpGNDpCQzowRFxyXG5hPXNldHVwOmFjdGl2ZVxyXG5hPW1pZDowXHJcbmE9c2VuZG9ubHlcclxuYT1ydGNwLW11eFxyXG5hPXJ0Y3AtcnNpemVcclxuYT1ydHBtYXA6MTA5IEgyNjQvOTAwMDBcclxuYT1mbXRwOjEwOSBsZXZlbC1hc3ltbWV0cnktYWxsb3dlZD0xO3BhY2tldGl6YXRpb24tbW9kZT0xO3Byb2ZpbGUtbGV2ZWwtaWQ9NDJlMDFmXHJcbmE9cnRwbWFwOjExNCBydHgvOTAwMDBcclxuYT1mbXRwOjExNCBhcHQ9MTA5XHJcbmE9cnRjcC1mYjoxMDkgbmFja1xyXG5hPXJ0Y3AtZmI6MTA5IGdvb2ctcmVtYlxyXG5hPXJ0Y3AtZmI6MTA5IHRyYW5zcG9ydC1jY1xyXG5tPWF1ZGlvIDkgVURQL1RMUy9SVFAvU0FWUEYgMFxyXG5jPUlOIElQNCAxMjcuMC4wLjFcclxuYT1jYW5kaWRhdGU6MCAxIHVkcCAyMTMwNzA2NDMxIDEwLjI1NC4wLjE3MyAzNjg1MyB0eXAgaG9zdCByYWRkciAwLjAuMC4wIHJwb3J0IDAgZ2VuZXJhdGlvbiAwIG5ldHdvcmstY29zdCA5OTlcclxuYT1tc2lkOm15S3ZzVmlkZW9TdHJlYW0gbXlBdWRpb1RyYWNrXHJcbmE9c3NyYzoxNDY0MzI2NzU5IGNuYW1lOk9xTGlFVlFSWHduU2t4a2RcclxuYT1zc3JjOjE0NjQzMjY3NTkgbXNpZDpteUt2c1ZpZGVvU3RyZWFtIG15QXVkaW9UcmFja1xyXG5hPXNzcmM6MTQ2NDMyNjc1OSBtc2xhYmVsOm15S3ZzVmlkZW9TdHJlYW1cclxuYT1zc3JjOjE0NjQzMjY3NTkgbGFiZWw6bXlBdWRpb1RyYWNrXHJcbmE9cnRjcDo5IElOIElQNCAwLjAuMC4wXHJcbmE9aWNlLXVmcmFnOktQOWtcclxuYT1pY2UtcHdkOkQyV014cUFJdkN1Y01IbExVRjRBdE54OVxyXG5hPWljZS1vcHRpb25zOnRyaWNrbGVcclxuYT1maW5nZXJwcmludDpzaGEtMjU2IDMwOkIxOjExOjEzOkIwOkFFOkZFOkMyOjMwOjY5OjE1OkY2OkZEOjdDOjZBOkU0OjZFOjI4OjY0OjU4OkU4OkREOjI5OjdCOkFGOkE0OkYwOkVDOkIyOkY0OkJDOjBEXHJcbmE9c2V0dXA6YWN0aXZlXHJcbmE9bWlkOjFcclxuYT1zZW5kcmVjdlxyXG5hPXJ0Y3AtbXV4XHJcbmE9cnRjcC1yc2l6ZVxyXG5hPXJ0cG1hcDowIFBDTVUvODAwMFxyXG5hPXJ0Y3AtZmI6MCBuYWNrXHJcbmE9cnRjcC1mYjowIGdvb2ctcmVtYlxyXG5hPXJ0Y3AtZmI6MCB0cmFuc3BvcnQtY2NcclxubT1hcHBsaWNhdGlvbiA5IFVEUC9EVExTL1NDVFAgd2VicnRjLWRhdGFjaGFubmVsXHJcbmM9SU4gSVA0IDEyNy4wLjAuMVxyXG5hPWNhbmRpZGF0ZTowIDEgdWRwIDIxMzA3MDY0MzEgMTAuMjU0LjAuMTczIDM2ODUzIHR5cCBob3N0IHJhZGRyIDAuMC4wLjAgcnBvcnQgMCBnZW5lcmF0aW9uIDAgbmV0d29yay1jb3N0IDk5OVxyXG5hPXJ0Y3A6OSBJTiBJUDQgMC4wLjAuMFxyXG5hPWljZS11ZnJhZzpLUDlrXHJcbmE9aWNlLXB3ZDpEMldNeHFBSXZDdWNNSGxMVUY0QXROeDlcclxuYT1maW5nZXJwcmludDpzaGEtMjU2IDMwOkIxOjExOjEzOkIwOkFFOkZFOkMyOjMwOjY5OjE1OkY2OkZEOjdDOjZBOkU0OjZFOjI4OjY0OjU4OkU4OkREOjI5OjdCOkFGOkE0OkYwOkVDOkIyOkY0OkJDOjBEXHJcbmE9c2V0dXA6YWN0aXZlXHJcbmE9bWlkOjJcclxuYT1zY3RwLXBvcnQ6NTAwMFxyXG4ifQ==",
                        "messageType": "SDP_ANSWER"
                    }
                    """
                    # Pass the answer from messagePayload to a WebRTCAnswer, and send it back to the client using the callback
                    answer = base64.b64decode(data["messagePayload"]).decode()
                    wrtcanswer = WebRTCAnswer(answer=answer)
                    self.callback(wrtcanswer)
                    break

