# Kellermann Web UI Kit

Pixel-faithful recreation of the Kellermann Réservations Django web app.
The real stack is Django + Bootstrap 5.3 + FullCalendar; this kit reproduces
the visual language in vanilla HTML/CSS/JS with no dependencies beyond
Bootstrap CDN (matching production).

## Screens included

1. **Bienvenue** — the entry splash with brand glyph and two-tier access.
2. **Calendrier** — month view with color-coded events per temple.
3. **Formulaire de tenue** — the main reservation request form (loge → date → temple → agapes).
4. **Tableau de bord admin** — KPI stats + attente banner + quick actions.

## How to view

Open `index.html`. A top tab strip lets you switch between screens.
Every screen is a direct port of the corresponding template in
`temple_project/templates/{auth,calendrier,reservations,administration}/`.

## Notes

- All copy is French and sourced from the real templates.
- Icons are emoji, inline in text (matches production).
- The navy navbar with gold links, gold-on-navy temple badges, and the
  navy card-header band are the three signature patterns to preserve.
- Focus rings use the gold ring token; all buttons round to 6px.
- The calendar grid is a static screenshot-style mock (FullCalendar is
  too heavy to recreate faithfully for a kit); event pills show the
  per-temple color palette from `colors_and_type.css`.
