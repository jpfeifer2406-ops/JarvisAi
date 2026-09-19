# COMPUTER Browser Bridge — v0.6.0 TEST

This local Chromium extension only reports the active tab title/URL to the
COMPUTER process at `127.0.0.1:7860`. It does not send browser data to a cloud
service.

## Load unpacked

1. Start COMPUTER.
2. Open your Chromium browser's extensions page and enable developer mode.
3. Choose **Load unpacked** and select this `browser_extension` folder.
4. Open COMPUTER settings. The Browser card should change to **connected**
   after the next active-tab event (or within about one minute).

v0.6.0 intentionally keeps the bridge read-only. Browser actions will be added
behind the COMPUTER permission broker rather than granting broad write/control
permissions to the first test build.
