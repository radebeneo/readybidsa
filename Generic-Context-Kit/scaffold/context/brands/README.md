# Brands

One file per brand that this project presents to users. A brand file records what makes the brand distinct: its personality, voice, words, colours, typography, logos, imagery and approved copy. Agents read it before any change to interface or copy for that brand.

The design system that every brand shares, such as components, layout, accessibility and the token structure, is in `context/ui-context.md`. Brand files cover only what differs between brands.

## Adding a brand

1. Copy `_brand-template.md` to `<brand-id>.md`, using a short lowercase name with hyphens, for example `example-brand.md`.
2. Fill it in from the client's brand guidelines and designs, then ask the brand owner to confirm it.
3. Add the brand to the Brands table in `context/ui-context.md`.

A single-brand project has one brand file. A site that serves several brands or markets, for example several sites in one CMS, has one file for each brand. Markets that share a brand but differ in language or legal copy are covered in that brand's file.

## Rules

- Never copy token values such as hex codes into a brand file. Name the theme and link to the token source in `context/ui-context.md`.
- Never put unreleased campaign details, personal data or confidential client material here unless `context/modules/security-compliance.md` allows it.
- Files whose names start with `_` and this README are not checked. Every other file here is checked like a context file, so it needs the Owner, Last reviewed and Status header.
