# Art assets

The source of truth is `art/` at the repository root.

- `art/Iconi/Papir-master-1024.png`: original artwork.
- `art/Iconi/Papir-*.png`: retained exports.
- `art/Iconi/Papir-Header-Mark.png`: ink-silhouette plane for the Mac window header.
- `art/Iconi/Papir.icns`: app bundle icon, copied by the Mac build script.
- `art/Iconi/AppIcon.appiconset/`: retained Xcode asset catalog.
- `art/Iconi/Papir.iconset/`: source exports for regenerating the ICNS.
- `art/Papir-macOS-IconSuite-v2.zip`: delivered v2 suite (dark, light,
  transparent, menu bar, document and web assets).
- `art/Papir-icon-pack.zip`: retained original asset package.
- `art/Papir-art-style-spec.md`: colours, geometry and usage rules.

The Mac and Android interfaces now use ink `#1F1B16` on parchment `#F3EADB`;
the Mac app icon is retoned to warm ink; the Android launcher art still uses
the suite's forest field. The master and fixed exports remain useful even
though the menu bar proposal was dropped. Change master artwork first, then
regenerate exports. The small copy in `_screenshots/` is for README display; it
is not the editable master.
