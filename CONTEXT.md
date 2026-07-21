# Context

## Glossary

### Project
A construction job. The top-level container for all work. Identified by a unique `project_number` (e.g. "26-131") and a human-readable `name`. Has no status of its own — its state is implied by the aggregate state of its VDIs.

### Vendor Data Item (VDI)
A single piece of required vendor documentation that belongs to a Project. Tracks its own lifecycle status from `NOT_STARTED` through approval. Has many Revisions.

### VDI Revision
One round-trip with the buyer on a VDI — a submittal sent out and (optionally) a return received back. All history lives in VDI Revisions; the VDI status always reflects the current state. A VDI Revision always represents a real submittal; it is never a draft.
_Avoid_: JSA revision

### Job Safety Analysis (JSA)
The single project-level safety analysis submitted for approval. It has a history of JSA Revisions; its current status is Submitted, Approved, or Rejected. A submitted package contains one to three files and may include a competent-person roster; Onyx does not track competent persons separately. Rejection retains one to three buyer-marked-up return files; approval applies to the submitted package. Internal notes belong to the JSA itself, rather than any revision.
_Avoid_: safety document

### JSA Revision
One submitted JSA package and its approval decision. The submitted package and a rejection return each contain one to three files; approved revisions have no separate return files. Either decision may carry buyer comments.
_Avoid_: VDI revision

### Project Document (ProjectDoc)
A document associated with a Project that we **receive and record** but do not submit or get approved — drawings, specifications, special conditions, contracts, the vendor data schedule sheet, addendums, and the like. Contrast with a Vendor Data Item, which we submit to the buyer for approval. Explicitly excludes RFIs, RECs, and JSAs, which are separately modeled features. One ProjectDoc represents one logical document; a 40-page drawing set is a single document stored as one file per version. Carries our own **label** (a required, non-unique name we assign — e.g. "E-101", "Contract"), set once and reused across all its versions, and a required document **type**. Has no lifecycle/status of its own.

### Request for Information (RFI)
A project-scoped question submitted to the buyer to resolve missing, conflicting, or unclear project information. Identified within a Project by a required, unique, free-form RFI Number, which remains immutable after first submission, and a required title; its lifecycle is Not Started, Submitted, Approved, or Rejected. Both Approved and Rejected RFIs may be resubmitted as a new RFI Revision.
_Avoid_: clarification request

### RFI Revision
One submitted RFI and its buyer decision. It has one submitted file, an optional buyer return file, and optional buyer comments; it is created only by submitting or resubmitting its RFI.

### Document Version (DocVersion)
An internally-numbered version of a Project Document — version control, not a submittal. Each time we receive an updated file we record a new DocVersion; the file always lives on the version, never on the Project Document itself. Each version carries an auto-incremented `version_number` (1, 2, 3…) that **we** generate as `max + 1` per document — the issuer does not assign it. Its human-facing name "{label} Version {n}" is composed for display from the parent's label, not stored. Distinct from a (VDI) Revision: no submit/return cycle, no return code, no external assignment. The current version is simply the most recently created one; the Project Document's updated date tracks that version's creation. A Project Document can never have zero versions — creating one always records Version 1 with its file.

### Item Number
The identifier the buyer assigns to a VDI when handing us the list of required vendor data. Unique within a Project. Frequently does not match the Submittal Number.

### Submittal Number
The identifier our company assigns a VDI internally, often not until the item is submitted. Distinct from the buyer's Item Number.

### Return Code
The buyer's verdict on a submitted Revision: A or D mean approved; B or C mean rejected and require resubmittal.

### Approval Type
Whether a VDI requires the buyer's approval (Mandatory Approval) or is provided for reference only (Information Only).

### Open Item
A VDI whose lifecycle is not yet finished — its status is anything other than an approved terminal code (A or D). The project gallery surfaces the count of Open Items per project ("N OPEN", or "ALL CLEAR" when none remain).
_Avoid_: outstanding, pending, unresolved.

### Submit Code
A short code on a VDI indicating when its submittal is due relative to the project timeline (e.g. PS — Prior to Shipment).

### User
A person allowed to use Onyx. Authenticated through the company's Microsoft (Entra) directory and identified canonically by their immutable Entra `oid`; their email is held only for provisioning and display. A User exists solely because an Admin created them — Onyx has no self-signup.

### Admin
A User additionally privileged to provision and manage other Users. The only role distinction in Onyx: it gates account management, not data — every User can see every Project.

### Provision
The act of an Admin creating a User (by email) before that person has ever signed in. The account becomes usable the first time the person authenticates with Microsoft, at which point it is permanently bound to their Entra identity.
