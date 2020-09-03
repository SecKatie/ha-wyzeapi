from abc import *
from ..devices import BaseDevice
from typing import Dict


class IUpdatable(BaseDevice):
    @abstractmethod
    def prop_map(self) -> Dict:
        pass
