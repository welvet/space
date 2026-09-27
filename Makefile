.DEFAULT_GOAL := help

.PHONY: help compile install monitor backend scan-ble

compile:
	./tools/arduino compile

install:
	./tools/arduino install

monitor:
	./tools/arduino monitor

backend:
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install --quiet -e . && python -m backend

scan-ble:
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install --quiet -e . && ./tools/scan-ble
