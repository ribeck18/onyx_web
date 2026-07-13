# JSA revisions use ordered file links while File remains decoupled

A JSA Revision has one to three submitted files and, when rejected, one to three returned markup files. Rather than make `File` domain-aware or force that cardinality into fixed columns, JSA-specific ordered link rows will point to the generic `File` storage leaf and distinguish submitted from returned groups. This extends ADR 0003: `File` remains reusable and ignorant of business domains, while JSA owns its package structure and lifecycle validation.
