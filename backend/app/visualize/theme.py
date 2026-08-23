"""Color palettes handed to the visualize agent's prompt so generated
charts match the frontend's active theme. Mirrors frontend/app/globals.css
— kept in sync manually, same as any other cross-language constant in
this codebase (there's no way to share CSS custom properties with a
Python prompt template directly)."""

__all__ = ["get_palette"]

_PALETTES = {
    "light": {
        "text_color": "#18181b",
        "dim_text_color": "#52525b",
        "grid_color": "#d4d4d9",
        "accent_color": "#0d9488",
        "series_palette": ["#0d9488", "#c53d42", "#a3790a", "#6d54c9", "#2f6fb0", "#b8497a"],
    },
    "dark": {
        "text_color": "#e4e4e7",
        "dim_text_color": "#8b8b93",
        "grid_color": "#26262b",
        "accent_color": "#35c9be",
        "series_palette": ["#35c9be", "#e5484d", "#e5b93f", "#8b7fd6", "#4f9de0", "#e07fb0"],
    },
}


def get_palette(theme: str) -> dict:
    """Color palette for `theme` ("light" or "dark"); unknown values fall
    back to dark."""
    return _PALETTES.get(theme, _PALETTES["dark"])
