"""Install HA's optional platform requirements for isolated compatibility tests.

Run with the compatibility environment's Python after installing Home Assistant.
Do not install the root project: its dependency pins describe the development
baseline, while HACS installs only the custom component and manifest requirements.
"""

import json
from importlib.metadata import version
from pathlib import Path
import subprocess
import sys

import homeassistant


def main() -> None:
    """Use each tested HA version's own integration requirements."""
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads(
        (root / "custom_components/wyzeapi/manifest.json").read_text()
    )
    requirements = set(manifest["requirements"])
    ha_root = Path(homeassistant.__file__).parent
    for domain in ("bluetooth", "usb", "hassio", "camera", "stream"):
        component = json.loads(
            (ha_root / "components" / domain / "manifest.json").read_text()
        )
        requirements.update(component.get("requirements", []))
    # aiodns 3.x allows pycares 5 in metadata, but still uses its removed API.
    # Keep this historical test-environment dependency compatible; no HA pin
    # is overridden and no constraint is added to users' HACS installations.
    if version("aiodns").startswith("3."):
        requirements.add("pycares<5")
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            sys.executable,
            f"homeassistant=={version('homeassistant')}",
            *sorted(requirements),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
