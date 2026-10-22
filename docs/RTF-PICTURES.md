# Pictures inside source RTF documents

Select an RTF attachment under **Gestión → Documentos técnicos → Adjuntos y
textos PZH**. Choose **Imágenes RTF…** to consult its original embedded picture
destinations. The browser separates primary pictures, compatibility alternatives
and inert preview images belonging to objects. A picture destination count is not
a count of unique logical illustrations.

Choose a row to preview it. **Exportar imagen original…** writes its exact decoded
picture bytes; it does not write the containing RTF group. **Exportar vista PNG…**
saves the rendered preview, which can be reduced or approximate. Supported WMF
pictures can also open the existing vector zoom window. Exporting a view never
replaces the original image or changes the project history.

## Supported inputs and boundaries

- Hexadecimal picture data and explicit `bin` blocks, with bounded group parsing.
- PNG and JPEG previews subject to decoder and dimension checks.
- Examined uncompressed RGB DIB with a 40-byte header, bounded color tables and
  row strides. Top-down and bottom-up images are supported. A BMP wrapper is
  constructed for preview; the original DIB export remains unchanged.
- Structurally valid WMF, including a verified placeable header where present.
  Preview coverage and font limitations follow [Drawing previews](DRAWING-PREVIEWS.md).
- Original-byte export for formats without a supported preview, including source
  EMF, DIB variants and other opaque picture data.

Objects are counted and their inert picture previews can be inspected. OLE data,
linked objects and external image references are not activated or followed. This
is not an embedded spreadsheet/document editor. Unsupported data remains inside
the original RTF and the preserved PZH source.

The editable native text copy is separate. Its existing RTF export contains its
supported text styles; this browser does not insert source pictures into that
copy or reproduce their layout, cropping, scale or anchoring. To recover the full
original RTF, use **Exportar archivo…** on the parent attachment. Editing a text
copy does not remove the pictures from its retained original.

## Bounds and validation

One source RTF is read on selection. Extraction is limited to 16 MiB, 128 picture
destinations and 256 nested groups. Mixed/invalid picture encodings and truncated
binary blocks are rejected. Preview images are limited to 16 million source
pixels and 20,000 pixels on either axis; raster previews are reduced to at most
1,200 pixels per axis. The raw picture remains exportable when preview is refused.
Unknown formats are not passed to external programs. Original bytes, the source
group range and a SHA-256 digest are kept in the temporary inspection result.

The new index is derived on demand and adds no duplicated image payload or new
container version to saved projects. Existing native source preservation provides
the recovery path after save/reopen. Synthetic tests cover binary delimiters,
alternate picture groups, object previews, exact export, image pixels, dimensions,
invalid inputs, source preservation, stale worker results and unchanged history.

Try `openpresto/data/imagenes-rtf-demo.openpresto.json`, a synthetic project with a
one-pixel red PNG inside its source entity RTF. No third-party source picture is
included in that example.

The parser uses the published [RTF specification](https://learn.microsoft.com/en-us/previous-versions/office/developer/office2000/aa140277(v=office.10)).
DIB preview follows Microsoft's [bitmap storage](https://learn.microsoft.com/en-us/windows/win32/gdi/bitmap-storage)
and [BITMAPINFOHEADER stride rules](https://learn.microsoft.com/en-us/windows/win32/api/wingdi/ns-wingdi-bitmapinfoheader).

A selected local sample of 23 RTF streams from 14 files yielded 78 picture
references: 24 PNG and 54 WMF, including compatibility alternatives. All produced
previews under the supported projection. These are sample-based observations,
not proof of all source documents, all objects or complete visual fidelity.
Closed picture and vector dialogs are disposed to release their preview resources.
