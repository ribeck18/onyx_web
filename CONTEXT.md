# Context

## Glossary

### Project
A construction job. The top-level container for all work. Identified by a unique `project_number` (e.g. "26-131") and a human-readable `name`. Has no status of its own — its state is implied by the aggregate state of its VDIs.

### Vendor Data Item (VDI)
A single piece of required vendor documentation that belongs to a Project. Tracks its own lifecycle status from `NOT_STARTED` through approval. Has many Revisions.

### Revision
One round-trip with the buyer on a VDI — a submittal sent out and (optionally) a return received back. All history lives in Revisions; the VDI status always reflects the current state.
