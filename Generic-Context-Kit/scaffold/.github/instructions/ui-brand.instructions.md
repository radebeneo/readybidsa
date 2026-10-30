---
applyTo: "**/*.css,**/*.scss,**/*.less,**/*.html,**/*.cshtml,**/*.razor,**/*.tsx,**/*.jsx,**/*.vue,**/*.svelte"
---

# Interface and brand code

Follow `context/ui-context.md` for the shared design system, and the file in `context/brands/` for each brand the change affects. The most important reminders:

- Use design tokens for colours, fonts, sizes, spacing, radius, shadows and breakpoints. Never hard-code a hex code or pixel size where a token exists.
- Use semantic or component tokens, not primitive tokens, so the code works in every brand theme.
- Reuse existing components before creating new ones.
- Never recreate or alter a logo, and never invent claims, prices or legal text.
- Changing token values, brand themes, logos or approved copy needs human approval.
