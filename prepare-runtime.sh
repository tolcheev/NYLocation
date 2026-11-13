#!/bin/zsh
set -euo pipefail
cd "${0:A:h}"
# Run on Apple silicon with Rosetta to package the x86_64 interpreter as well.
root="$PWD/build/runtime"
for arch in arm64 x86_64; do
    platform=$arch
    if [[ "$arch" == arm64 ]]; then platform=aarch64; fi
    spec="cpython-3.13.13-macos-$platform-none"
    uv python install --no-bin --install-dir "$PWD/build/toolchains" "$spec"
    src="$PWD/build/toolchains/$spec"
    target="$root/$arch"
    mkdir -p "$target/bin" "$target/lib"
    cp "$src/bin/python3.13" "$target/bin/python3"
    rsync -a --exclude __pycache__/ --exclude site-packages/ --exclude test/ --exclude tests/ "$src/lib/python3.13" "$target/lib/"
    uv pip install --only-binary cryptography --python "$src/bin/python3.13" --target "$target/lib/python3.13/site-packages" -r "Support/requirements-$arch.txt"
done
