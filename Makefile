SHELL=/bin/bash
nautilus_path=`which nautilus`
install:
	mkdir -p ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	cp nautilus-file-menu.py ~/.local/share/nautilus-python/extensions
	cp nautilus_file_menu.py translation.py config.json ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	cp -rf modules ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	cp -rf translations ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true

uninstall:
	rm ~/.local/share/nautilus-python/extensions/nautilus-file-menu.py
	rm -rf ~/.local/share/nautilus-python/extensions/nautilus-file-menu
	@echo 'Restarting nautilus'
	@${nautilus_path} -q||true
