# Technical documentation and PZH entity texts

Open **Gestión → Documentación técnica**, also available from **Seguimiento**,
to create and edit native plain-text documents. References are unique. Changes,
removal and source copying use application commands and support undo/redo.
Plain-text-only documents use JSON container version 35. Documents with separate
original payloads use version 40.
Earlier projects remain readable; older builds do not read the new container.

**Origen PZH · textos de entidades** lists the source text index from table 23.
The reader validates each explicit entity code and physical record offset;
it does not guess associations by text similarity or record order. Source
records and index entries must have valid bounds and unique associations.
Header variants supported in a54 are handled by the same reader.

Select an indexed entry to preview its text. Reading and decompression run in
a background worker; only the selected record is decompressed. Stale results
from a previous selection or project are ignored. Source catalogues are cached
against their archive identity, not rebuilt just because a native field changes.

**Copiar texto PZH** creates an editable plain-text copy with the original
source digest, entity code and record offset. Repeating the operation preserves
existing native edits. Source content is never overwritten. The exact original
RTF, images or embedded data remain in the preserved PZH. New native copies also
retain the decompressed original payload, format, byte length and SHA-256 digest.
This is separate from the editable plain-text projection. No source library
content from real projects is bundled with the application.

Source text records are bounded to 16 MiB unpacked. Native documents allow up
to 4 Mi characters each and 64 MiB of combined UTF-8 text, with at most 10,000
documents. Missing or unsupported source records produce an explicit error;
they do not create empty successful copies. Source preview does not post any
budget, invoice, production, certification or cash operation.

Export the native text listing or complete text table through the shared report
engine. The package includes a small project-owned synthetic source example,
`openpresto/data/technical-documents-demo.openpresto.json`. It demonstrates an
encoded header, explicit text index, source preview and native editable copy.

The four local reference datasets contain 880, 72, 72 and 2,543 indexed texts.
All index offsets and entity-code links were checked. A selected text was
previewed and copied in each file; this does not establish complete RTF/layout,
attachment or building-book equivalence for all their contents.

## Recover the original document

Choose **Exportar original** to save the decompressed RTF or original CP1252 text
bytes to a file you select. Editing the native plain text does not alter these
bytes. Export does not open or execute the file. Embedded objects and images remain
inside their original RTF envelope; they are not individually decoded attachments.

For a copy created by an older version, choose **Conservar original PZH**, or copy
the same source text again. The source file digest, entity code and record offset
must match. This attaches the original without overwriting native edits and
supports undo/redo. The source preview only reads the selected document; ordinary
navigation does not attach or decompress every document.

Each payload is bounded to 16 MiB and validated by size, format and SHA-256.
Combined native text and original payloads are bounded to 64 MiB. Base64 overhead
is additional container storage. This preserves bytes; it does not provide native
rich-text editing or guarantee visual equivalence with the source application.
