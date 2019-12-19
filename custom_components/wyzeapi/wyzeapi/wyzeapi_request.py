import requests
import json
import threading
import logging
_LOGGER = logging.getLogger(__name__)

from .wyzeapi_exceptions import *

headers = {
	'Host': 'api.wyzecam.com:443',
	'User-Agent': 'Wyze/2.6.62 (iPhone; iOS 13.2.3; Scale/2.00)',
	'Content-Type': 'application/json'
}

def request_helper(url, payload, api):
	r = requests.post(url, headers=headers, data=json.dumps(payload))

	data = r.json()

	if data['code'] != '1':
		if data['msg'] == 'AccessTokenError':
			_LOGGER.info("Recieved AccessTokenError attempting to regenerate the AccessToken")

			api._access_token = None
			api.initialize()
		else:
			raise WyzeApiError(data['msg'])

	return data

def do_request(url, payload, api, no_return=False):
	if no_return:
		x = threading.Thread(target=request_helper, args=(url, payload, api))
		x.start()
	else:
		return request_helper(url, payload, api)
