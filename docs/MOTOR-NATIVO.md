# Application architecture

Core project and calculation modules are independent of Qt. Commands validate a private model before returning a result. Versioned persistence, undo/redo and isolated purchase and sales models help keep changes reviewable.

This note follows the current product scope. For the maintained English guide, see [Application architecture](ARCHITECTURE.md). Use the documentation supplied with an older release when reviewing that build; capabilities and validation may differ.

Related guides: [Features](FEATURES.md), [Compatibility](COMPATIBILITY.md), [Validation](VALIDATION.md) and [Licensing](LEGAL-NOTICE.md).
