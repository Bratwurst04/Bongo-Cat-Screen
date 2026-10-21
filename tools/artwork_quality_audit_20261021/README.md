# Isolated artwork quality audit

Run with the existing project-local Python/Pillow environment:

```powershell
build/product-committee-2026-10-20/venv31316/Scripts/python.exe -B tools/artwork_quality_audit_20261021/run_audit.py --output build/artwork-quality-2026-10-21-local-new
```

The output must be a NEW directory inside this repository. The audit reads the
verified public C421/EBB source freezes, extracts the actual static image
converter without importing the Windows companion, and exercises the real
Python codec plus a small native host reference for the frozen compact-expansion
header and pinned LVGL color macro. This is not an app or firmware build.

Inputs are synthetic, apart from the public footer-alpha-only recognition
fixture. No user artwork, profile, network, COM or running application is used.
All host pictures are simulations. RGB565 previews use full-range bit expansion;
nearest zoom previews use Pillow, not the panel or an exact LVGL pixel oracle.
No enhancement, gamma command or product setting is applied.
