from abc import *
from ..devices import BaseDevice
from typing import Dict


class ISwitchable(BaseDevice):
    @abstractmethod
    def switch_on_props(self) -> Dict:
        pass

    @abstractmethod
    def switch_off_props(self) -> Dict:
        pass
