# Vinyl Listening App — MVP Design System

## Scope

This document translates the current MVP screen mockups into implementation guidelines for the Android Compose prototype.

Source mockups:

- `docs/product/app-screens-mockups/Home.tsx`
- `docs/product/app-screens-mockups/Capture.tsx`
- `docs/product/app-screens-mockups/Processing.tsx`
- `docs/product/app-screens-mockups/Match.tsx`
- `docs/product/app-screens-mockups/ManualSearch.tsx`
- `docs/product/app-screens-mockups/SessionLogging.tsx`
- `docs/product/app-screens-mockups/RecordDetail.tsx`

Analytics is intentionally out of scope for the current Android prototype.

## Color Tokens

Use a true dark UI with muted, record-collection style accents. The design is not a flat Material default dark theme; it relies on low-contrast surfaces, subtle borders, and soft accent glow lines.

| Token | Hex / RGBA | Use |
| --- | --- | --- |
| `AppBackground` | `#121212` | Main screen background |
| `SurfacePrimary` | `#1e1e1e` | Cards, inputs, result rows, primary dark panels |
| `SurfaceSecondary` | `#252525` | Bottom nav, secondary fills, inactive pills |
| `BorderDefault` | `#3a3a3a` | Card/input/button outlines |
| `TextPrimary` | `#e8e8e8` | Main readable text |
| `TextSecondary` | `#9a9a9a` | Subtitles, metadata, placeholders, inactive nav |
| `TextOnAccent` | `#ffffff` | Text/icons on green glass buttons |
| `TextOnSolidAccent` | `#121212` | Text/icons on solid green chips |
| `AccentGreen` | `#5eb17f` | Primary actions, success, selected state, active nav |
| `AccentOrange` | `#e07856` | Ratings, warning/progress, medium confidence, average values |
| `AccentPurple` | `#8b7fc8` | Low confidence, secondary mood/history accent |
| `ShadowBlack` | `rgba(0, 0, 0, 0.3)` | Soft elevation under glass buttons |
| `GreenTint20` | `rgba(94, 177, 127, 0.2)` | High-confidence chip fill |
| `OrangeTint20` | `rgba(224, 120, 86, 0.2)` | Medium-confidence chip fill |
| `PurpleTint20` | `rgba(139, 127, 200, 0.2)` | Low-confidence chip fill |
| `GreenBorder30` | `rgba(94, 177, 127, 0.3)` | Glass button border |

## Gradients

### Accent Hairline

Many cards use a 1 px top accent line:

```text
linear-gradient(90deg, transparent, AccentColor, transparent)
```

Use this as a thin decorative top border inside cards.

Opacity by context:

- `0.3` for subtle list cards and camera hint.
- `0.4` for stat cards, top records, record detail cards, and selected history accents.
- `0.5` for stronger active/confirmation cards such as match candidates and processing steps.

Accent color mapping:

- Green: `#5eb17f`
- Orange: `#e07856`
- Purple: `#8b7fc8`

### Primary Glass Button

Large primary buttons use a translucent green gradient with blur/shadow.

Full-width primary actions:

```text
linear-gradient(135deg, rgba(94, 177, 127, 0.85), rgba(94, 177, 127, 0.7))
backdrop blur: 12 px
shadow: 0 4 px 12 px rgba(0, 0, 0, 0.3)
border: 1 px solid rgba(94, 177, 127, 0.3)
```

Used by:

- Capture: `Take Photo`
- Manual Search: `Search`
- Match: `Confirm`
- Session Logging: `Save Session`

Floating primary actions are more transparent:

```text
linear-gradient(135deg, rgba(94, 177, 127, 0.75), rgba(94, 177, 127, 0.6))
backdrop blur: 12 px
shadow: 0 4 px 12 px rgba(0, 0, 0, 0.3)
border: 1 px solid rgba(94, 177, 127, 0.3)
```

Used by:

- Home: `Log Session`
- Record Detail: `Add Session`

In Compose, use a `Brush.linearGradient` and alpha-based colors. Android does not need exact CSS backdrop blur for MVP; approximate the glass look with translucent gradient, soft shadow, and the green border.

## Surfaces And Borders

Cards and fields:

- Fill: `SurfacePrimary`
- Border: `1 dp` `BorderDefault`
- Radius: usually `16 dp`
- Content padding: `16-24 dp`
- Optional top accent hairline for important cards.

Bottom bars:

- Fill: `SurfaceSecondary`
- Top border: `1 dp` `BorderDefault`
- Fixed to bottom.

Inputs:

- Fill: `SurfacePrimary`
- Border: `BorderDefault`
- Radius: `16 dp`
- Placeholder: `TextSecondary`
- Text: `TextPrimary`
- No bright focus treatment in static mockups; use green border only if focus state is needed.

## Shape Scale

