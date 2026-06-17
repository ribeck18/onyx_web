# MVP Plan — Construction Project Tracker

## Overview
A web-based status and document tracker for vendor data items on construction projects. Built with FastAPI, Jinja2, SQLAlchemy, and Python.

---

## Core Concepts

- A **Project** represents a construction job.
- A **Vendor Data Item (VDI)** belongs to a project and tracks one piece of required vendor documentation.
- A **Revision** represents one round-trip with the buyer — a submittal sent out and (optionally) a return received back.

---

## Data Models

### Project
| Field          | Type            | Notes                                |
| -------------- | --------------- | ------------------------------------ |
| id             | Integer PK      |                                      |
| project_number | String          | usually something like 26-131        |
| name           | String          |                                      |
| description    | Text            | nullable                             |
| created_at     | DateTime        |                                      |
| vendor_data    | VendorDataItems | a project has many vendor data items |

### VendorDataItem
| Field                  | Type         | Notes                                                                  |
| ---------------------- | ------------ | ---------------------------------------------------------------------- |
| id                     | Integer PK   |                                                                        |
| project_id             | FK → Project |                                                                        |
| item_number            | Integer      | buyer-assigned, user-entered, required, unique per project             |
| submittal_number       | String       | nullable — internal number; typically `[project_id] - [incremented count of VDIs in project]`; often unassigned until submitted |
| name                   | String       | e.g. "Concrete Mix Design"                                             |
| description            | Text         | nullable                                                               |
| approval_type          | Enum         | ApprovalType: MANDATORY_APPROVAL, INFORMATION_ONLY                     |
| submit_code            | Enum         | SubmitCode (see below)                                                 |
| spec_drawing_reference | String       | nullable, not unique                                                   |
| notes                  | String       | nullable                                                               |
| status                 | Enum         | NOT_STARTED, SUBMITTED, A, B, C, D                                     |
| created_at             | DateTime     |                                                                        |
| revisions              | Revision     | A vendor data item will have many revisions                            |

`item_number` and `submittal_number` are genuinely separate. The **item number** is assigned by the *buyer* when they hand us the list of vendor data items to complete. The **submittal number** is the number *our company* assigns internally, often not until the item is actually submitted. The two frequently do not line up. Enforce `UniqueConstraint(project_id, item_number)`.

**ApprovalType enum**
| Member             | Value                |
| ------------------ | -------------------- |
| MANDATORY_APPROVAL | "mandatory_approval" |
| INFORMATION_ONLY   | "information_only"   |

**SubmitCode enum** — when the submittal is due relative to the project timeline.
| Member | Value   | Meaning                  |
| ------ | ------- | ------------------------ |
| AC     | "ac"    | As Completed             |
| AFI    | "afi"   | At Final Inspection      |
| ARO    | "aro"   | After Receipt of Order   |
| AT     | "at"    | After Test               |
| BC     | "bc"    | Before Contract Awarded  |
| BFA    | "bfa"   | Before Final Acceptance  |
| BFS    | "bfs"   | Before Fabrication Start |
| PDS    | "pds"   | Prior to Delivery on Site |
| PS     | "ps"    | Prior to Shipment        |
| PT     | "pt"    | Prior to Test            |
| PTC    | "ptc"   | Prior to Construction    |
| PTI    | "pti"   | Prior to Installation    |
| PTP    | "ptp"   | Prior to Purchase        |
| PTW    | "ptw"   | Prior to Welding         |
| ROS    | "ros"   | Prior to Removal Off-Site |
| TS     | "ts"    | Time of Shipment         |

