# Kellermann Design System

Design system for **Kellermann Réservations** — the reservation management tool for *Temple Kellermann* (a French Masonic building complex in Paris that houses loges, cabinets de réflexion, meeting rooms and banquet halls).

The product is an internal Django web app used by three audiences:
- **Visiteurs / membres de loge** — browse the calendar, submit reservation requests
- **Administrateurs Kellermann** — validate requests, manage loges, seasons, rules, exports
- **Traiteur** (caterer) — dashboard for agapes (meals), block dates, notifications

Production URL (hosted on PythonAnywhere): `kellermanadmin.eu.pythonanywhere.com`

The UI is **Bootstrap 5** + custom CSS. All copy is in **French**. The visual identity is **navy + gold** (Masonic tones), with heavy use of emoji as iconography.

---

## Sources

- **Local codebase (read-only mount):** `kellermann_resa/` — Django 5, Python 3.13
  - `temple_project/templates/` — all HTML templates (base.html, calendrier/, reservations/, administration/, auth/, loges/, traiteur/)
  - `temple_project/apps/` — Django apps: `loges`, `reservations`, `calendrier`, `exports`, `administration`, `auth_custom`, `traiteur`
  - `temple_project/static/icons/` — PWA icons (192/512)
  - `CHANGELOG.md` — feature history
- **GitHub repo:** `auerfr/kellermann_resa` (private)
- **Primary CSS:** all design tokens + Bootstrap overrides live inline in `temple_project/templates/base.html` (static/css/ is empty)

Dependencies pulled from CDN by the real product:
- Bootstrap 5.3.3, jQuery 3.7.1, Select2 4.0.13 + bootstrap-5 theme
- FullCalendar 6.1.11 (calendar view)
- Chart.js (reporting page)

---

## Products represented

1. **Portail membres** — visiteur-facing pages: welcome, login (access code), calendar, request forms, loge portal (personal reservations + season validation)
2. **Administration Kellermann** — admin dashboard with KPIs, pending validations, loge directory, rules, imports/exports
3. **Espace Traiteur** — caterer dashboard: upcoming meals, blocks, notifications

---

## Content fundamentals

**Language:** French, formal tone, uses `vous` (never `tu`). Second-person friendly but professional — *"Remplissez ce formulaire pour demander un créneau"*, *"Vous recevrez une confirmation par email"*.

**Casing:** Sentence case for buttons, titles, labels. No ALL CAPS except micro-eyebrows (`TENUES 2026`, `ABRÉV.`, `OBÉDIENCE` on table headers, rendered through `letter-spacing` + `text-transform: uppercase`).

**Voice & vibe:** Institutional, slightly ceremonious — the product serves a Masonic organization so specialized vocabulary is present and untouched: *loge, obédience, tenue, vénérable, agapes, REAA, RER, RF, cabinet de réflexion, banquet d'ordre*. Never translate or soften these terms.

**Dates & times:** French locale. Days of week lowercased in lists (`lun. 12/09/2026`), time written as `19h00` or `19h` when minutes = 0 (custom `fmtH` / `fmtHM` helpers in the calendar view). Months fully spelled out in longer strings (`lundi 12 septembre 2026`).

**Microcopy examples:**
- *"Entrez le code annuel fourni par votre loge"* (login hint)
- *"Le code d'accès annuel est distribué en début de saison par l'administrateur. Si vous ne l'avez pas, contactez votre vénérable."* (help)
- *"Aucune demande en attente — tout est à jour !"* (success empty state)
- *"Action requise"* (uppercase tag on pending cards)
- *"Traiter →"* (CTA on pending rows)
- *"✓ Tout confirmer"* (bulk action)
- *"T∴F∴ {{nom_venerable}}"* — uses Masonic trigrams (three-dot triangles) for honorifics

**Emoji-as-iconography:** Emoji are used prolifically as inline icons, not decoration. Every nav item, every button, every KPI card has one. See ICONOGRAPHY below.

---

## Visual foundations

