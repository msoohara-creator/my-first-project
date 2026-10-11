# 国税専門官募集 — RPG title-screen recruitment poster (B3)

![preview](output/poster_preview.png)

| File | What it is |
| --- | --- |
| `output/poster_B3.png` | Print render, 4368 × 6184 px (B3 364 × 515 mm ≈ 305 dpi) |
| `output/poster_B3.pdf` | Same render as a single-page B3 PDF |
| `output/poster_preview.png` | 1092 × 1546 preview |
| `poster.html` | Layout: all text and UI windows, layered over the pixel art |
| `build_art.py` | Draws every pixel-art layer into `art/` (Python 3 + Pillow + NumPy) |
| `render.cjs` | Renders `poster.html` with headless Chromium (Playwright) |

## Rebuild

```sh
cd poster
python3 build_art.py   # regenerate art/*.png
node render.cjs        # regenerate output/ (needs network access for Google Fonts)
```

Open `poster.html` in a browser for a live, window-fitted view (the ▼ in the notice blinks there).

## Structure

The page is laid out on a 546 × 773 dot grid (1 dot = 1 CSS px = ⅔ mm at B3), top to bottom:

1. **Title**: "国税専門官募集" (Dela Gothic One, white with a thick navy outline) on a gold emblem plate with pixel-stepped edges
2. **Catch copy**: "Lv.1から、社会のど真ん中へ。", plain white bold with a thin navy outline
3. **Main visual**: four navy-suited characters (tablet, pointing + notepad, laptop, document file) on a soft spotlight; four framed scene panels with command tabs; the `LV 1` status bar
4. **Notice window**: gold glow, おしらせ in yellow, ▼ at the end
5. **Command window**: 2 × 2 commands with ▶ on the first
6. **Information band**: an empty exam-date area, two name-entry search windows, and two blank QR squares

Depth comes from three layers: the backdrop is blurred and desaturated in CSS (`#bg`), the panels are slightly softened and desaturated (`.panel img`), and the characters and UI stay sharp at full saturation.

## Filling in the blanks before printing

- **Exam dates**: put the text inside `#dates` in `poster.html`
- **QR codes**: put an `<img>` of each real QR code inside the two `.qr` boxes (66 dots ≈ 44 mm square)

Then run `node render.cjs` again.
