#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
build_root=${MAC_BUILD_DIR:-"$project_dir/.build-mac"}
output_root=${MAC_OUTPUT_DIR:-"$project_dir/dist"}
python_bin=${PYTHON:-python3}
"$project_dir/mac/native/build.sh"
"$python_bin" -m PyInstaller --noconfirm --onefile --name 'Codespace Desktop Host' \
  --collect-all av --collect-all aiortc --paths "$project_dir/mac" \
  --distpath "$build_root/dist" --workpath "$build_root/build" --specpath "$build_root" "$project_dir/mac/host.py"
folder="$output_root/Codespace Desktop Mac"
mkdir -p "$folder"
cp "$build_root/dist/Codespace Desktop Host" "$folder/"
cp "$project_dir/mac/bin/ScreenEncoder" "$folder/"
cp "$project_dir/mac/Start Mac Host.command" "$project_dir/mac/Change Connection.command" "$folder/"
cp "$project_dir/mac/README-Mac.txt" "$folder/"
chmod +x "$folder/Codespace Desktop Host" "$folder/ScreenEncoder" "$folder/Start Mac Host.command" "$folder/Change Connection.command"
codesign --verify --strict "$folder/ScreenEncoder"
codesign --verify --strict "$folder/Codespace Desktop Host"
(cd "$output_root" && /usr/bin/zip -q -r 'Codespace-Desktop-Mac-0.2.2.zip' 'Codespace Desktop Mac')
printf 'Created %s\n' "$output_root/Codespace-Desktop-Mac-0.2.2.zip"
