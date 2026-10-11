.DEFAULT_GOAL := help

device ?=

.PHONY: help compile install monitor backend scan-ble

compile:
	./tools/firmware compile $(if $(device),--device "$(device)")

install:
	./tools/firmware install $(if $(device),--device "$(device)")

monitor:
	./tools/firmware monitor

backend:
	@.venv/bin/python -m backend

scan-ble:
	@.venv/bin/python tools/scan-ble
