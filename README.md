# Home Assistant - WYZE Bulb Component

## Installation (HACS) - Highly Recommended

0. Have HACS installed, this will allow you to easily update
1. Add https://github.com/JoshuaMulliken/ha-wyzebulb as a custom repository as Type: Integration
2. Click install under "Wyze Bulb Api Integration" in the Integration tab
3. Restart HA

## Installation (Manual)
1. Download this repository as a ZIP (green button, top right) and unzip the archive
2. Copy `/custom_components/wyzeapi` to your `<config_dir>/` directory
   * On Hassio the final location will be `/config/custom_components/wyzeapi`
   * On Hassbian the final location will be `/home/homeassistant/.homeassistant/custom_components/wyzeapi`
3. Restart HA

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
