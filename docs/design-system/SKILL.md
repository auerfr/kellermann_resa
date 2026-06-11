---
name: kellermann-design
description: Use this skill to generate well-branded interfaces and assets for Kellermann Réservations (Temple Kellermann reservation management tool), either for production or throwaway prototypes/mocks/etc. Contains essential design guidelines, colors, type, fonts, assets, and UI kit components for prototyping.
user-invocable: true
---

Read the README.md file within this skill, and explore the other available files.
If creating visual artifacts (slides, mocks, throwaway prototypes, etc), copy assets out and create static HTML files for the user to view. If working on production code, you can copy assets and read the rules here to become an expert in designing with this brand.
If the user invokes this skill without any other guidance, ask them what they want to build or design, ask some questions, and act as an expert designer who outputs HTML artifacts _or_ production code, depending on the need.

Key rules:
- Product is in French. Keep all copy French, formal `vous`, preserve Masonic vocabulary (loge, obédience, tenue, vénérable, agapes, REAA, cabinet de réflexion, banquet d'ordre).
- Navy `#0F2137` + gold `#C8A84B` are the brand. Gold only on navy backgrounds, never on white.
- Font stack: `'Open Sans', 'Segoe UI', Arial, sans-serif`. Open Sans is loaded from Google Fonts — include `<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">` in the `<head>`.
- Icons = emoji, inline in text. See ICONOGRAPHY in README.
- Stack is Bootstrap 5.3 + custom CSS variables. Load `colors_and_type.css` for tokens.
- PWA logo is the crossed-hammers glyph in `assets/`.
