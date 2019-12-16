# Awesome Lights

This integration shows how you would go ahead and integrate a physical light into Home Assistant.

If you use this integration as a template, make sure you tweak the following places:

 - `manifest.json`: update the requirements to point at your Python library
 - `light.py`: update the code to interact with your library

### Installation

Copy this folder to `<config_dir>/custom_components/example_light/`.

Add the following entry in your `configuration.yaml`:

```yaml
light:
  - platform: awesome_lights
    host: HOST_HERE
    username: USERNAME_HERE
    password: PASSWORD_HERE_OR_secrets.yaml
```
