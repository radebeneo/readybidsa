# Stack Profiles

A profile adapts the scaffold to a technology stack. `eck init --profile <id>` applies it on top of `scaffold/`.

| Profile | Use for |
| --- | --- |
| `generic` (default) | Any stack. Stack-neutral templates with every stack decision left to fill in. |

## How a profile works

```text
profiles/<id>/
├── profile.json   Name, description, parent profile and extra context files
├── tokens/        One Markdown file per placeholder value, e.g. VERIFY_COMMANDS.md
└── files/         Files copied over the scaffold at the same relative path
```

- **`profile.json`**
  - `id`, `name`, `description`: shown by `eck list` and recorded in `kit.json`.
  - `extends`: optional parent profile. Tokens and files from the parent apply first, and the child overrides them. Every profile should extend `generic`, directly or indirectly, so that all tokens have a value.
  - `extraContextFiles`: context files the profile adds to the "Always read" list in `AGENTS.md`. Each has a `path`, a `purpose` and an optional `after` (the path it should follow in the reading order). The file itself goes in `files/`.
- **`tokens/<TOKEN>.md`**: the value for `{{TOKEN}}` in scaffold templates. The file's contents are inserted with leading blank lines and trailing whitespace removed, so indentation on the first line is kept. If a token is alone on its line and its value is empty, the whole line is removed. `generic` defines the default for every profile token:

  | Token | Used in |
  | --- | --- |
  | `VERIFY_COMMANDS` | `AGENTS.md`: commands to run before a unit is done |
  | `APPROVAL_GATES` | `ai-workflow-rules.md`: extra actions that need human approval |
  | `PROTECTED_PATHS` | `ai-workflow-rules.md`: paths agents must not modify |
  | `SCHEMA_PROMOTION` | `modules/environments-delivery.md`: how schema and content move between environments |

  Built-in tokens are set by `eck init` and cannot be defined by a profile: `PROJECT_NAME`, `CLIENT_NAME`, `OWNER`, `TODAY`, `KIT_VERSION`, `PROFILE_NAME`, `REVIEW_DAYS` and `CONTEXT_READING_LIST`.

- **`files/`**: replaces or adds files. For example, `files/context/architecture.md` replaces the generic architecture template.

## Adding a profile

1. Create `profiles/<id>/profile.json` with `"extends": "generic"`.
2. Add token files for anything that differs from the generic defaults.
3. Add replacement or extra files under `files/`. Keep the header block (Owner, Last reviewed, Status) on every context file so the check can track reviews.
4. Run `node tools/eck.mjs init <temp-dir> --yes --profile <id>` and read the result.
5. Run `npm test`, then add the profile to the tables in this file and in the kit README, and record it in `CHANGELOG.md`.
