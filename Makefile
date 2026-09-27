.DEFAULT_GOAL := help

.PHONY: help compile install monitor backend scan-ble

help:
	@printf '%s\n' \
		'make compile  Compile firmware using ./arduino.json' \
		'make install  Compile and upload firmware' \
		'make monitor  Open the configured serial monitor' \
		'make backend  Run the backend in this terminal' \
		'make scan-ble  Scan for nearby LEGO hubs'

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
