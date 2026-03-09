#!/bin/bash
set -e
apt-get install -y fonts-nanum || true
pip install -r requirements.txt
