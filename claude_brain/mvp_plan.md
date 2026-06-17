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
| Field       | Type         | Notes                                  |
| ----------- | ------------ | -------------------------------------- |
| id          | Integer PK   |                                        |
| project_id  | FK → Project |                                        |
| name        | String       | e.g. "Concrete Mix Design"             |
| description | Text         | nullable                               |
| status      | Enum         | NOT_STARTED, SUBMITTED, A, B, C, D     |
| created_at  | DateTime     |                                        |
| revisions   | Revison      | A vendor data will have many revisions |

### Revision
| Field               | Type                | Notes                                |
| ------------------- | ------------------- | ------------------------------------ |
| id                  | Integer PK          |                                      |
| vendor_data_item_id | FK → VendorDataItem |                                      |
| revision_number     | Integer             | auto-incremented per VDI             |
| submit_document     | String              | file path, nullable                  |
| submitted_at        | DateTime            | nullable                             |
| return_document     | String              | file path, nullable (buyer's return) |
| returned_at         | DateTime            | nullable                             |
| comments            | Text                | buyer comments, nullable             |
| status              | Enum                | SUBMITTED, A, B, C, D                |
| created_at          | DateTime            |                                      |

---

## VDI Lifecycle

```
NOT_STARTED
    ↓  (user submits → creates Revision #1, attaches submittal doc)
SUBMITTED
    ↓  (buyer returns with comments → attaches return doc + comments)
RETURNED
    ↓  (user resubmits → creates Revision #2, attaches new submittal doc)
SUBMITTED
    ↓  (buyer approves → attaches approval doc)
APPROVED
```

The VDI `status` always reflects the current state. All history lives in the Revisions table.

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

| Method   | Route                    | Action                                              |
| -------- | ------------------------ | --------------------------------------------------- |
| GET      | `/`                      | Project list                                        |
| GET/POST | `/projects/new`          | Create project                                      |
| GET      | `/projects/{id}`         | Project detail                                      |
| GET/POST | `/projects/{id}/vdi/new` | Create VDI                                          |
| GET      | `/vdi/{id}`              | VDI detail + revision history                       |
| POST     | `/vdi/{id}/submit`       | Submit revision (upload submittal doc)              |
| POST     | `/vdi/{id}/return`       | Record buyer return (upload return doc + comments)  |
| POST     | `/vdi/{id}/approve`      | Mark approved (A or D status) (upload approval doc) |
|          |                          |                                                     |
|          |                          |                                                     |

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
│   └── schema.py
├── revision/
│   ├── router.py
│   ├── service.py
│   └── schema.py
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
