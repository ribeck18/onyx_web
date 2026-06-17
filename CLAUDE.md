## Rules
- Ask the user before importing a new package or library.
- Maintain a requirements.txt
- Keep md files, excluding README.md, and CLAUDE.md in the gitignore
- All new .md files (excluding README.md and CLAUDE.md) must be placed in the `claude_brain/` directory at the project root.
- As this is a FastAPI app, use async.

## Style

- Prefer simple implementation and code rather than clever implementations
- Avoid repetitive code; if something is done more than 5 times, make a function
- Keep files in the correct domain folder (i.e things about vendor data in the vdi folder)
## Conventions

- Git branch names are in camel case and use dashes. Example: Feature-FileSaves
- Variable and function names use snake case. No single-letter variables, even when writing a for loop.
- Type annotations: if the type is ambiguous or when the return type is unclear.
- Classes should be kept in separate files dedicated to only that class. The file name matches the class name.
- Use modern union syntax: str | None, not Optional[str]. list[Project], not List[Project].
- Use from __future__ import annotations at the top of any file that needs forward references or has circular import concerns.
- Keep data things sorted by domain; if it is vendor data code, store it in vdi/
	- There are some exceptions to this rule, such as when code touches several places. Make sure these types of files are stored and named meaningfully. 
	- You should try your best to separate by domain; this makes clear deep modules

## Naming
- Files: Lowercase snake_case for all .py files(seed_data.py, general_service.py). UPPER_SNAKE_CASE for .md files.
- Classes: PascalCase (Project, ReadSubmittal, UserManager).
- Functions and variables: snake_case (create_project, get_engine, read_project).
- Enum members: UPPER_SNAKE_CASE (NOT_STARTED, APPROVED_W_COMMENTS).
- Enum values: lowercase snake_case strings ("not_started", "approved_w_comments").

## Documentation

- Code should be self-documenting with clear variable, class, and function names.
- Write docstrings for all functions.
- When comments are written they should address the why rather than the what
## Packages

- Use minimal packages and libraries; prefer the standard library

## Database

- Use SQLAlchemy to interact with the database.
- Use the async engine and AsyncSession everywhere (service signatures take `session: AsyncSession`).
- Sessions are created in the route layer and passed down — services never create their own sessions.
- Create functions instantiate the model, add to session, then flush (not commit). Transaction control stays in the route layer.
- list getters should wrap the result in a list.
- Use Mapped[...] with mapped_column(...) for all columns. Always specify the SQLAlchemy type explicitly
- Use string-based relationship targets with TYPE_CHECKING-guarded imports to avoid circular dependencies

## FastAPI

- Every route file creates a single APIRouter
- Routes that deal with the database call service functions, commit, and return the schema

## Enums

- Inherit from enum.Enum (not StrEnum)

## Import Style

- Group imports: stdlib → third-party → local. No enforced separator comments required.

## Formatting

- Follow PEP 8 line length and whitespace conventions.
- One blank line between functions within a class or module.
- Two blank lines between top-level definitions (classes, standalone functions).
- Trailing commas on the last item of multi-line argument lists and collections.

## Folder Structure
```
app/
├── main.py
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
- Store other documents such as the readme or the .env in the root.
