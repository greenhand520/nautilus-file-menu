SHELL=/bin/bash
nautilus_path=`which nautilus`
install:
	@rm -rf ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	@rm -f ~/.local/share/nautilus-python/extensions/nautilus-file-menu.py
	@find modules -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	mkdir -p ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	cp nautilus-file-menu.py ~/.local/share/nautilus-python/extensions
	cp nautilus_file_menu.py translation.py config.json ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	cp -rf modules ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	cp -rf translations ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true

uninstall:
	rm -f ~/.local/share/nautilus-python/extensions/nautilus-file-menu.py
	rm -rf ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true
