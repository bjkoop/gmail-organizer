#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

if command -v python3 >/dev/null 2>&1; then
	python3 launch_web.py
else
	python launch_web.py
fi
