from abc import *
from typing import Dict


class IUpdatable(ABC):
    @abstractmethod
    def prop_map(self) -> Dict:
        pass

    def __setitem__(self, key, value):
        vars(self)[key] = value
