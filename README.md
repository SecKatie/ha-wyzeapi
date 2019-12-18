# Home Assistant - WYZE Bulb and Switch Integration

## Installation (HACS) - Highly Recommended

1. Have HACS installed, this will allow you to easily update
2. Add [https://github.com/JoshuaMulliken/ha-wyzeapi](https://github.com/JoshuaMulliken/ha-wyzebulb) as a custom repository as Type: Integration
3. Click install under "Wyze Bulb and Switch Api Integration" in the Integration tab
4. Restart HA

## Installation (Manual)

1. Download this repository as a ZIP (green button, top right) and unzip the archive
2. Copy `/custom_components/wyzeapi` to your `<config_dir>/` directory
   * On Hassio the final location will be `/config/custom_components/wyzeapi`
   * On Hassbian the final location will be `/home/homeassistant/.homeassistant/custom_components/wyzeapi`
3. Restart HA

## Configuration

Add the following to your configuration file. ***Note: This will change in a future release I am expecting to integrate the platform section so you only need to include the email and password once if you use both the light and the switch. Please refer to issue [#12](https://github.com/JoshuaMulliken/ha-wyzeapi/issues/12)***

```yaml
light:
  - platform: wyzeapi
    username: <email for wyze>
    password: <password for wyze>

switch:
  - platform: wyzeapi
    username: <email for wyze>
    password: <password for wyze>

```

## Usage

* Restart HA

* Entities will show up as `light.<friendly name>` or  `switch.<friendly name>` for example (`light.livingroom_lamp`).

### *Please report any issues you find*
