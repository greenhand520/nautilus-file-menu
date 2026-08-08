SHELL=/bin/bash
EXT_DIR=~/.local/share/nautilus-python/extensions
nautilus_path=`which nautilus`
POT_FILE=po/nautilus-file-menu.pot
PO_FILES=po/[a-z]*.po
SRC_FILES=nautilus_file_menu.py modules/*.py

# Compile MO from PO into target/{lang}/LC_MESSAGES/ (gettext standard layout)
define compile_po
	@for po in $(PO_FILES); do \
		lang=$$(basename $$po .po); \
		mkdir -p $(1)/$$lang/LC_MESSAGES; \
		msgfmt -o $(1)/$$lang/LC_MESSAGES/nautilus-file-menu.mo $$po; \
	done
endef

# --- Main targets ---

install:  ## Install extension to Nautilus extensions directory
	@rm -rf $(EXT_DIR)/nautilus-file-menu
	@rm -f $(EXT_DIR)/nautilus-file-menu.py
	@find modules -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	mkdir -p $(EXT_DIR)/nautilus-file-menu
	cp nautilus-file-menu.py $(EXT_DIR)
	cp nautilus_file_menu.py translation.py config.json VERSION README.md $(EXT_DIR)/nautilus-file-menu
	cp -rf modules $(EXT_DIR)/nautilus-file-menu
	$(call compile_po,$(EXT_DIR)/nautilus-file-menu/locale)
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true
	@echo ''
	@echo 'Installation complete. Edit config.json to customize:'
	@echo '  $(EXT_DIR)/nautilus-file-menu/config.json'
	@echo 'See README.md for configuration details.'

uninstall:  ## Remove extension from Nautilus extensions directory
	rm -f $(EXT_DIR)/nautilus-file-menu.py
	rm -rf $(EXT_DIR)/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true

# --- gettext targets ---

xgettext:  ## Extract translatable strings from source code into .pot
	xgettext -o $(POT_FILE) --from-code=UTF-8 \
		--keyword=gettext \
		--package-name=nautilus-file-menu \
		$(SRC_FILES)

msgmerge:  ## Update .po files from .pot template
	@for po in $(PO_FILES); do \
		echo "Merging $$po"; \
		msgmerge -U $$po $(POT_FILE); \
	done

msgfmt:  ## Compile .po files to .mo binary (in po/ for dev)
	$(call compile_po,po)

i18n: xgettext msgmerge msgfmt  ## Full i18n pipeline: extract → merge → compile

.PHONY: install uninstall xgettext msgmerge msgfmt i18n
