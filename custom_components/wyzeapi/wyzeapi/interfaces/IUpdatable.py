from abc import *
from ..devices import BaseDevice
from typing import Dict


class IUpdatable(BaseDevice):
    @abstractmethod
    def prop_map(self) -> Dict:
        pass

    def __setitem__(self, key, value):
        vars(self)[key] = value
