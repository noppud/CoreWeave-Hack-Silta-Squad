#!/usr/bin/env python3
"""Generate synthetic dimensioned engineering drawing for fixture-block-01.

This script creates a 2-view mechanical drawing (top + front section) from
silta.fixtures.DEMO_SPEC. The drawing is synthetic and can never drift from
the spec because it is generated directly from it.

Usage:
    uv run python scripts/make_demo_drawing.py
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle

from silta.fixtures import DEMO_SPEC


def draw_dimension_line(
    ax,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    text: str,
    offset: float = 5.0,
    text_offset: float = 1.5,
):
    """Draw dimension line with extension lines and arrows."""
    # Calculate perpendicular offset direction
    dx = x2 - x1
    dy = y2 - y1
    length = math.sqrt(dx**2 + dy**2)
    if length == 0:
        return

    # Perpendicular unit vector
    px = -dy / length
    py = dx / length

    # Offset points for dimension line
    ox1 = x1 + px * offset
    oy1 = y1 + py * offset
    ox2 = x2 + px * offset
    oy2 = y2 + py * offset

    # Draw extension lines
    ax.plot([x1, ox1], [y1, oy1], "k-", linewidth=0.5, zorder=2)
    ax.plot([x2, ox2], [y2, oy2], "k-", linewidth=0.5, zorder=2)

    # Draw dimension line
    ax.annotate(
        "",
        xy=(ox2, oy2),
        xytext=(ox1, oy1),
        arrowprops=dict(arrowstyle="<->", color="black", lw=0.8, shrinkA=0, shrinkB=0),
        zorder=3,
    )

    # Add text
    mid_x = (ox1 + ox2) / 2 + px * text_offset
    mid_y = (oy1 + oy2) / 2 + py * text_offset
    ax.text(mid_x, mid_y, text, ha="center", va="center", fontsize=7, zorder=4)


def draw_dimension_label(ax, x: float, y: float, text: str, offset_x=0, offset_y=0):
    """Draw a dimension reference label (e.g., A1, B1)."""
    ax.text(
        x + offset_x,
        y + offset_y,
        text,
        ha="center",
        va="center",
        fontsize=8,
        weight="bold",
        bbox=dict(boxstyle="circle", facecolor="white", edgecolor="black", pad=0.3),
        zorder=5,
    )


def create_drawing(dimensioned: bool = True) -> plt.Figure:
    """Create the engineering drawing.

    Args:
        dimensioned: If True, include dimension lines and labels.
    """
    # Create figure with white background
    fig = plt.figure(figsize=(16, 10), facecolor="white")

    # Create two subplots: top view and front section
    ax_top = fig.add_subplot(1, 2, 1)
    ax_front = fig.add_subplot(1, 2, 2)

    # ===== TOP VIEW =====
    stock_x = DEMO_SPEC.stock_x_mm
    stock_y = DEMO_SPEC.stock_y_mm

    # Draw stock outline
    stock_rect = Rectangle((0, 0), stock_x, stock_y, fill=False, edgecolor="black", lw=2)
    ax_top.add_patch(stock_rect)

    # Draw pocket (rounded rectangle)
    pocket = DEMO_SPEC.features[0]
    pocket_x = pocket.x_min_mm
    pocket_y = pocket.y_min_mm
    pocket_w = pocket.x_max_mm - pocket.x_min_mm
    pocket_h = pocket.y_max_mm - pocket.y_min_mm
    pocket_r = pocket.corner_radius_mm

    pocket_rect = FancyBboxPatch(
        (pocket_x, pocket_y),
        pocket_w,
        pocket_h,
        boxstyle=f"round,pad=0,rounding_size={pocket_r}",
        fill=False,
        edgecolor="black",
        lw=1.5,
        linestyle="--",
    )
    ax_top.add_patch(pocket_rect)

    # Draw holes
    holes = DEMO_SPEC.features[1:5]
    for hole in holes:
        circle = Circle(
            (hole.center_x_mm, hole.center_y_mm),
            hole.diameter_mm / 2,
            fill=False,
            edgecolor="black",
            lw=1.5,
            linestyle=":",
        )
        ax_top.add_patch(circle)
        # Center mark
        cx, cy = hole.center_x_mm, hole.center_y_mm
        ax_top.plot([cx - 2, cx + 2], [cy, cy], "k-", lw=0.8)
        ax_top.plot([cx, cx], [cy - 2, cy + 2], "k-", lw=0.8)

    if dimensioned:
        # Stock dimensions
        draw_dimension_line(ax_top, 0, 0, stock_x, 0, f"{stock_x:.0f}", offset=-8)
        draw_dimension_line(ax_top, 0, 0, 0, stock_y, f"{stock_y:.0f}", offset=-8)

        # Pocket dimensions
        draw_dimension_line(
            ax_top, pocket_x, pocket_y, pocket_x + pocket_w, pocket_y, f"{pocket_w:.0f}", offset=8
        )
        draw_dimension_line(
            ax_top, pocket_x, pocket_y, pocket_x, pocket_y + pocket_h, f"{pocket_h:.0f}", offset=8
        )

        # Pocket labels (A1, A2, A3)
        draw_dimension_label(ax_top, pocket_x + pocket_w / 2, pocket_y + pocket_h + 12, "A1")
        draw_dimension_label(ax_top, pocket_x - 12, pocket_y + pocket_h / 2, "A2")
        draw_dimension_label(
            ax_top, pocket_x + pocket_w - pocket_r, pocket_y + pocket_r, "A3", offset_x=3
        )

        # Hole labels (B1, B2, B3, B4)
        hole_labels = ["B1", "B2", "B3", "B4"]
        offsets = [(-8, -8), (8, -8), (-8, 8), (8, 8)]
        for hole, label, (ox, oy) in zip(holes, hole_labels, offsets, strict=True):
            draw_dimension_label(ax_top, hole.center_x_mm, hole.center_y_mm, label, ox, oy)

    ax_top.set_xlim(-15, stock_x + 15)
    ax_top.set_ylim(-15, stock_y + 15)
    ax_top.set_aspect("equal")
    ax_top.axis("off")
    ax_top.set_title("TOP VIEW", fontsize=12, weight="bold", pad=10)

    # ===== FRONT SECTION VIEW =====
    stock_z = DEMO_SPEC.stock_z_mm
    pocket_depth = pocket.depth_mm
    hole_depth = holes[0].depth_mm

    # Draw stock outline (front view: width x height)
    front_rect = Rectangle((0, 0), stock_x, stock_z, fill=False, edgecolor="black", lw=2)
    ax_front.add_patch(front_rect)

    # Draw pocket depth (dashed line at top - depth)
    pocket_bottom = stock_z - pocket_depth
    ax_front.plot([pocket_x, pocket_x + pocket_w], [pocket_bottom, pocket_bottom], "k--", lw=1.5)

    # Draw hole depths (smaller dashed lines)
    hole_bottom = stock_z - hole_depth
    for hole in holes:
        cx = hole.center_x_mm
        r = hole.diameter_mm / 2
        ax_front.plot([cx - r, cx + r], [hole_bottom, hole_bottom], "k:", lw=1.5)

    if dimensioned:
        # Stock height dimension
        draw_dimension_line(ax_front, stock_x, 0, stock_x, stock_z, f"{stock_z:.0f}", offset=8)

        # Pocket depth dimension
        draw_dimension_line(
            ax_front,
            pocket_x + pocket_w,
            stock_z,
            pocket_x + pocket_w,
            pocket_bottom,
            f"{pocket_depth:.0f}",
            offset=15,
        )

        # Hole depth dimension
        draw_dimension_line(
            ax_front,
            holes[0].center_x_mm,
            stock_z,
            holes[0].center_x_mm,
            hole_bottom,
            f"{hole_depth:.0f}",
            offset=-10,
        )

        # Drill tip convention note
        ax_front.text(
            stock_x / 2,
            stock_z / 2 - 5,
            "HOLE DEPTH IS FULL-DIAMETER\nCYLINDRICAL DEPTH;\n118° POINT REACHES 1.803 DEEPER",
            ha="center",
            va="center",
            fontsize=7,
            bbox=dict(boxstyle="round", facecolor="lightyellow", edgecolor="black", pad=5),
        )

    ax_front.set_xlim(-15, stock_x + 25)
    ax_front.set_ylim(-5, stock_z + 5)
    ax_front.set_aspect("equal")
    ax_front.axis("off")
    ax_front.set_title("FRONT SECTION", fontsize=12, weight="bold", pad=10)

    # ===== TITLE BLOCK =====
    if dimensioned:
        title_text = (
            "FIXTURE BLOCK 01\n"
            f"Material: {DEMO_SPEC.material}\n"
            "ALL DIMENSIONS IN MILLIMETRES\n"
            "SYNTHETIC DEMONSTRATION DRAWING — NOT FOR MANUFACTURE\n"
            f"Scale: 1:1    Revision: {DEMO_SPEC.revision}\n"
            "ORIGIN AT LOWER-LEFT OF STOCK, TOP FACE Z=0"
        )
        fig.text(
            0.5,
            0.05,
            title_text,
            ha="center",
            va="center",
            fontsize=9,
            bbox=dict(boxstyle="round", facecolor="lightgray", edgecolor="black", pad=10),
        )

    plt.tight_layout(rect=[0, 0.12, 1, 1])
    return fig


def main():
    """Generate both dimensioned and undimensioned drawings."""
    output_dir = Path(__file__).parent.parent / "fixtures" / "demo"
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate dimensioned drawing
    print("Generating dimensioned drawing...")
    fig_dimensioned = create_drawing(dimensioned=True)
    output_path_dimensioned = output_dir / "fixture-block-01.png"
    fig_dimensioned.savefig(
        output_path_dimensioned, dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.close(fig_dimensioned)
    print(f"  → {output_path_dimensioned}")

    # Generate undimensioned drawing
    print("Generating undimensioned drawing...")
    fig_undimensioned = create_drawing(dimensioned=False)
    output_path_undimensioned = output_dir / "fixture-block-01-undimensioned.png"
    fig_undimensioned.savefig(
        output_path_undimensioned, dpi=150, bbox_inches="tight", facecolor="white"
    )
    plt.close(fig_undimensioned)
    print(f"  → {output_path_undimensioned}")

    print("Done.")


if __name__ == "__main__":
    main()
