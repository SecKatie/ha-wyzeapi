import json
import logging
import ssl

import aiohttp
import certifi
import requests

from .wyzeapi_exceptions import WyzeApiError, AccessTokenError

_LOGGER = logging.getLogger(__name__)


class WyzeRequest:
    def __init__(self, url, payload, no_return=False):
        _LOGGER.debug("Wyze Request initializing.")
        self.__url = url
        self.__payload = json.dumps(payload)
        self.__no_return = no_return
        self.__response = None

        self.__header = {
            'Host': 'api.wyzecam.com:443',
            'User-Agent': 'Wyze/2.6.62 (iPhone; iOS 13.2.3; Scale/2.00)',
            'Content-Type': 'application/json'
        }

    def get_response(self):
        _LOGGER.debug("Wyze Request getting response.")
        r = requests.post(self.__url, headers=self.__header, data=self.__payload)

        data = r.json()

        if data['code'] != '1':
            if data['msg'] == 'AccessTokenError':
                raise AccessTokenError("Payload: " + str(self.__payload) + "\nResponse Data: " + str(data))
            else:
                raise WyzeApiError("Payload: " + str(self.__payload) + "\nResponse Data: " + str(data))

        return data

    async def async_get_response(self):
        _LOGGER.debug("Wyze Request getting response async.")
        async with aiohttp.ClientSession() as session:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            async with session.post(self.__url, headers=self.__header, data=self.__payload, ssl=ssl_context) as resp:
                data = await resp.json()

                if data['code'] != '1':
                    if data['msg'] == 'AccessTokenError':
                        raise AccessTokenError("Payload: " + str(self.__payload) + "\nResponse Data: " + str(data))
                    else:
                        raise WyzeApiError("Payload: " + str(self.__payload) + "\nResponse Data: " + str(data))

                return data
