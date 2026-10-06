# Art assets

The source of truth is `art/` at the repository root.

- `art/Iconi/Papir-master-1254.png`: original artwork.
- `art/Iconi/Papir-*.png`: retained exports.
- `art/Iconi/Papir.icns`: app bundle icon, copied by the Mac build script.
- `art/Iconi/AppIcon.appiconset/`: retained Xcode asset catalog.
- `art/Iconi/Papir.iconset/`: source exports for regenerating the ICNS.
- `art/Papir-icon-pack.zip`: retained original asset package.
- `art/Papir-art-style-spec.md`: colours, geometry and usage rules.

The Mac UI uses forest green `#123325` and ivory `#F3EADB`. The original master
and fixed exports remain useful even though the menu bar proposal was dropped.
Change master artwork first, then regenerate exports. The small copy in
`_screenshots/` is for README display; it is not the editable master.
