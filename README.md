# Home Assistant - Wyze Integration

This is a custom component to allow control of various Wyze devices in Home Assistant using the unofficial API. Please
note this mimics the Wyze app and therefore access may be cut off at anytime.

### Highlights of what **WyzeApi** can do

* Control Wyze Bulbs as lights through HA
* Control Wyze Plugs as switches through HA
* Use Wyze Cameras as motion sensors
* Turn on and off Wyze Cameras
* Lock, unlock, and view status of lock and door for the Wyze Lock

### Potential Downsides

* This is an unofficial implementation of the api and therefore may be disabled or broken at anytime by WyzeLabs
* ***It requires two factor authentication to be disabled on your account***

## Support

If you like what I have done here and want to help I would recommend that you firstly look into supporting Home
Assistant. You can do this by purchasing some swag from their [store](https://teespring.com/stores/home-assistant-store)
or paying for a Nabu Casa subscription. None of this could happen without them.

After you have done that if you feel like my work has been valuable to you I welcome your support through BuyMeACoffee.

<a href="https://www.buymeacoffee.com/joshmulliken" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-blue.png" alt="Buy Me A Coffee" style="height: 51px !important;width: 217px !important;" ></a>

## Installation (HACS) - Highly Recommended

1. Have HACS installed, this will allow you to easily update
2. Add [https://github.com/JoshuaMulliken/ha-wyzeapi](https://github.com/JoshuaMulliken/ha-wyzebulb) as a custom
   repository as Type: Integration
3. Click install under "Wyze Bulb and Switch Api Integration" in the Integration tab
4. Restart HA
5. Navigate to _Integrations_ in the config interface.
6. Click _ADD INTEGRATION_
7. Search for _Wyze Home Assistant Integration_
8. Put the email for wyze in the first box and your password in the second
9. Click _SUBMIT_ and profit!

## Usage

* Entities will show up as `light.<friendly name>`, `switch.<friendly name>`, `binary_sensor.<friendly name>`
  or `lock.<friendly name>` for example (`light.livingroom_lamp`).
* Instructions for interacting with lights can be found here: https://www.home-assistant.io/integrations/light/
    * Switches: https://www.home-assistant.io/integrations/switch/
    * Camera motion sensors: https://www.home-assistant.io/integrations/binary_sensor/

## More information and Help

If you would like more information then please look at the [wiki](https://github.com/JoshuaMulliken/ha-wyzeapi/wiki)!

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

