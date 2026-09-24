# Bongo Cat sprite export

The sprite layers are 64x64 PNG files grouped by purpose:

- `body/`: normal body and ear-twitch body.
- `face/`: stock, blink, happy and sleepy faces.
- `paws/`: left down, right down and both paws up.
- `table/`: table layer.
- `effects/`: click and sleep effects.
- `EXPORT-ALL-PNG/`: all 15 PNG layers in one flat folder for quick export.
- `bongocat all.ase`: original layered Aseprite source.

Keep the transparent canvas and original 64x64 dimensions when replacing a
layer. The firmware combines the layers in this order: body, face, table,
paws, effects.
