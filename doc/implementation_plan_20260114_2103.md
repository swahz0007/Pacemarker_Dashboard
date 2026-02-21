# Implementation Plan - Visual Redesign

This plan details the technical steps to implement the approved visual or "Medical Geek" aesthetic optimization for the Pacemaker Dashboard.

## Goal Description
Transform the current "Nuclear Option" (no borders, simple black/white) design into a modern, high-end medical interface using:
- A new "Medical Geek" color palette (Deep Blue, Tech Blue, Emerald, Rose).
- Micro-interactions (hover states, transitions).
- Depth effects (soft shadows, glassmorphism).
- Optimized data visualization.

## User Review Required
> [!IMPORTANT]
> This change involves significant modifications to `style.css` and will alter the visual appearance of the entire application.

## Proposed Changes

### Dashboard UI

#### [MODIFY] [style.css](file:///e:/Gemini%20CLI%20%E5%AE%9E%E6%88%98/Pacemarker_Dashboard/dashboard_ui/assets/css/style.css)
- **Refactor `:root` variables**:
    - Replace monochrome colors with:
        - `--bg-main`: `#F8FAFC` (Cool Gray)
        - `--bg-sidebar`: `#0F172A` (Deep Blue)
        - `--primary`: `#3B82F6` (Tech Blue)
        - `--success`: `#10B981`
        - `--danger`: `#F43F5E`
- **Update Layout & Typography**:
    - Increase `gap` in grids.
    - Set Sidebar text color to white/light gray.
- **Enhance Components**:
    - `.card`: Add `box-shadow`, `border-radius: 16px`, and hover effects (`transform`, `shadow`).
    - `.sidebar`: Apply dark theme styles.
    - `.tab-btn`: Update active states to use the new Primary color.
- **Add Animations**:
    - `fadeInUp` for cards.
    - Button click scales.

#### [MODIFY] [charts.js](file:///e:/Gemini%20CLI%20%E5%AE%9E%E6%88%98/Pacemarker_Dashboard/dashboard_ui/assets/js/charts.js)
- Update `chartConfig` to use the new CSS variable values (or matching hex codes).
- Implement **Gradient Fills** for the datasets (fading from opaque color to transparent).
- Ensure `tension: 0.4` is set for smooth curves.

## Verification Plan

### Manual Verification
1.  **Open the Dashboard**: Open `dashboard_ui/index.html` in the browser.
2.  **Visual Check**:
    - Verify the sidebar is dark blue (`#0F172A`).
    - Verify the main background is light cool gray (`#F8FAFC`).
    - distinct shadows.
3.  **Interaction Check**:
    - Hover over cards: Should float up slightly.
    - Click tabs: Should switch content smoothly.
4.  **Data Check**:
    - Ensure Chart.js graphs appear with the new colors and gradient fills.
