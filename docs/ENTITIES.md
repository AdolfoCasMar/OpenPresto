# Native party directory

Management → Entidades contains an editable directory of project parties, including PZH entities without associated invoices or purchase contracts. Search covers names, contacts, addresses, telephone numbers and the other displayed fields.

The directory stores identification, contact details, postal information, fiscal identifiers and professional qualifications. Source fields and source identity remain preserved separately from editable values. Original monetary properties remain source information and do not create balances.

Native-copy import includes the available entity records in one batch. Repeating a copy adds missing records without overwriting native edits. The existing received-document supplier and issued-document customer records remain separate: changing this directory does not silently rename financial parties or change documents.

Commands: `entities.set` and `pzh.entities.copy`. The directory is available in reports and export through `entidades`. Projects containing it use container version 28; older builds may reject them. Undo/redo and save/load preserve both native edits and original properties.
