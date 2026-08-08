SHELL=/bin/bash
EXT_DIR=~/.local/share/nautilus-python/extensions
nautilus_path=`which nautilus`
POT_FILE=po/nautilus-file-menu.pot
PO_FILES=po/*.po
SRC_FILES=nautilus_file_menu.py modules/*.py

# Compile MO from PO into po/{lang}/LC_MESSAGES/ (gettext standard layout)
define compile_po
	@for po in $(PO_FILES); do \
		lang=$$(basename $$po .po); \
		dest=po/$$lang/LC_MESSAGES; \
		mkdir -p $$dest; \
		msgfmt -o $$dest/nautilus-file-menu.mo $$po; \
	done
endef

install:
	@rm -rf $(EXT_DIR)/nautilus-file-menu
	@rm -f $(EXT_DIR)/nautilus-file-menu.py
	@find modules -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	mkdir -p $(EXT_DIR)/nautilus-file-menu
	cp nautilus-file-menu.py $(EXT_DIR)
	cp nautilus_file_menu.py translation.py config.json $(EXT_DIR)/nautilus-file-menu
	cp -rf modules $(EXT_DIR)/nautilus-file-menu
	$(compile_po)
	cp -rf po $(EXT_DIR)/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true

uninstall:
	rm -f $(EXT_DIR)/nautilus-file-menu.py
	rm -rf $(EXT_DIR)/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true

# --- gettext targets ---

xgettext:  ## Extract translatable strings from source code
	xgettext -o $(POT_FILE) --from-code=UTF-8 \
		--keyword=gettext \
		--package-name=nautilus-file-menu \
		$(SRC_FILES)

msgmerge:  ## Update PO files from POT template
	@for po in $(PO_FILES); do \
		echo "Merging $$po"; \
		msgmerge -U $$po $(POT_FILE); \
	done

msgfmt:  ## Compile PO files to MO binary
	$(compile_po)

i18n: xgettext msgmerge msgfmt  ## Full i18n pipeline: extract → merge → compile

.PHONY: install uninstall xgettext msgmerge msgfmt i18n
