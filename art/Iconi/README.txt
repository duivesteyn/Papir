Papir — paper-plane icon

Ivory paper plane with ruled lines on warm ink, with transparent outer
corners. The delivered suite this folder is derived from is archived at
art/Papir-macOS-IconSuite-v2.zip.

Files
- Papir-master-1024.png: current artwork, 1024 × 1024 (suite plane retoned to ink).
- Papir-1024.png through Papir-16.png: exports from the same master.
- Papir-Header-Mark.png: the plane as an ink silhouette on transparency, for the
  parchment app header and success badge.
- Papir-launcher-glyph-432.png: the Android launcher glyph — the plane on
  transparency, fitted to Android's 66dp safe circle. Android resources are
  generated from this by android/tools/make-icons.py, which only resizes it.
- Papir.icns: multi-resolution macOS icon container.
- AppIcon.appiconset: macOS asset catalog set (1x and 2x).
- Papir.iconset: source PNGs for iconutil.

Use
Add AppIcon.appiconset to your Xcode asset catalog and select AppIcon as the app icon set. Alternatively use Papir.icns for an app bundle that takes an ICNS resource. The Mac build also copies Papir-Header-Mark.png so the window header can show the mark beside the wordmark.

The color app icon is intended for Finder, Dock, and app identity. For a menu bar status item, use the suite's monochrome template glyph so it adapts to light and dark appearance.
