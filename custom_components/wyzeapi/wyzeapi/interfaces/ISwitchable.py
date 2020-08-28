from abc import *
from typing import Dict


class ISwitchable(ABC):
    @abstractmethod
    def switch_on_props(self) -> Dict:
        pass

    @abstractmethod
    def switch_off_props(self) -> Dict:
        pass
