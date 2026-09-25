"""QR code utilities."""

import base64
import math
from pathlib import Path
from typing import Optional
import segno

# Dynamically locate bundled assets inside this package
ASSETS_DIR = Path(__file__).parent / "assets"
DEFAULT_MIKAELKIRKEN_LOGO = ASSETS_DIR / "mikaelkirken-rund.png"


def generate_qrcode(
    url: str,
    png_image: Optional[str] = None,
    color: str = "#000000",
    output_file: str = "qr-code.svg",
    style: str = "rounded",
    scale: int = 12,
    border: int = 4,
    corner_radius: float = 0.35,
    help: bool = False,
) -> Optional[str]:
    """Generate a styled SVG QR code with optional logo and custom color."""
    if url in ("--help", "-h") or help:
        print(generate_qrcode.__doc__)
        return None

    has_logo = png_image is not None
    logo_uri = ""
    logo_size = 0.0
    cutout_radius = 0.0

    qr = segno.make(url, error="h")
    matrix = [list(row) for row in qr.matrix_iter(scale=1, border=border)]
    dim = len(matrix)
    total_size = dim * scale
    center_x = total_size / 2.0
    center_y = total_size / 2.0

    if has_logo:
        logo_path = Path(png_image)
        if not logo_path.is_file():
            raise FileNotFoundError(f"Logo image file not found: {png_image}")

        with open(logo_path, "rb") as image_file:
            logo_b64 = base64.b64encode(image_file.read()).decode("ascii")
        logo_uri = f"data:image/png;base64,{logo_b64}"

        logo_size = total_size * 0.23
        cutout_radius = (logo_size / 2.0) + (scale * 0.4)

    def is_in_finder(r: int, c: int) -> bool:
        if border <= r < border + 7 and border <= c < border + 7:
            return True
        if border <= r < border + 7 and (dim - border - 7) <= c < (dim - border):
            return True
        if (dim - border - 7) <= r < (dim - border) and border <= c < border + 7:
            return True
        return False

    svg_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {total_size} {total_size}" '
        f'width="{total_size}" height="{total_size}">',
        f'  <rect width="100%" height="100%" fill="white" rx="{scale * 1.5:.2f}"/>',
    ]

    finder_coords = [
        (border, border),
        (border, dim - border - 7),
        (dim - border - 7, border),
    ]

    for fr, fc in finder_coords:
        fx = fc * scale
        fy = fr * scale
        s = scale
        inner_rx = 1.5 * s if style == "dots" else 0.9 * s

        svg_lines.append(
            f'  <rect x="{fx:.2f}" y="{fy:.2f}" width="{7 * s:.2f}" height="{7 * s:.2f}" '
            f'rx="{2.2 * s:.2f}" ry="{2.2 * s:.2f}" fill="{color}"/>'
        )
        svg_lines.append(
            f'  <rect x="{fx + s:.2f}" y="{fy + s:.2f}" width="{5 * s:.2f}" height="{5 * s:.2f}" '
            f'rx="{1.4 * s:.2f}" ry="{1.4 * s:.2f}" fill="white"/>'
        )
        svg_lines.append(
            f'  <rect x="{fx + 2 * s:.2f}" y="{fy + 2 * s:.2f}" width="{3 * s:.2f}" height="{3 * s:.2f}" '
            f'rx="{inner_rx:.2f}" ry="{inner_rx:.2f}" fill="{color}"/>'
        )

    for r in range(dim):
        for c in range(dim):
            if matrix[r][c] == 1 and not is_in_finder(r, c):
                mod_cx = c * scale + scale / 2.0
                mod_cy = r * scale + scale / 2.0

                if (
                    has_logo
                    and math.hypot(mod_cx - center_x, mod_cy - center_y) < cutout_radius
                ):
                    continue

                if style == "dots":
                    svg_lines.append(
                        f'  <circle cx="{mod_cx:.2f}" cy="{mod_cy:.2f}" '
                        f'r="{scale * 0.44:.2f}" fill="{color}"/>'
                    )
                else:
                    r_val = scale * corner_radius
                    svg_lines.append(
                        f'  <rect x="{c * scale:.2f}" y="{r * scale:.2f}" '
                        f'width="{scale:.2f}" height="{scale:.2f}" '
                        f'rx="{r_val:.2f}" ry="{r_val:.2f}" fill="{color}"/>'
                    )

    if has_logo:
        svg_lines.append(
            f'  <circle cx="{center_x:.2f}" cy="{center_y:.2f}" '
            f'r="{cutout_radius:.2f}" fill="white"/>'
        )
        logo_pos = (total_size - logo_size) / 2.0
        svg_lines.append(
            f'  <image href="{logo_uri}" xlink:href="{logo_uri}" '
            f'x="{logo_pos:.2f}" y="{logo_pos:.2f}" '
            f'width="{logo_size:.2f}" height="{logo_size:.2f}"/>'
        )

    svg_lines.append("</svg>")

    dest = Path(output_file)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as out:
        out.write("\n".join(svg_lines))

    return str(dest)


def generate_qrcode_mikaelkirken(
    url: str, output_file: str = "qrcode.svg"
) -> Optional[str]:
    """Generate a branded Mikaelkirken QR code using the bundled logo asset."""
    return generate_qrcode(
        url=url,
        png_image=str(DEFAULT_MIKAELKIRKEN_LOGO),
        color="#8D008C",
        output_file=output_file,
    )
