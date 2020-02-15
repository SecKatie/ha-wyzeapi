import unittest
import asyncio
import time

from typing import List

from . import wyzeapi
from . import wyze_bulb
from . import wyze_switch
from . import secrets

class WyzeApiTest(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
        self.wyzeapi = wyzeapi.WyzeApi(secrets.username, secrets.password)

    def tearDown(self):
        self.wyzeapi = None

    def test_get_bulbs(self):
        self.loop.run_until_complete(self.async_get_bulbs())

    async def async_get_bulbs(self):
        bulbs = await self.wyzeapi.async_list_bulbs()
        self.assertIsInstance(bulbs, List)
        if len(bulbs) > 0:
            self.assertIsInstance(bulbs[0], wyze_bulb.WyzeBulb)
    
    def test_get_switches(self):
        self.loop.run_until_complete(self.async_get_switches())

    async def async_get_switches(self):
        switches = await self.wyzeapi.async_list_switches()
        self.assertIsInstance(switches, List)
        if len(switches) > 0:
            self.assertIsInstance(switches[0], wyze_switch.WyzeSwitch)

    def test_recover_from_access_token_error(self):
        self.loop.run_until_complete(self.async_test_recover_from_access_token_error())

    async def async_test_recover_from_access_token_error(self):
        firstAccessToken = self.wyzeapi._access_token

        self.wyzeapi._access_token = "ERROR"
        bulbs1, bulbs2 = await asyncio.gather(self.wyzeapi.async_list_bulbs(), self.wyzeapi.async_list_bulbs(), return_exceptions=True)
        
        self.assertIsInstance(bulbs1, List)
        if len(bulbs1) > 0:
            self.assertIsInstance(bulbs1[0], wyze_bulb.WyzeBulb)
        self.assertIsInstance(bulbs2, List)
        if len(bulbs2) > 0:
            self.assertIsInstance(bulbs2[0], wyze_bulb.WyzeBulb)

        self.assertEqual(len(self.wyzeapi._invalid_access_tokens), 1)
        finalAccessToken = self.wyzeapi._access_token

        self.assertNotEqual(firstAccessToken, finalAccessToken)

    def test_async_speed_increase(self):
        start = time.perf_counter()
        bulbs = self.wyzeapi.list_bulbs()
        bulbs[0].turn_off()
        bulbs[0].turn_off()
        end = time.perf_counter()
        firstTime = end - start

        start = time.perf_counter()
        self.loop.run_until_complete(self.async_turn_bulb_off_twice())
        end = time.perf_counter()
        secondTime = end - start

        self.assertGreater(firstTime, secondTime)


    async def async_turn_bulb_off_twice(self):
        bulbs = await self.wyzeapi.async_list_bulbs()
        asyncio.gather(bulbs[0].async_turn_off(), bulbs[0].async_turn_off())