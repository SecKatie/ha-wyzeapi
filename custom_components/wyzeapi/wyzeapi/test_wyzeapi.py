import unittest
from .wyzeapi import WyzeApi
from .secrets import *

class WyzeApiTestCase(unittest.TestCase):
    def setUp(self):
        self.wyzeapi = WyzeApi(username, password)
    
    def tearDown(self):
        self.wyzeapi = None

    def test_initialize(self):
        self.assertIsNotNone(self.wyzeapi, "wyzeapi should exist")
    
    def test_should_have_access_token(self):
        self.assertIsNotNone(self.wyzeapi._access_token, "wyze api should have an access token")

    def test_should_recover_from_broken_access_token(self):
        self.wyzeapi._access_token = "ERROR"
        self.wyzeapi.list_bulbs()
        self.assertNotEqual("ERROR", self.wyzeapi._access_token, "wyze api must recover from broken access token")