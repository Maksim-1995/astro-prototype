# Прозрачная героиня, версия 2

Режим: встроенный image_gen, редактирование исходного изображения.

Исходник: `dist/assets/hero-woman.png`.
Результат: `dist/assets/hero-foreground-v2.png`.
Параметр: `transparent_background=true`.

## Точный prompt

```text
Use case: background-extraction
Asset type: transparent foreground photographic layer for an interactive website scene.
Input images: Image 1 is the exact edit target. Remove its background, preserving its subject.
Primary request: extract this exact adult woman together with her dark plum armchair as a single foreground layer. Remove ALL of the surrounding plum interior/background and replace it with genuine transparent alpha.
Invariants: preserve this woman's exact identity, face, expression, natural chestnut hair, same hair length and strands, the closed dark blouse, dark trousers, exact seated pose, both hands, all fingers, armchair shape and upholstery, and the original warm amber/lavender lighting. Do not regenerate her as another person and do not alter her pose or clothing.
Composition/framing: portrait-oriented asset cropped close to the nontransparent woman-and-chair silhouette, with a small transparent margin above and beside it. Preserve the original lower crop at the knees and chair, no invented legs or feet.
Edges: natural detailed fine hair edges with alpha transparency between strands, clean edges of clothing and chair, no leftover backdrop and no broad soft rectangular glow.
Constraints: genuine transparent background; keep only the woman and her chair. No added shadows, no text, no logos, no watermark, no new objects. Do not print checkerboard into pixels.
```
