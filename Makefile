.PHONY: install

# Dev shortcut: build and install the native Arch/CachyOS pacman package
# from this checkout via the bundled PKGBUILD (see packaging/arch/PKGBUILD
# and the "On Arch Linux / CachyOS" section of README.md).
install:
	cd packaging/arch && makepkg -si
