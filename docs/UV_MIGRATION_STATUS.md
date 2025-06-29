# uv Migration Status

The project’s packaging and CI configuration have been fully migrated
from Poetry to **uv** + Hatch‐build system.

✅  `pyproject.toml` now uses PEP 621 metadata and Hatch build backend  
✅  Editable install with `uv pip install -e .` succeeds  
✅  GitHub Action `.github/workflows/HASAction.yml` contains no Poetry
    references, so no workflow changes are needed  
✅  Wheel build selects the `custom_components` package via
    `[tool.hatch.build.targets.wheel]`  

No further code or configuration changes are necessary at this time.
