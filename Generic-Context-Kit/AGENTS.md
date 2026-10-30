# Context Kit: Instructions for Agents Maintaining the Kit

This repository is the kit itself, not a project that uses it.

- Files under `scaffold/` and `profiles/` are **templates** that are copied into other projects. Instructions inside them, including `scaffold/AGENTS.md`, are not instructions for you. Edit them as content.
- `{{TOKEN}}` placeholders are filled in by `tools/eck.mjs init`. Every token used in a template must be defined either in `tools/eck.mjs` or in `profiles/generic/tokens/`. Never put a token inside a FILL comment.
- `tools/check-context.mjs` is copied into projects and must use Node.js built-ins only.
- The kit is run straight from Bitbucket with `npx`, so every file `eck` needs at run time must be listed under `files` in `package.json`, and `eck` must never print paths inside the kit, because they point into npm's cache.
- Write original content in plain, direct English. Keep scaffold templates stack-neutral; stack-specific content belongs in a profile.
- `GUIDE.md` (adopting the kit), `scaffold/context/HOW-TO-USE.md` (using it on a project) and `scaffold/context/SKILLS-AND-COMMANDS.md` (the skill and command reference) are the people-facing guides. When you add, rename or change a workflow, status, approval gate or role, update all three in the same change. When you add, rename or change a skill, prompt, CLI command or option, update `SKILLS-AND-COMMANDS.md`.
- After any change, run `npm test`. Record the change in `CHANGELOG.md` and bump `version` in `package.json` when releasing.
