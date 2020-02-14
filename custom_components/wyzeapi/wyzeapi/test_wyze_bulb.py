import unittest
from .wyzeapi import WyzeApi
from .secrets import *

class WyzeBulbTestCase(unittest.TestCase):
    def setUp(self):
        self.wyzeapi = WyzeApi(username, password)
        self.bulbs = self.wyzeapi.list_bulbs()
    
    def tearDown(self):
        self.wyzeapi = None

    def test_can_turn_on_bulb(self):
        if len(self.bulbs) > 0:
            self.bulbs[0].turn_off()
            self.bulbs[0].turn_on()
            self.assertTrue(self.bulbs[0].is_on())

    def test_can_update_bulb(self):
        if len(self.bulbs) > 0:
            self.bulbs[0].update()