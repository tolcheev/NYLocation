#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
mkdir -p build
bridge_args=(-mmacosx-version-min=14.0)
if [[ "${NYLOCATION_PORTABLE:-0}" == 1 ]]; then
    slices=()
    for arch in arm64 x86_64; do
        target="$arch-apple-macosx14.0"
        swift build -c release --triple "$target"
        slices+=("$(swift build -c release --triple "$target" --show-bin-path)/NYLocation")
    done
    bin="$PWD/build/NYLocation.universal"
    xcrun lipo -create "${slices[@]}" -output "$bin"
    bridge_args+=(-arch arm64 -arch x86_64)
else
    swift build -c release
    bin="$(swift build -c release --show-bin-path)/NYLocation"
fi
stage="$(mktemp -d "$PWD/build/nylocation.XXXXXX")"
trap 'rm -rf "$stage"' EXIT
app="$stage/NYLocation.app"
contents="$app/Contents"
mkdir -p "$contents/MacOS" "$contents/Resources/Bluetooth" "$contents/Resources/Helpers"
cp "$bin" "$contents/MacOS/NYLocation"
cp Support/Info.plist "$contents/"
if [[ "${NYLOCATION_PORTABLE:-0}" == 1 ]]; then
    plutil -insert NYLocationBluetoothOnly -bool YES "$contents/Info.plist"
fi
if [[ -n "${NYLOCATION_SIGNER_URL:-}" ]]; then
    PYTHONPATH=Bluetooth /usr/bin/python3 -B -c 'import os; from accessory_location.auth import ReleaseSigner; ReleaseSigner(os.environ["NYLOCATION_SIGNER_URL"])'
    plutil -insert NYLocationSignerURL -string "$NYLOCATION_SIGNER_URL" "$contents/Info.plist"
fi
devicePython="${NYLOCATION_PYTHON:-$PWD/../.venv/bin/python3}"
if [[ "${NYLOCATION_PORTABLE:-0}" != 1 && -x "$devicePython" ]]; then
    "$devicePython" -B -c 'from pymobiledevice3.remote.native_tunnel import NativeRemotedTunnel'
    /usr/libexec/PlistBuddy -c "Add :NYLocationDevicePython string $devicePython" "$contents/Info.plist"
fi
cp -R Bluetooth/accessory_location "$contents/Resources/Bluetooth/"
cp Bluetooth/{session.py,NOTICE,LICENSE} "$contents/Resources/Bluetooth/"
xcrun clang "${bridge_args[@]}" -fobjc-arc -framework Foundation -framework IOBluetooth Bluetooth/bluetooth_bridge.m -o "$contents/Resources/Helpers/bluetooth-bridge"
codesign --force --sign - "$contents/Resources/Helpers/bluetooth-bridge"
codesign --force --sign - "$app"
codesign --verify --deep --strict "$app"
if [[ -e build/NYLocation.app ]]; then mv build/NYLocation.app "$stage/previous.app"; fi
mv "$app" build/NYLocation.app || { [[ ! -d "$stage/previous.app" ]] || mv "$stage/previous.app" build/NYLocation.app; exit 1; }
