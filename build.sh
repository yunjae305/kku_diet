#!/bin/bash
set -e
apt-get install -y fonts-nanum fonts-nanum-extra 2>/dev/null || true
mkdir -p fonts
find /usr/share/fonts -name "NanumGothic.ttf" -exec cp {} fonts/NanumGothic.ttf \; 2>/dev/null || true
pip install -r requirements.txt
