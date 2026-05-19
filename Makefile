.PHONY: test test-backend

test:
	cd services/carpayin-backend && python -m pytest

test-backend:
	cd services/carpayin-backend && python -m pytest

