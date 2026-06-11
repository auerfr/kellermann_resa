# How to integrate this design system into the Django repo

This folder is the standalone Kellermann design system. To merge it into
the production codebase (`auerfr/kellermann_resa`) as `docs/design-system/`:

```bash
cd kellermann_resa             # your Django project root
mkdir -p docs/design-system
# Unzip this archive into docs/design-system/
cp -r ~/Downloads/kellermann-design-system/* docs/design-system/

git add docs/design-system/
git commit -m "Add design system: tokens, preview cards, web UI kit"
git push
```

## Loading the design tokens in the Django app

If you want the production app to use the same tokens (Open Sans + colors),
edit `temple_project/templates/base.html`:

1. Copy the fonts into Django's static folder:
   ```
   temple_project/static/fonts/OpenSans-VariableFont_wdth_wght.ttf
   temple_project/static/fonts/OpenSans-Italic-VariableFont_wdth_wght.ttf
   ```

2. Add inside the `<style>` block in `base.html`:
   ```css
   @font-face {
     font-family: 'Open Sans';
     font-weight: 300 800;
     font-stretch: 75% 125%;
     font-display: swap;
     src: url("{% static 'fonts/OpenSans-VariableFont_wdth_wght.ttf' %}") format('truetype');
   }
   body { font-family: 'Open Sans', 'Segoe UI', Arial, sans-serif; }
   ```

3. On PythonAnywhere after `git pull`:
   ```bash
   python manage.py collectstatic --noinput
   # then Reload via the Web tab
   ```

## What's inside

- `README.md` — design system overview (audience, voice, tokens, iconography)
- `SKILL.md` — agent instructions if you reuse this with an AI assistant
- `colors_and_type.css` — all CSS custom properties + base typography
- `fonts/` — Open Sans variable fonts (regular + italic)
- `assets/` — PWA icons + SVG logo glyph (façade classique)
- `preview/` — visual reference cards (colors, type, components)
- `ui_kits/web/index.html` — 4-screen interactive kit (bienvenue, calendrier, formulaire, admin)
