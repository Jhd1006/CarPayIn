.PHONY: test test-backend test-mock-card test-mock-pg test-pms android-compile

test: test-backend test-mock-card test-mock-pg test-pms

test-backend:
	cd services/carpayin-backend && python -m pytest tests/unit tests/api -q --import-mode=importlib

test-mock-card:
	cd services/mock-card && python -m pytest tests/unit tests/api -q --import-mode=importlib

test-mock-pg:
	cd services/mock-pg && python -m pytest tests/unit tests/api -q --import-mode=importlib

test-pms:
	cd services/pms && python -m pytest tests/unit tests/api -q --import-mode=importlib

android-compile:
	cd services/android-app && ./gradlew :app:compileDebugKotlin