### Color
- **Primary brand:** navy `#0F2137` + gold `#C8A84B`. Navy is the backbone — navbars, CTAs, card headers, big numbers. Gold is an accent on navy surfaces only (text on navy cards, badge text, decorative borders, focus ring).
- **Never** pair gold on white — it has too little contrast. Gold always appears on navy.
- **Neutrals:** slate scale from `#F8FAFC` (page bg) through `#E2E8F0` (borders) to `#1E293B` (text) and `#94A3B8` (muted).
- **Temple identities (calendar events):** each temple has a signature color — Lafayette navy `#1a3a5c`, Égalité teal `#0d6e6e`, Fraternité brown-gold `#92400E`, Liberté violet `#5B21B6`. Each is paired with a ~10% light background tint for filled event pills.
- **Semantic:** soft pastel pairs for badges (bg `#DCFCE7` + fg `#166534` for success, etc.) and slightly saturated fills for alert banners.

### Typography
- Primary: **Open Sans** (Google Fonts) — weights 400 / 500 / 600 / 700. Load via `<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&display=swap" rel="stylesheet">`.
- Full stack: `'Open Sans', 'Segoe UI', Arial, system-ui, sans-serif` — falls back to Segoe UI on Windows (the production OS) and Arial elsewhere so the visual shift is minimal if Open Sans fails to load.
- Weights: 400 body, 500 medium, 600 semibold (most UI copy), 700 bold (titles, KPIs).
- Tight letter-spacing (`-.01em`) on headings, wide `.08em` on all-caps micro-labels.
- Font sizes are **Bootstrap-rem-based** (0.875rem / 0.9rem / etc.) — see `colors_and_type.css` for the full scale.

### Backgrounds, textures, imagery
- **No photography, no illustrations, no repeating patterns.** The product is pure UI.
- Primary background: flat `#F8FAFC`. Secondary: `#F1F5F9`.
- Full navy background only on auth pages (welcome, login) — creates a gated, ceremonious threshold before entering the app.
- **Gradient usage is limited to KPI cards** on the admin dashboard: 4 preset gradients (blue `#1E40AF→#3B82F6`, amber `#D97706→#F59E0B`, green `#059669→#34D399`, violet `#7C3AED→#A78BFA`) at 135°. Never use gradients for page backgrounds or cards elsewhere.
- Decorative emoji at `opacity: .7` float in the corner of KPI cards.

### Motion & states
- **Transitions:** short (.15s) on `background-color`, `border-color`, `box-shadow`. Card hover adds `transform: translateY(-3px)` (lift) with a deeper shadow.
- **No bounces, springs, or page-level animations.** All motion is micro-interaction.
- **Hover on primary (navy):** lightens to `#1a3a5c`. On gold text (nav links): `opacity: 0.8`.
- **Active/pressed on navy buttons:** darkens to `#0a1a2e`.
- **Focus state:** custom 3px gold ring `0 0 0 3px rgba(200,168,75,.28)`, no outline. Applied consistently on inputs, buttons, checkboxes.
- **Row hover in tables:** pale blue tint `#F0F9FF`.

### Borders & radii
- Borders are **light** — `#E2E8F0` default, `#F1F5F9` on subtle card edges.
- Radius scale: 4 / 6 / 10 / 14 / 20 px. Inputs and buttons use 6px, cards 12px, login/welcome cards 20px. Pills use 99px.
- Bootstrap `--bs-border-radius: 8px` is the generic fallback.

### Shadows
- 5-step elevation: xs (1px 3px .05) → sm (1px 4px .08) → md (4px 12px .10) → lg (8px 24px .13) → xl (20px 60px .40, reserved for auth card on navy bg).
- KPI cards use a mid-depth `0 4px 15px rgba(0,0,0,.15)` rising to `0 10px 28px rgba(0,0,0,.20)` on hover.
- Navbar has a dedicated 2px/8px shadow.

### Cards
- White `#fff`, 12px radius, 1px `#F1F5F9` border + `shadow-sm`. On hover: `translateY(-3px)` + `shadow-md`.
- Navy-header variant: `background: #0F2137`, gold uppercase 11px label inside, radius clipped top-only.
- Accent-left-border variant (pending alerts): 4px left border in `#F59E0B` (warning) or `#3B82F6` (info), soft-color background.

