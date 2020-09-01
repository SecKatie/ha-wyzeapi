from typing import Dict

from ..interfaces import IUpdatable


class Lock(IUpdatable):
    open_close_state: int
    switch_state: int

    def __init__(self, nick_name, product_model, mac, switch_state, open_close_state):
        super().__init__(nick_name, product_model, mac)

        self.switch_state = switch_state
        self.open_close_state = open_close_state

    def prop_map(self) -> Dict:
        prop_map = {
            "P5": self.available,
        }

        if self.product_model == "YD.LO1":
            prop_map.update({
                "P3": self.switch_state,
                "P2001": self.open_close_state
            })

        return prop_map
