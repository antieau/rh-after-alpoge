PYTHON ?= python3.9
ENGINE ?= xelatex

.PHONY: all bootstrap tags check clean

all:
	$(PYTHON) tools/build.py --engine "$(ENGINE)"

bootstrap:
	$(PYTHON) tools/bootstrap.py

tags:
	$(PYTHON) tools/assign_tags.py

check:
	runtime/.venv/bin/python tools/check_edition.py
	runtime/.venv/bin/python tools/check_reading_views.py
	runtime/.venv/bin/python tools/check_pdf.py

clean:
	$(PYTHON) tools/build.py --clean
