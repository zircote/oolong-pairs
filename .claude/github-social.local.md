---
# Image generation provider (default: svg)
# Options: svg, dalle-3, gemini, manual
provider: svg

# SVG-specific settings (only used when provider: svg)
svg_style: illustrated

# Dark mode support (default: false)
# false = light mode only, true = dark mode only, both = generate both variants
dark_mode: false

# Output settings
output_path: .github/social-preview.svg
dimensions: 1280x640
include_text: true
colors: auto

# README infographic settings
infographic_output: .github/readme-infographic.svg
infographic_style: hybrid

# Upload to repository (requires gh CLI or GITHUB_TOKEN)
upload_to_repo: true
---

# GitHub Social Plugin Configuration

This configuration was created by `/github-social:setup`.

## Provider: SVG

Claude generates clean, minimal SVG graphics directly. No API key required.
- **Pros**: Free, instant, editable, small file size (10-50KB)
- **Best for**: Professional, predictable results

## Style: Illustrated

Hand-drawn aesthetic using organic SVG paths with warm colors. Creates friendly, approachable social previews.

## Commands

- `/social-preview` - Generate social preview image
- `/readme-enhance` - Add marketing badges and infographic to README
- `/github-social:all` - Run all skills in sequence

## Override Settings

Override any setting via command flags:
```bash
/social-preview --provider=dalle-3 --dark-mode
/readme-enhance --svg-style=geometric
```

## Modify Configuration

Edit this file or run `/github-social:setup` again to change settings.
