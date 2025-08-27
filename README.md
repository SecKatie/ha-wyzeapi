<!--
SPDX-FileCopyrightText: 2021 Katie Mulliken <katie@mulliken.net>

SPDX-License-Identifier: Apache-2.0
-->

<a href="https://www.buymeacoffee.com/seckatie"><img src="https://img.buymeacoffee.com/button-api/?text=Buy me a coffee&emoji=&slug=seckatie&button_colour=BD5FFF&font_colour=ffffff&font_family=Cookie&outline_colour=000000&coffee_colour=FFDD00" /></a>


# Home Assistant - Wyze Integration

This is a custom component to allow control of various Wyze devices in Home Assistant using the unofficial API. Please
note this mimics the Wyze app and therefore access may be cut off at anytime.

### Highlights of what **WyzeApi** can do

* Control Wyze Bulbs as lights through HA
* Control Wyze Plugs as switches through HA
* Use Wyze Cameras as motion sensors **NOTE:** Disabled following API usage incident with Wyze
* Turn on and off Wyze Cameras
* Lock, unlock, and view status of lock and door for the Wyze Lock

### Potential Downsides

* This is an unofficial implementation of the api and therefore may be disabled or broken at anytime by WyzeLabs
* ~~***It requires two factor authentication to be disabled on your account***~~ 
* ***Two Factor Authentication is supported as of version 2021.9.2***

## Funding

If you like what I have done here and want to help I would recommend that you firstly look into supporting Home
Assistant. You can do this by purchasing some swag from their [store](https://teespring.com/stores/home-assistant-store)
or paying for a Nabu Casa subscription. None of this could happen without them.

After you have done that if you feel like my work has been valuable to you I welcome your support through BuyMeACoffee or Github Sponsers in the right hand menu.

## Installation (HACS) - Highly Recommended

1. Have HACS installed, this will allow you to easily update
2. Add [https://github.com/SecKatie/ha-wyzeapi](https://github.com/SecKatie/ha-wyzeapi) as a custom
   repository as Type: Integration
3. Click install under "Wyze Bulb and Switch Api Integration" in the Integration tab
4. Restart HA
5. Navigate to _Integrations_ in the config interface.
6. Click _ADD INTEGRATION_
7. Search for _Wyze Home Assistant Integration_
   **NOTE:** If _Wyze Home Assistant Integration_ does not appear, hard refresh the browser (ctrl+F5) and search again
9. Enter your email, password, keyid & apikey when prompted.
   **NOTE:** If you do not know how to generate your keyid & apikey, please see the following official Wyze documentation: [Creating an API Key](https://support.wyze.com/hc/en-us/articles/16129834216731-Creating-an-API-Key)
   **NOTE:** Google OAuth ("Sign in with Google") accounts are not supported. Use a Wyze email/password account.
10. Click _SUBMIT_ and profit!

## Authentication

- Not supported: Wyze accounts that sign in with Google OAuth ("Sign in with Google"). The integration requires a Wyze account that authenticates with a native email/password plus a valid Wyze Developer Key ID and API Key.
- Workaround: If your primary Wyze account uses Google SSO, create a secondary Wyze account with email/password and share your devices to it from the Wyze app. Generate a developer key for that account and use that account’s email/password and key ID/API key during setup.
- 2FA is supported and you may be prompted to enter a verification code during configuration.

## Usage

* Entities will show up as `light.<friendly name>`, `switch.<friendly name>`, `binary_sensor.<friendly name>`
  or `lock.<friendly name>` for example (`light.livingroom_lamp`).
* Instructions for interacting with lights can be found here: https://www.home-assistant.io/integrations/light/
    * Switches: https://www.home-assistant.io/integrations/switch/
    * Camera motion sensors: https://www.home-assistant.io/integrations/binary_sensor/

## Contributing

* For development contributions please join our IRC channel #wyzeapi on Libre.Chat
* For instructions on intercepting data from the Wyze app see: https://mulliken.net/p/intercepting-pinned-tls-connections-on-android/

## Support

If you need help with anything then please connect with the community!

* Visit us on IRC at librechat in the #wyzeapi channel!
* Visit the discussions tab on this repo
* For bugs or feature requests create an issue
* Check out the [wiki](https://github.com/SecKatie/ha-wyzeapi/wiki)!
