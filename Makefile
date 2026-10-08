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
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install --quiet -e . && python -m backend

scan-ble:
	@test -d .venv || python3 -m venv .venv
	@. .venv/bin/activate && pip install --quiet -e . && ./tools/scan-ble
