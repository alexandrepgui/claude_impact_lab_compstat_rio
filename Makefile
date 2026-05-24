PYTHON ?= python3
HOST ?= 127.0.0.1
PORT ?= 8787
KILL_PORTS ?= $(PORT) 8765

.PHONY: dev ui ui-dev kill-ui check-ui

dev: check-ui kill-ui ui-dev

ui:
	$(PYTHON) ui/pipeline_server.py --host $(HOST) --port $(PORT)

ui-dev:
	$(PYTHON) ui/reload_server.py --host $(HOST) --port $(PORT)

kill-ui:
	@for port in $(KILL_PORTS); do \
		pids="$$(lsof -tiTCP:$$port -sTCP:LISTEN 2>/dev/null)"; \
		if [ -n "$$pids" ]; then \
			echo "Killing UI server on $(HOST):$$port: $$pids"; \
			kill $$pids; \
		else \
			echo "No UI server listening on $(HOST):$$port"; \
		fi; \
	done

check-ui:
	$(PYTHON) -m py_compile ui/pipeline_server.py ui/reload_server.py
