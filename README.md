# Home Assistant - WYZE Bulb Component

## Installation
1. Download this repository as a ZIP (green button, top right) and unzip the archive
2. Copy `/custom_components/wyze_api` to your `<config_dir>/` directory
   * On Hassio the final location will be `/config/custom_components/wyze_api`
   * On Hassbian the final location will be `/home/homeassistant/.homeassistant/custom_components/wyze_api`

## Configuration
Add the following to your configuration file

```yaml
light:
  - platform: wyzeapi
    username: <email for wyze>
    password: <password for wyze>
    
```

## Usage
* Restart HA

* Entities will show up as `light.<friendly name>` for example (`light.livingroom_lamp`).

### Please report any issues you find!
