.PHONY: proof test test-stateful soak-test kill-recover parallel-test audit

test:
	source venv/bin/activate && PYTHONPATH=. pytest tests/test_phase1.py tests/test_phase2.py tests/test_phase3.py

test-stateful:
	source venv/bin/activate && PYTHONPATH=. pytest tests/test_stateful.py -v

parallel-test:
	source venv/bin/activate && PYTHONPATH=. python scripts/parallel_test.py

kill-recover:
	source venv/bin/activate && PYTHONPATH=. python scripts/kill_recover_test.py

soak-test:
	source venv/bin/activate && PYTHONPATH=. python scripts/soak_test.py

audit:
	psql -U rishi -d payment_orchestrator -f audit.sql

proof: test test-stateful parallel-test kill-recover soak-test audit
	@echo "All proof tests completed successfully!"
