import unittest
import asyncio
from .wyzeapi import WyzeApi
from .secrets import *

class WyzeApiAsyncTestCase(unittest.TestCase):
    def setUp(self):
        self.wyzeapi = WyzeApi(username, password)
    
    def tearDown(self):
        self.wyzeapi = None

    def test_async_recover_from_broken_access_token(self):
        self.wyzeapi._access_token = "ERROR"
        asyncio.run(self.wyzeapi.async_list_bulbs())
        self.assertNotEqual("ERROR", self.wyzeapi._access_token, "wyze api must recover from broken access token")