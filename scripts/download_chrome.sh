#!/usr/bin/env bash
# Downloads matching Chrome for Testing and ChromeDriver into downloads/.
#
#   ./scripts/download_chrome.sh                 # latest stable version
#   ./scripts/download_chrome.sh 142.0.7444.59   # a specific version

set -euo pipefail
cd "$(dirname "$0")/.."

base_url="https://storage.googleapis.com/chrome-for-testing-public"
latest_url="https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE"

version="${1:-$(curl -fsSL "$latest_url")}"
echo "Chrome version: $version"

mkdir -p downloads

download() {
    local folder="$1"
    local exe="downloads/$folder/$2"

    # Skip the download if the right version is already there
    if [[ -x "$exe" && "$("$exe" --version 2>/dev/null) " == *" $version "* ]]; then
        echo "$folder is already up to date."
        return
    fi

    echo "Downloading $folder..."
    curl -fL --progress-bar "$base_url/$version/linux64/$folder.zip" -o "downloads/$folder.zip"
    rm -rf "downloads/$folder"
    unzip -q "downloads/$folder.zip" -d downloads
    rm "downloads/$folder.zip"
}

download chromedriver-linux64 chromedriver
download chrome-linux64 chrome
