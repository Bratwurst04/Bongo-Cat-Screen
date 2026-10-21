# Test-only Windows x64 C declarations

These headers declare the existing Windows C runtime ABI for the installed
MSVC compiler when its standard header pack is absent. They are used only by
`lvgl_viewport_host.py`; production firmware never includes this directory.
Malloc, strings and math link to the real UCRT. LVGL itself, its software
renderer and fonts are compiled from the separately verified 8.3.11 dependency.
No library/SDK is installed and no LVGL function is replaced by a stub.

The host uses `/we4013`, so an undeclared C function fails compilation. Its
effective assertion handler calls `abort`, and the varargs ABI is checked with
the actual LVGL formatter. Linux uses normal system headers; that branch has
not been locally verified. This directory is not a general C or C++ SDK.