### Layout
- Bootstrap grid. Container-fluid on most pages with `py-3 py-md-4`.
- Forms center on `col-lg-7` or `col-lg-8` at desktop, full-width on mobile.
- Sticky detail panel (`right: 0` slide-in, 400px wide) for event details on the calendar.
- Mobile tables convert to stacked cards via `@media (max-width: 768px)` — each cell shows its `data-label` as a left-column eyebrow.
- Navbar fixed `padding: 0.6rem 1rem`, single row on desktop, collapses to burger on mobile.

### Transparency & blur
- Minimal. Overlay behind slide-in panel is `rgba(15,33,55,.4)` — tinted navy, no blur.
- Gold on navy hover uses `rgba(200,168,75,.15)`.

### Print behavior
- `@media print` hides nav/footer/btns; strips card shadows; forces 1px `#ccc` borders.

---

## Iconography

The product's icon system is **emoji, inline in text**. No SVG icon library is imported, no icon font, no bespoke icons. Some key mappings:

| Concept | Emoji |
|---|---|
| Kellermann brand | ⚒ (hammer and pick — also the PWA logo glyph) |
| Calendar / date | 📅 |
| Reservation form | 📝 / ➕ |
| Temple (masonic hall) | 🏛 |
| Salle de réunion | 🪑 |
| Cabinet de réflexion | 🚪 |
| Banquet d'ordre / agapes | 🍽 |
| Récurrence | 🔁 |
| Authentification | 🔑 |
| Admin gear | ⚙️ |
| Contact | 📬 |
| Journal / règles | 📋 |
| Export PDF | 📄 |
| Export Excel | 📂 / 📤 / 📥 |
| Reporting | 📊 |
| Reset / delete | 🗑 |
| Backup | 💾 |
| Success | ✅ / ✓ |
| Pending | ⏳ |
| Danger | 🔴 / ✕ |
| Bell / notif | 🔔 |
| Lock / bloquer | 🔒 |
| Calendar time-slots | 🌅 morning / ☀️ afternoon / 🌙 evening |

**Masonic trigrams** — the three-dot triangle `∴` is used after honorifics (`T∴F∴` for *Très Fraternel*) and in specialized Masonic strings. Preserve Unicode `U+2234` — never substitute.

**Logo glyph** — the PWA icon (`assets/icon-192.png`, `icon-512.png`) is a pair of **crossed hammers in gold on navy**, a traditional Masonic symbol. The text logo in the navbar uses the ⚒ emoji + "Kellermann" wordmark in gold.

---

## Missing / substituted assets

- **Font: Open Sans (Google Fonts)** — loaded via `<link href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;500;600;700&display=swap">`. Metrics very close to Segoe UI so visual identity is preserved while rendering identically on every OS. Production Django app may still be serving the OS stack; if so, add the same `<link>` to `base.html` so end-users see the same thing designers do.
- **No SVG icon set** — emoji only. If more semantic icons are needed (e.g. for print exports), flag and ask.
- **No brand imagery beyond the façade logo.**

---

## Index — files in this design system

| Path | What it is |
|---|---|
| `README.md` | This file |
| `colors_and_type.css` | All CSS custom properties (colors, radii, shadows, type scale) + semantic typography classes |
| `SKILL.md` | Skill manifest for downloadable/Claude Code use |
| `assets/icon-192.png`, `assets/icon-512.png` | PWA logo (crossed hammers) |
| `assets/manifest.json` | Original PWA manifest for reference |
| `preview/*.html` | Design-system preview cards (swatches, tokens, components) — registered in the Design System tab |
| `ui_kits/web/index.html` | UI kit: 4 core screens — bienvenue, calendrier, formulaire de tenue, tableau de bord admin |
| `ui_kits/web/README.md` | Notes on the UI kit's scope and file layout |

---

## How to iterate

See SKILL.md for agent instructions. For production changes, always match the existing French microcopy tone and preserve the navy + gold + emoji vocabulary.
