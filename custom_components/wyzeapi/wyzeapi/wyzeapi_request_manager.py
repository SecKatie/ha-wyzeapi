import requests
import json
import threading
from queue import Queue

from .wyzeapi_exceptions import WyzeApiError

import logging
_LOGGER = logging.getLogger(__name__)

class WyzeRequest():
	def __init__(self, url, payload, no_return=False):
		self._url = url
		self._payload = payload
		self._no_return = no_return
		self._response = None

		self._header = {
			'Host': 'api.wyzecam.com:443',
			'User-Agent': 'Wyze/2.6.62 (iPhone; iOS 13.2.3; Scale/2.00)',
			'Content-Type': 'application/json'
		}

class RequestManager():
	def __init__(self, api):
		self._api = api
		self._close = False
		self._request_queue = Queue()
		self._lock = threading.Lock()
		self._in_error_state = False
		self._error_msg = ""

		self._manager = threading.Thread(target=self.request_manager)
		self._manager.start()

	def request_manager(self):
		while self._close != True:
			request_item = self._request_queue.get()

			self._lock.acquire()
			if self._in_error_state:
				_LOGGER.error(self._error_msg)
				self._api._access_token = None
				self._api.initialize()
			self._lock.release()

			t = threading.Thread(target=self.request_worker, args=(request_item,))
			t.start()

	def request_worker(self, request):
		r = requests.post(request._url, headers=request._header, data=json.dumps(request._payload))

		data = r.json()

		if data['code'] != '1':
			if data['msg'] == 'AccessTokenError':
				_LOGGER.info("Recieved AccessTokenError attempting to regenerate the AccessToken")

				self._lock.acquire()
				self._in_error_state = True
				self._error_msg = data['msg']
				self._lock.release()

				self._request_queue.put(request)
			else:
				raise WyzeApiError(data['msg'])

		if request._response != None:
			request._response.put(data)

	def do_blocking_request(self, url, payload):
		request = WyzeRequest(url, payload)
		response = Queue()
		request._response = response
		self._request_queue.put(request)
		return response.get()

	def do_single_threaded_request(self, url, payload):
		request = WyzeRequest(url, payload)
		response = Queue()
		request._response = response
		self.request_worker(request)
		return response.get()

	def do_request(self, url, payload):
		request = WyzeRequest(url, payload)
		self._request_queue.put(request)
