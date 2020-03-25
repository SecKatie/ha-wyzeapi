# Home Assistant - Wyze Bulb and Switch Integration

This is a custom component to allow control of Wyze Bulbs and Switches in Homeassistant using the unofficial Wyze API. Please note this mimics the Wyze app and therefore Wyze may cut off access at anytime.

### Highlights of what **WyzeApi** can do

* Control Wyze Bulbs as lights through HA
* Control Wyze Switches as switches through HA

### Potential Downsides

* This is an unofficial implementation of the api and therefore may be disabled or broken at anytime by WyzeLabs
* I only have light bulbs and no switches so they are not tested directly by me. An update may break them without my knowledge. **Please use the betas as they become avaliable if you have switches to help me find bugs prior to release**
* It requires two factor authentication to be disabled on your account

## Installation (HACS) - Highly Recommended

ha-wyzeapi is now available in the HACS Integrations store. You no longer need to add a custom repository.
1. Have HACS installed, this will allow you to easily update
2. In the integrations tab of HACS, search for ' ha-wyzeapi ' and click install.

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

## Usage

* Restart HA

* Entities will show up as `light.<friendly name>` or  `switch.<friendly name>` for example (`light.livingroom_lamp`).

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
