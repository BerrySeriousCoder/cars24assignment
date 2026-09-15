PYTHON ?= python3
CONFIG ?= new
MODE ?= live
RUN_ID ?= $(shell date -u +%Y%m%dT%H%M%S)-$(CONFIG)
OUT ?= results/$(MODE)/$(RUN_ID)

.PHONY: test eval run smoke ablation help
help:
	@echo 'make test | make smoke | make eval CONFIG=old|new|degraded MODE=live | make ablation'
test:
	$(PYTHON) -m op02.verify
run:
	$(PYTHON) -m op02.runner --config $(CONFIG) --mode $(MODE) --output $(OUT)
eval: run
	$(PYTHON) -m op02.eval_report --run $(OUT)
smoke:
	bash scripts/reproduce.sh smoke
ablation:
	bash scripts/reproduce.sh ablation
