.DEFAULT_GOAL := help

device ?=

.PHONY: help compile install monitor backend scan-ble restart shutdown info

compile:
	./tools/firmware compile $(if $(device),--device "$(device)")

install:
	./tools/firmware install $(if $(device),--device "$(device)")

monitor:
	./tools/firmware monitor

backend:
	@.venv/bin/python -m backend

restart:
	@curl --fail --silent --show-error -X POST http://localhost:8080/restart

shutdown:
	@curl --fail --silent --show-error -X POST http://localhost:8080/shutdown

info:
	@curl --fail --silent --show-error http://localhost:8080/info

scan-ble:
	@.venv/bin/python tools/scan-ble
