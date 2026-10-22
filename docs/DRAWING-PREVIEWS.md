# Drawing previews

Open **Gestión → Documentos técnicos → Adjuntos y textos PZH**, then select a
WMF drawing. The application projects supported geometry into an internal SVG
and renders a bounded image on demand. Importing a project does not render every
drawing. No original executable, Windows GDI, Wine or external converter is used.

Choose **Ampliar dibujo…** for the vector window. Use the wheel or **Acercar** /
**Alejar** to zoom, drag to pan, and **Ajustar** to fit the drawing. Viewing,
zooming and exporting do not change the project or add undo entries.

**Exportar vista SVG…** saves the generated approximate preview. It is separate
from **Exportar archivo…**, which recovers the original identified stream, and
**Exportar envoltura original…**, which preserves the decompressed source envelope.
For a diagnosed zero-sized closing record, the preview uses the explicitly
identified corrected-EOF copy and says so. The retained original is unchanged.

## Supported projection

- Lines, polylines, polygons and polygon rings, rectangles, ellipses, radial arcs
  and individual colored pixels.
- Examined solid/null brushes, supported pen styles, window origin/extents,
  object selection/deletion, saved contexts and intersected rectangular clipping.
- Basic ANSI text with supported font properties, alignment and rotation.
  Font appearance depends on installed fonts and is labelled approximate.
- Examined DWORD context values and additional pen bytes are identified in the
  diagnostics; additional bytes are preserved outside the projection.

The window labels the view as approximate. Unsupported records and limitations
are listed explicitly. A partial view can omit advanced text spacing, indexed
palettes, printer extensions, embedded bitmaps or additional mapping operations.
It is not a complete GDI implementation, a CAD editor or a drawing quantity
measurement tool. Do not use the preview to infer missing geometry or dimensions.
DWG remains a preserved source asset without a native drawing preview.

Input record sizes, EOF, object links, point counts, nesting, generated SVG size
and image dimensions are bounded. SVG output consists only of generated shapes,
escaped text and internal clip paths; it loads no external resources.

## Example and validation boundary

Try `openpresto/data/dibujos-vectoriales-demo.openpresto.json`, a synthetic drawing
with a known red polyline. Tests check its coordinates, actual rendered pixels,
clipping, rings, arcs, zoom, export, invalid data rejection and unchanged history.
The local 22-WMF reference set produced renderable previews; 21 reported partial
coverage or font/variant approximations. Rendering without an exception does not
establish pixel equivalence with the source application. Private reference works
and their generated previews are not distributed.

The implementation follows the published [MS-WMF specification](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/),
including [object table allocation](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/aeab62b8-03ab-48c0-8176-09c392f3c9da)
and [radial arc records](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-wmf/742097b4-5879-4c36-b57e-77e7cc152253).
