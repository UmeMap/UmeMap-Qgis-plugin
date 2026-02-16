#/***************************************************************************
# UmeMap QGIS Plugin
# Copyright (c) 2022 UmeMap - MIT License
# ***************************************************************************/

PLUGINNAME = UmeMap
PY_FILES = __init__.py plugin.py
UI_FILES = UmeMap_dialog_base.ui
EXTRAS = metadata.txt icon.png
EXTRA_DIRS = core features ui icons
COMPILED_RESOURCE_FILES = resources.py
RESOURCE_SRC = $(shell grep '^ *<file' resources.qrc | sed 's@</file>@@g;s/.*>//g' | tr '\n' ' ')

# Set QGISDIR to your QGIS plugin directory.
# Linux:   ~/.local/share/QGIS/QGIS3/profiles/default/python/plugins
# macOS:   ~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins
QGISDIR ?= .local/share/QGIS/QGIS3/profiles/default/python/plugins

PLUGINDIR = $(HOME)/$(QGISDIR)/$(PLUGINNAME)

.PHONY: default compile deploy package test clean

default:
	@echo "Available targets: compile, deploy, package, test, clean"

compile: $(COMPILED_RESOURCE_FILES)

%.py : %.qrc $(RESOURCE_SRC)
	pyrcc5 -o $@ $<

deploy: compile
	@echo "Deploying plugin to $(PLUGINDIR)"
	mkdir -p $(PLUGINDIR)
	cp -vf $(PY_FILES) $(PLUGINDIR)
	cp -vf $(UI_FILES) $(PLUGINDIR)
	cp -vf $(COMPILED_RESOURCE_FILES) $(PLUGINDIR)
	cp -vf $(EXTRAS) $(PLUGINDIR)
	@for dir in $(EXTRA_DIRS); do \
		cp -vfr $$dir $(PLUGINDIR)/; \
	done

package: compile
	@echo "Creating plugin zip package"
	rm -f $(PLUGINNAME).zip
	git archive --prefix=$(PLUGINNAME)/ -o $(PLUGINNAME).zip HEAD

test: compile
	@echo "Running tests"
	@-export PYTHONPATH=`pwd`:$(PYTHONPATH); \
		export QGIS_DEBUG=0; \
		export QGIS_LOG_FILE=/dev/null; \
		python -m pytest test/ -v || true

clean:
	rm -f $(COMPILED_RESOURCE_FILES)
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
