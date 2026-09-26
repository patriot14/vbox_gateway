# VBox TV Gateway for Home Assistant

Local Home Assistant integration for VBox TV Gateway XTi 3442-21, verified
against responses from firmware VJ.2.66.20. No cloud account is used.

## What it exposes

- Two DVB-T/T2 tuners: lock state, signal strength, RF, SNR, BER, channel,
  frequency, bandwidth, PLP ID and advanced diagnostic parameters.
- CPU use, memory use, CPU temperature and uptime from the System Status page.
- Current state of seven services from Administer System Services.
- Number of tuned channels (total, TV and radio), number of active streams,
  total streaming bitrate, current stream details and running recording count.
- Device information, connectivity and a manually operated restart button.

The restart button invokes the HTTP API method `SystemRestart`, captured
during a real restart from the device's own web interface. It is never called
during setup or polling. Shutdown and service controls are not implemented.

## Install with HACS

1. Create a GitHub repository and upload the **contents** of this directory
   to its root, keeping `custom_components/vbox_gateway/manifest.json`
   in that exact location. Do not upload the ZIP as the repository's only file.
   In `manifest.json`, replace the temporary `issue_tracker` URL with
   `https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY/issues` before publishing.
2. In HACS choose the menu for **Custom repositories**, paste your repository
   URL, select **Integration**, then add it. Install **VBox TV Gateway**.
3. Restart Home Assistant. In **Settings → Devices & services → Add
   integration**, choose **VBox TV Gateway** and enter the device IP.
4. If access to the device's ManageApp pages requires a username and password,
   enable the login option and enter them in the next step. The XML API is
   called without those credentials. Passwords are stored in the Home
   Assistant config entry and are never placed in URLs.

HACS requires a reachable GitHub repository to track installs and updates.
A downloaded ZIP by itself is for creating that repository or for manual
installation, not a URL accepted by HACS.

## Manual install

Copy `custom_components/vbox_gateway` into your Home Assistant
`/config/custom_components/` directory, restart Home Assistant and add the
integration in the UI.

## Data refresh and limitations

Tuner, system, service and streaming information is polled every 30 seconds.
Channel counts are refreshed at most once per hour. Web page failures leave
XML API sensors functional; web-only sensors then show unknown. The Basic
authentication option affects only ManageApp pages. Streaming details describe
the first active stream as entities and all active streams as attributes.
The list of tuned channels is used only to count TV and radio entries.

The sampled web page showed no recordings. Recording count parsing may require
adjustment if a future page with active recordings uses a different table
layout. Date and time fields are populated by browser JavaScript and are not
exposed as sensors. The integration has not been live tested inside the
owner's Home Assistant instance.
