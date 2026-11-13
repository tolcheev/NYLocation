# NY Location

A small macOS app that sends the coordinates of Times Square, New York (40.7580, -73.9855), to a paired iPhone. One button starts the session; the same button disconnects it.

## Use on the configured Mac

1. Turn off Airplane Mode on the iPhone. Turn on Bluetooth and Location Services, and pair the iPhone with the Mac in Bluetooth settings. Initial USB trust may be required.
2. Open `NYLocation.app` and press **Подключить и сменить локацию**. If the app asks you to tap the Mac in the iPhone's Bluetooth settings, do so. Wait for the status saying coordinates are being sent.
3. Open Health Checklist on the iPhone and configure the available Sleep Apnea Notifications, ECG, Irregular Rhythm Notifications and Hypertension Notifications.
4. Press **Отключить iPhone**. Check that the iPhone has returned to its normal location. Restore any iPhone settings you changed for this session.

The app cannot configure Health settings on the user's behalf. Feature availability also depends on the iPhone, Apple Watch, software and Apple's eligibility checks. In one local test, Sleep Apnea Notifications became available while the Bluetooth session was active; the other features were configured by the user, but their availability was not independently verified by this project.

## Build

Requires macOS 14+, Swift 6/Xcode command line tools, and Python 3.9+. Run `./build.sh`; the app is written to `build/NYLocation.app`. The build signs the app locally with an ad hoc signature. A build for another Mac should be made on that Mac.

The app prefers Bluetooth when a local accessory identity or signing helper is configured. Otherwise it tries USB, which requires `pymobiledevice3`, a trusted cable connection and iPhone Developer Mode. `build.sh` uses `../.venv/bin/python3` for the USB dependency when present; set `NYLOCATION_PYTHON` to another Python executable at build time. USB location simulation was tested, but its effect on Health feature eligibility was not established.

## Bluetooth authentication

Bluetooth Classic iAP2 requires an accessory certificate and private key accepted by the iPhone. **This repository and its app builds contain no certificate or private key.** Put an authorized DER PKCS#7 certificate at `~/Library/Application Support/NYLocation/identity/certificate.p7b` and its matching DER PKCS#8 P-256 key at `~/Library/Application Support/NYLocation/identity/identity.pk8`, with access restricted to the current user. Alternatively, set `ACCESSORY_MFI_CERT_FILE` and `ACCESSORY_MFI_KEY_FILE`, or provide `NYLOCATION_AUTH_HELPER` implementing the JSON-lines interface in `Bluetooth/accessory_location/auth.py`.

Without an accepted identity or helper, the Bluetooth mode cannot authenticate. The public source therefore does not provide a ready-to-use Bluetooth setup for every Mac. Do not commit or redistribute private accessory keys.

The iAP2 implementation derives from [aur3l14no/accessory-location](https://github.com/aur3l14no/accessory-location). Attribution is in `Bluetooth/NOTICE`; the GPL-3.0-only license is in `LICENSE` and `Bluetooth/LICENSE`.
