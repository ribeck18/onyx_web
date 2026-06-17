# Context

## Glossary

### Project
A construction job. The top-level container for all work. Identified by a unique `project_number` (e.g. "26-131") and a human-readable `name`. Has no status of its own — its state is implied by the aggregate state of its VDIs.

### Vendor Data Item (VDI)
A single piece of required vendor documentation that belongs to a Project. Tracks its own lifecycle status from `NOT_STARTED` through approval. Has many Revisions.

### Revision
One round-trip with the buyer on a VDI — a submittal sent out and (optionally) a return received back. All history lives in Revisions; the VDI status always reflects the current state. A Revision always represents a real submittal; it is never a draft.

### Item Number
The identifier the buyer assigns to a VDI when handing us the list of required vendor data. Unique within a Project. Frequently does not match the Submittal Number.

### Submittal Number
The identifier our company assigns a VDI internally, often not until the item is submitted. Distinct from the buyer's Item Number.

### Return Code
The buyer's verdict on a submitted Revision: A or D mean approved; B or C mean rejected and require resubmittal.

### Approval Type
Whether a VDI requires the buyer's approval (Mandatory Approval) or is provided for reference only (Information Only).

### Submit Code
A short code on a VDI indicating when its submittal is due relative to the project timeline (e.g. PS — Prior to Shipment).
