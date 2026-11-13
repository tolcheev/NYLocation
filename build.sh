#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
swift build -c release
bin="$(swift build -c release --show-bin-path)/NYLocation"
mkdir -p build
stage="$(mktemp -d "$PWD/build/nylocation.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
app="$stage/NYLocation.app"
contents="$app/Contents"
mkdir -p "$contents/MacOS" "$contents/Resources/Bluetooth" "$contents/Resources/Helpers"
cp "$bin" "$contents/MacOS/"
cp Support/Info.plist "$contents/"
devicePython="${NYLOCATION_PYTHON:-$PWD/../.venv/bin/python3}"
if [[ -x "$devicePython" ]]; then
    "$devicePython" -B -c 'from pymobiledevice3.remote.native_tunnel import NativeRemotedTunnel'
    /usr/libexec/PlistBuddy -c "Add :NYLocationDevicePython string $devicePython" "$contents/Info.plist"
fi
cp -R Bluetooth/accessory_location "$contents/Resources/Bluetooth/"
cp Bluetooth/{session.py,NOTICE,LICENSE} "$contents/Resources/Bluetooth/"
xcrun clang -fobjc-arc -framework Foundation -framework IOBluetooth Bluetooth/bluetooth_bridge.m -o "$contents/Resources/Helpers/bluetooth-bridge"
codesign --force --sign - "$contents/Resources/Helpers/bluetooth-bridge"
codesign --force --sign - "$app"
codesign --verify --deep --strict "$app"
if [[ -e build/NYLocation.app ]]; then mv build/NYLocation.app "$stage/previous.app"; fi
mv "$app" build/NYLocation.app || { [[ ! -d "$stage/previous.app" ]] || mv "$stage/previous.app" build/NYLocation.app; exit 1; }
