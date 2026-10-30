---
name: enterprise-context-kit
description: Add the Context Kit (AGENTS.md, context files, enterprise modules, playbooks and the context check) to a new or existing repository, or check a repository's context files. Use when the user asks to add, install, set up or update the context kit, or to run the context check.
---

# Context Kit

This skill's folder is `skills/enterprise-context-kit/` inside the kit, so the kit folder (`<kit>` below) is `../..` from this skill's base directory. Its command-line tool is `<kit>/tools/eck.mjs`. Run it with Node.js 20 or later; it needs no other dependencies.

## Add the kit to a repository

1. Confirm the target folder with the user. It is usually the current working directory.
2. Ask the user for the project name, the client name, and the person or role who will own the context files. Do not guess them.
3. Ask which profile to use. Run `node <kit>/tools/eck.mjs list` to show the options. The default is `generic`, which suits any stack.
4. Preview the changes:

   ```bash
   node <kit>/tools/eck.mjs init <target> --yes --dry-run --profile <id> --name "<name>" --client "<client>" --owner "<owner>"
   ```

5. Show the user the preview. If any files are listed as `conflict`, explain that the existing files will be kept and the kit's versions written beside them as `.kit-new` copies. Do not use `--force` unless the user explicitly asks to overwrite files.
6. Once the user agrees, run the same command without `--dry-run`.
7. Report what was created. Then offer to fill in the context files by following `context/playbooks/setup-context.md` in the target repository, including one file per brand in `context/brands/`. The other workflows (plan, spec, implement, small changes, review, releases and go-live, decisions and refreshing the context) are listed in the Playbooks table in the target's `AGENTS.md`. Tell the user that `context/HOW-TO-USE.md` is the team's guide to working with the kit, and `context/SKILLS-AND-COMMANDS.md` is the quick reference to every skill and command, and suggest they share both with the project team.

## Check a repository

Run `node context/check-context.mjs` in the repository root. If the repository has no copy of the script, run `node <kit>/tools/eck.mjs check <target>` instead. Explain each error and offer to fix it. Warnings for files still in `Draft` are expected while the context is being filled in.

## Rules

- Never commit, push or open a pull request without the user's approval.
- Never put secrets, personal data or production data into a context file.
