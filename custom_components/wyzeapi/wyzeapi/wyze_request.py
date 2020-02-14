import requests
import json
import aiohttp
import ssl
import certifi

from .wyzeapi_exceptions import WyzeApiError, AccessTokenError

class WyzeRequest():
    def __init__(self, url, payload, no_return=False):
        self._url = url
        self._payload = json.dumps(payload)
        self._no_return = no_return
        self._response = None

        self._header = {
            'Host': 'api.wyzecam.com:443',
            'User-Agent': 'Wyze/2.6.62 (iPhone; iOS 13.2.3; Scale/2.00)',
            'Content-Type': 'application/json'
        }

    def getResponse(self):
        r = requests.post(self._url, headers=self._header, data=self._payload)

        data = r.json()

        if data['code'] != '1':
            if data['msg'] == 'AccessTokenError':
                raise AccessTokenError("Payload: " + str(self._payload) + "\nResponse Data: " + str(data))
            else:
                raise WyzeApiError("Payload: " + str(self._payload) + "\nResponse Data: " + str(data))

        return data

    async def async_getResponse(self):
        async with aiohttp.ClientSession() as session:
            sslcontext = ssl.create_default_context(cafile=certifi.where())
            async with session.post(self._url, headers=self._header, data=self._payload, ssl=sslcontext) as resp:
                data = await resp.json()

                if data['code'] != '1':
                    if data['msg'] == 'AccessTokenError':
                        raise AccessTokenError("Payload: " + str(self._payload) + "\nResponse Data: " + str(data))
                    else:
                        raise WyzeApiError("Payload: " + str(self._payload) + "\nResponse Data: " + str(data))

                return data