### Revision
| Field               | Type                | Notes                                                         |
| ------------------- | ------------------- | ------------------------------------------------------------- |
| id                  | Integer PK          |                                                               |
| vendor_data_item_id | FK → VendorDataItem | indexed                                                       |
| revision_number     | Integer             | app-assigned, starts at 0, sequential per VDI                 |
| submit_document     | String              | file path, **required** (a Revision is always a submittal)    |
| submitted_at        | DateTime            | **required**                                                  |
| return_document     | String              | file path, nullable (buyer's return)                          |
| returned_at         | DateTime            | nullable                                                      |
| comments            | Text                | buyer comments, nullable                                      |
| status              | Enum (SubmitStatus) | reuses SubmitStatus; defaults to SUBMITTED; never NOT_STARTED |
| created_at          | DateTime            |                                                               |
| updated_at          | DateTime            |                                                               |

`revision_number` is sequential per VDI starting at 0, enforced by `UniqueConstraint(vendor_data_item_id, revision_number)`. A Revision is created only at submit-time with a document attached, so the submit side is non-nullable; only the buyer's return side is optional. Enum columns are stored as lowercase string values in non-native columns — see `docs/adr/0001-enum-storage-as-string-values.md`. File storage currently persists a path string; the retrieval mechanism (VPS) will be finalized later.

---

## VDI Lifecycle

```
NOT_STARTED
    ↓  (user submits → creates Revision 0, attaches submittal doc)
SUBMITTED
    ↓  (buyer returns with a Return Code + doc + comments)
   ├─ A or D → approved (terminal)
   └─ B or C → rejected
                  ↓  (user resubmits → creates next Revision)
              SUBMITTED → …
```

The buyer's return is a single event carrying a Return Code; A/D are approved (terminal) and B/C are rejected (resubmit). There is no separate "approve" step. The VDI `status` always equals the latest Return Code (or `NOT_STARTED`/`SUBMITTED`); all history lives in the Revisions table.

---

## Pages (Jinja2 Templates)

| Page | Route | Description |
|---|---|---|
| Project List | `GET /` | All projects, link to each |
| Project Detail | `GET /projects/{id}` | Project info + all VDIs with current status |
| VDI Detail | `GET /vdi/{id}` | Full revision history, current status, action buttons |
| Create Project | `GET/POST /projects/new` | Form |
| Create VDI | `GET/POST /projects/{id}/vdi/new` | Form |

---

## API / Form Actions (FastAPI Routes)

| Method | Route                  | Action                                                                       |
| ------ | ---------------------- | ---------------------------------------------------------------------------- |
| GET    | `/`                    | Project list                                                                 |
| POST   | `/projects`            | Create project                                                               |
| GET    | `/projects/{id}`       | Project detail                                                               |
| POST   | `/vdi`                 | Create VDI (`project_id` in body; 404 if project missing)                    |
| GET    | `/vdi?project_id=`     | List VDIs in a project                                                       |
| GET    | `/vdi/{id}`            | VDI detail                                                                   |
| PATCH  | `/vdi/{id}`            | Update VDI fields (status excluded — lifecycle-only)                         |
| DELETE | `/vdi/{id}`            | Delete VDI (cascades to revisions)                                           |
| GET    | `/vdi/{id}/revisions`  | Revision history for a VDI                                                    |
| POST   | `/vdi/{id}/submit`     | Submit: create next Revision (`submit_document` path), set status `SUBMITTED` |
| POST   | `/vdi/{id}/return`     | Record buyer return (`return_code` A/B/C/D, `return_document`, `comments`) on the latest submitted Revision; set status to the code |

There is no separate `approve` action — approval is a `return` carrying Return Code A or D (see the Return Code glossary entry in `CONTEXT.md`). Lifecycle transitions are guarded in `vdi.service` (submit only from `NOT_STARTED`/`B`/`C`; return only from `SUBMITTED`; `A`/`D` terminal); illegal transitions return HTTP 409. File handling is a path string only for now — real uploads under `/uploads/{project_id}/{vdi_id}/` remain post-MVP.

---

## File Storage
- Documents stored locally under `/uploads/{project_id}/{vdi_id}/` for MVP.
- FastAPI serves files as static or via a download route.

---

## MVP Scope (In / Out)

### In
- Project CRUD
- VDI CRUD
- Revision tracking with document uploads
- Status lifecycle enforcement (can't approve before submitting, etc.)
- Simple HTML UI via Jinja2

### Out (post-MVP)
- User authentication
- Email notifications to buyer
- PDF generation for submittals
- Cloud file storage
- API-only / frontend separation

---

## Folder Structure

```
app/
├── database.py
├── models/
│   ├── project.py
│   ├── vdi.py
│   └── revision.py
├── project/
│   ├── router.py
│   ├── service.py
│   └── schema.py
├── vdi/
│   ├── router.py
│   ├── service.py
│   ├── schema.py
│   └── revision/
│       ├── router.py
│       ├── service.py
│       └── schema.py
├── templates/
│   ├── base.html
│   ├── project/
│   │   ├── list.html
│   │   ├── detail.html
│   │   └── new.html
│   ├── vdi/
│   │   ├── detail.html
│   │   └── new.html
│   └── revision/
│       └── detail.html
├── static/
│   └── style.css
uploads/
claude_brain/
│   └── mvp_plan.md
```
