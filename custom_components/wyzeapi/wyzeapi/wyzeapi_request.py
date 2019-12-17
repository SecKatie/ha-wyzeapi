import requests
import json
import threading

from .wyzeapi_exceptions import *

headers = {
	'Host': 'api.wyzecam.com:443',
	'User-Agent': 'Wyze/2.6.62 (iPhone; iOS 13.2.3; Scale/2.00)',
	'Content-Type': 'application/json'
}

def request_helper(url, payload):
	r = requests.post(url, headers=headers, data=json.dumps(payload))

	data = r.json()

	if data['code'] != '1':
		raise WyzeApiError(data['msg'])

	return data

def do_request(url, payload, no_return=False):
	if no_return:
		x = threading.Thread(target=request_helper, args=(url, payload))
		x.start()
	else:
		return request_helper(url, payload)