Map the mockup Tailwind radii to Compose values:

| Mockup class | Compose radius | Use |
| --- | --- | --- |
| `rounded-xl` | `12 dp` | Small confirm buttons, compact controls |
| `rounded-2xl` | `16 dp` | Cards, fields, most buttons |
| `rounded-3xl` | `24 dp` | Floating glass CTAs, large camera preview |
| `rounded-full` | `50 percent` / pill | Chips, icon buttons, nav indicators |

## Typography

The mockups use a compact, high-contrast hierarchy:

| Role | Approx. Compose style | Color |
| --- | --- | --- |
| Screen title | `28-32 sp`, bold | `TextPrimary` |
| Section title | `22-24 sp`, bold | `TextPrimary` |
| Card title | `18-20 sp`, semibold | `TextPrimary` |
| Body / metadata | `14-16 sp`, medium | `TextSecondary` |
| Button label | `16-18 sp`, semibold | `TextOnAccent` |
| Chip label | `14-16 sp`, medium | Accent color or `TextOnSolidAccent` |

Avoid oversized marketing typography. This is a dense mobile utility UI.

## Spacing

Use these values as the Compose spacing scale:

| Token | Size | Use |
| --- | --- | --- |
| `SpaceXs` | `4 dp` | Tight icon/text gaps |
| `SpaceSm` | `8 dp` | Chip internals, nav item gaps |
| `SpaceMd` | `12 dp` | Button icon gaps, compact stack gaps |
| `SpaceLg` | `16 dp` | Card padding, list item gaps |
| `SpaceXl` | `24 dp` | Screen horizontal padding, section gaps |
| `Space2Xl` | `32 dp` | Large vertical screen separation |

Screen content generally uses `24 dp` horizontal padding and scroll content should reserve bottom padding for floating buttons and bottom bars.

## Component Guidelines

### Glass Primary Button

Use for main positive actions.

- Gradient: `PrimaryGlassButton` or `FloatingGlassButton`
- Text/icon: white
- Radius: `16 dp` for full-width, `24 dp` for floating
- Border: `GreenBorder30`
- Shadow: soft black, close to CSS `0 4 px 12 px`
- Height: around `56-64 dp`

### Secondary Button

Use for upload, manual search, cancel, view details.

- Fill: `SurfacePrimary`
- Border: `BorderDefault`
- Text: `TextSecondary` or `TextPrimary`
- Radius: `16 dp`
- Icon and label centered.

### Icon Button

Used for close, info, details, and navigation controls.

- Shape: circle
- Fill: `SurfaceSecondary`
- Border: `BorderDefault`
- Icon: `TextPrimary` for close/info, `TextSecondary` for inactive states.

### Status And Confidence Chips

Confidence:

- High: fill `GreenTint20`, text `AccentGreen`
- Medium: fill `OrangeTint20`, text `AccentOrange`
- Low: fill `PurpleTint20`, text `AccentPurple`

Side played chip:

- Solid green fill `AccentGreen`
- Text `TextOnSolidAccent`
- Pill shape.

Mood chips:

- Default: `SurfacePrimary`, `BorderDefault`, `TextSecondary`
- Selected: green tinted/outlined treatment with `AccentGreen`
- Custom mood: dashed border, `TextSecondary`, plus icon.

### Rating

Rating uses orange stars:

- Filled star: `AccentOrange`
- Empty star: `BorderDefault`
- Keep star size large enough for touch and readability, around `36-44 dp` on the logging screen.

### Progress Processing Cards

Processing status cards use the same card surface and accent hairline:

- Complete: green hairline, green icon circle.
- Active: orange hairline, orange icon circle.
- Pending: no hairline or neutral border.
- Active card may scale slightly; in Compose keep this subtle.

### Bottom Navigation

Home mockup includes a bottom nav shell:

- Bar fill: `SurfaceSecondary`
- Top border: `BorderDefault`
- Active item: `AccentGreen`
- Inactive items: `TextSecondary`
- Keep Analytics/Stats route as a placeholder until backend/analytics scope begins.

## Layout Notes

- Screens are dark full-screen mobile views.
- Use edge-to-edge dark system bars if possible.
- Scrollable screens need bottom padding so fixed/floating CTAs do not cover content.
- Home and Record Detail use floating primary CTAs at bottom-right above the bottom bar.
- Modal-like screens use a top close button and centered title.
- Image thumbnails are rounded and should use real/mock album imagery where available.

## Compose Implementation Notes

Create design primitives before building screens:

- `VinylColors`
- `VinylSpacing`
- `VinylShapes`
- `GlassPrimaryButton`
- `SecondaryButton`
- `AccentCard`
- `ConfidenceChip`
- `MoodChip`
- `RatingStars`
- `BottomNavBar`

Use these primitives consistently. Do not recreate color literals inside each screen once the tokens exist.
