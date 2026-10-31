"""WCAG contrast of the colour tokens in style.css (R5.1)."""

import re

from neurisko.web.export import static_dir

TEXT_TOKENS = ("fg", "dim", "amber", "red", "focus")
BACKGROUNDS = ("bg", "panel")


def _tokens() -> dict[str, str]:
    css = (static_dir() / "style.css").read_text()
    root = re.search(r":root\s*{(.*?)}", css, re.S).group(1)
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", root))


def _luminance(hex_colour: str) -> float:
    def channel(c: int) -> float:
        s = c / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_text_colours_meet_wcag_aa():
    t = _tokens()
    for fg in TEXT_TOKENS:
        for bg in BACKGROUNDS:
            ratio = contrast(t[fg], t[bg])
            assert ratio >= 4.5, f"--{fg} on --{bg}: {ratio:.2f}"


def test_main_text_meets_aaa():
    t = _tokens()
    assert contrast(t["fg"], t["bg"]) >= 7
    assert contrast(t["dim"], t["bg"]) >= 7


def test_contrast_formula():
    assert round(contrast("#000000", "#ffffff"), 1) == 21.0
    assert contrast("#777777", "#777777") == 1.0
