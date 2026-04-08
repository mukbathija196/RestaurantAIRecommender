# Design System Specification: Editorial Gastronomy

## 1. Overview & Creative North Star: "The Digital Maître D’"

The objective of this design system is to evolve the platform from a utility-based directory into a high-end editorial experience. Our Creative North Star is **"The Digital Maître D’"**—an interface that feels intelligent, anticipatory, and effortlessly sophisticated.

We are moving away from the "standard grid" of typical delivery apps. Instead, we embrace **Intentional Asymmetry** and **Tonal Depth**. By utilizing overlapping elements, oversized editorial typography, and high-quality food imagery that breaks container boundaries, we create a sense of culinary motion. The "AI-first" layer is not expressed through clunky bots, but through subtle glowing accents and conversational transitions that guide the user with professional intuition.

---

### 2. Colors & Surface Philosophy

This system rejects the rigidity of traditional lines. We define space through weight and light, not borders.

*   **Primary Palette:** We utilize `primary` (#b7122a) for high-impact brand moments and `primary_container` (#db313f) for functional interactions.
*   **The "No-Line" Rule:** 1px solid borders are strictly prohibited for sectioning. Boundaries must be defined solely through background shifts. For instance, a `surface_container_low` section should sit directly on a `surface` background to create a logical break without visual clutter.
*   **Surface Hierarchy & Nesting:** Treat the UI as a series of physical layers. Use the hierarchy of `surface_container` tokens (Lowest to Highest) to "lift" content. An inner card (`surface_container_lowest`) placed on a section background (`surface_container_low`) creates a soft, natural hierarchy that feels like stacked fine paper.
*   **The "Glass & Gradient" Rule:** For AI-driven or floating elements, use Glassmorphism. Apply a semi-transparent `surface` color with a `backdrop-filter: blur(20px)`. 
*   **Signature Textures:** Main CTAs must use a subtle linear gradient from `primary` to `primary_container` (135deg). This adds "soul" and depth, preventing the flat, "default" look of standard buttons.

---

### 3. Typography: Editorial Authority

We use a dual-font strategy to balance character with legibility.

*   **Display & Headlines (Lexend):** These are our "voice." Use `display-lg` and `headline-lg` to create focal points. Don't be afraid of tight tracking and intentional white space. The geometry of Lexend provides a modern, clean, and appetizing structure.
*   **Body & Labels (Plus Jakarta Sans):** Chosen for its high x-height and readability. `body-lg` is your workhorse for descriptions. 
*   **Editorial Scaling:** Use dramatic scale shifts. A `display-md` headline paired with a `label-md` category tag creates a high-end magazine feel that guides the eye better than uniform sizing.

---

### 4. Elevation & Depth: Tonal Layering

Traditional drop shadows are often too heavy. We use **Tonal Layering** to convey importance.

*   **The Layering Principle:** Depth is achieved by stacking `surface` tiers. 
    *   *Level 0:* `surface` (Base)
    *   *Level 1:* `surface_container_low` (Sectioning)
    *   *Level 2:* `surface_container_lowest` (Cards/Interaction)
*   **Ambient Shadows:** If a "floating" state is required (e.g., a cart summary), use an extra-diffused shadow: `box-shadow: 0 12px 32px rgba(25, 28, 30, 0.06)`. The shadow color must be a tinted version of `on_surface`, never pure black.
*   **The "Ghost Border" Fallback:** If a container lacks sufficient contrast, use a "Ghost Border": `outline_variant` at 15% opacity. High-contrast, 100% opaque borders are forbidden.
*   **AI Glow:** To signify AI-driven insights, apply a subtle outer glow using the `tertiary_fixed_dim` (#f0be6d) color at 30% opacity to mimic a soft, warm light source behind the element.

---

### 5. Components

#### Buttons
*   **Primary:** Gradient (`primary` to `primary_container`), `xl` (1.5rem) roundedness. No border. White text.
*   **Secondary:** `surface_container_high` background with `primary` text. No border.
*   **Tertiary:** Ghost style. No background, `primary` text, bold weight.

#### Cards & Lists
*   **The Card Rule:** No dividers. Separate items using `surface_container` shifts or 24px vertical white space.
*   **Imagery:** Food photos in cards should use a `lg` (1rem) corner radius. For featured "Editorial" cards, allow the image to bleed off one edge (asymmetric) to break the box.

#### Input Fields
*   **Conversational Style:** Text inputs should use `surface_container_highest` with a `md` radius. Focus states transition the background to `surface_container_lowest` and add a soft `surface_tint` glow.
*   **Labels:** Use `label-md` in `on_surface_variant`. Avoid floating labels; keep them static and elegant.

#### AI Accents (Bespoke)
*   **Insight Chips:** Small `surface_container_lowest` chips with a 2px `tertiary` left-border and `tertiary` text to highlight "AI-Recommended" dish attributes.

---

### 6. Do’s and Don'ts

#### Do
*   **Do** use white space as a structural element. If a screen feels crowded, increase the vertical gap rather than adding a line.
*   **Do** lean into high-quality food photography. The interface should feel like it's built *around* the food.
*   **Do** use asymmetrical layouts (e.g., a left-aligned headline with a right-aligned image slightly offset vertically).

#### Don't
*   **Don't** use 100% black (#000). Use `on_surface` (#191c1e) for text to maintain a premium, softer contrast.
*   **Don't** use "default" shadows. If you can see the shadow clearly, it’s too dark. It should feel like a suggestion of height.
*   **Don't** use standard "Select" dropdowns. Opt for conversational selection chips or full-screen overlays to maintain the premium feel.

---

### 7. Accessibility Note
While we prioritize high-end aesthetics, contrast ratios must never fall below WCAG AA standards. Always ensure `on_surface` and `on_primary` text maintains high visibility against their respective containers. Ghost borders should be used sparingly if tonal shifts are too subtle for low-vision users.