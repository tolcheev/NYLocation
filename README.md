# NY Location

Set a connected iPhone's location to Times Square (40.7580, -73.9855) from a Mac. One app includes USB and Bluetooth. [Download NY Location for macOS](https://github.com/tolcheev/NYLocation/releases/latest/download/NYLocation.zip).

## USB

1. Unzip the download and open NYLocation.app. The build is ad hoc signed. If macOS blocks it, review the app under System Settings → Privacy & Security → Open Anyway.
2. Connect an unlocked iPhone using a data cable. Tap Trust if prompted. Turn on Location Services. For USB use iOS 17 or later and enable Developer Mode under Privacy & Security. Confirm the restart on the phone if requested.
3. Leave USB selected and press **Подключить и сменить локацию**. The first connection may download a developer disk image. Keep the cable connected during setup.
4. Once coordinates are being sent, open Health Checklist on the phone to configure features that are available to you. Press **Отключить iPhone** on the Mac before unplugging the cable to clear the simulation.

The download includes the app, Python and the USB libraries for Apple silicon and Intel. No separate Xcode or Python installation is required. Location simulation does not guarantee that a specific Health feature becomes available. The new packaged USB path has not yet been tested on a second physical Mac and iPhone.

## Bluetooth

Select Bluetooth, pair the iPhone with the Mac in Bluetooth settings, and press the same button. This mode requires an accepted accessory identity or an authorized signing helper on the Mac. The public build has no shared signer or credentials. On an unconfigured Mac, use USB. A Bluetooth prompt may ask you to tap the Mac on the iPhone.

For a locally authorized identity place the DER certificate and private key in the current user's Library/Application Support/NYLocation/identity directory as certificate.p7b and identity.pk8. Restrict key access to its owner. The helper interface and publisher HTTPS signer are in Bluetooth/accessory_location/auth.py. Set NYLOCATION_SIGNER_URL at build time to configure a publisher endpoint.

## Build

On Apple silicon with Rosetta, Swift 6 command line tools and uv, run `./prepare-runtime.sh` then `./build.sh`. Output is build/NYLocation.app. Package versions for each architecture are in Support/requirements-*.txt. USB uses pymobiledevice3 11.54.0. Bluetooth protocol attribution is in Bluetooth/NOTICE. Project license is GPL-3.0-only. Dependency notices are included with the bundled Python distributions and packages.
