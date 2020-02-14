import unittest
from .wyzeapi import WyzeApi
from .secrets import *

class WyzeBulbTestCase(unittest.TestCase):
    def setUp(self):
        self.wyzeapi = WyzeApi(username, password)
        self.switches = self.wyzeapi.list_switches()
    
    def tearDown(self):
        self.wyzeapi = None

    def test_can_turn_on_switch(self):
        if len(self.switches) > 0:
            self.switches[0].turn_off()
            self.switches[0].turn_on()
            self.assertTrue(self.switches[0].is_on())

    def test_can_update_switch(self):
        if len(self.switches) > 0:
            self.switches[0].update()