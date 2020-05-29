# Home Assistant - Wyze Bulb, Switch, Sensor and Lock Integration

This is a custom component to allow control of Wyze Bulbs and Switches in Homeassistant using the unofficial Wyze API. Please note this mimics the Wyze app and therefore Wyze may cut off access at anytime.

### Highlights of what **WyzeApi** can do

* Control Wyze Bulbs as lights through HA
* Control Wyze Switches as switches through HA
* View Wyze Sensors as binary_sensor through HA
* View Wyze Lock Status and Door Status as lock through HA
	* Note: Currently you can only view the lock status or door status. Lock and Unlock does not work!

### Potential Downsides

* This is an unofficial implementation of the api and therefore may be disabled or broken at anytime by WyzeLabs
* I only have light bulbs and no switches so they are not tested directly by me. An update may break them without my knowledge. **Please use the betas as they become avaliable if you have switches to help me find bugs prior to release**
* It requires two factor authentication to be disabled on your account

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

Add the following to your configuration file. ***Note: This has changed recently. Check your configuration!***

```yaml
wyzeapi:
  username: <email for wyze>
  password: <password for wyze>
```
You can exclude any of the devices.

```yaml
wyzeapi:
  username: <email for wyze>
  password: <password for wyze>
  sensors: false
  light: false
  switch: false
  lock: false
```
## Usage

* Restart HA

* Entities will show up as `light.<friendly name>`, `switch.<friendly name>`, `binary_sensor.<friendly name>` or `lock.<friendly name>` for example (`light.livingroom_lamp`).

## Reporting an Issue

1. Setup your logger to print debug messages for this component by adding this to your `configuration.yaml`:
    ```yaml
    logger:
      default: warning
      logs:
        custom_components.wyzeapi: debug
    ```
2. Restart HA
3. Verify you're still having the issue
4. File an issue in this Github Repository
