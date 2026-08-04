"""Generate a multi-resolution app icon using Pillow."""

from PIL import Image, ImageDraw


def generate_icon(output_path: str) -> None:
    """Draw a simple icon (dark-blue rounded-rect + white bar chart) and save as PNG."""
    sizes = [16, 32, 48, 64, 128, 256]
    images: list[Image.Image] = []

    BG_COLOR = (43, 87, 154, 255)  # dark teal-blue
    FG_COLOR = (255, 255, 255, 255)

    for size in sizes:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        margin = max(1, size // 16)
        radius = max(1, size // 6)

        # background rounded rectangle
        draw.rounded_rectangle(
            [margin, margin, size - margin - 1, size - margin - 1],
            radius=radius,
            fill=BG_COLOR,
        )

        # draw three vertical bars — a simple "stats" symbol
        bar_count = 3
        bar_w = max(1, size // 8)
        total_bars_w = bar_count * bar_w + (bar_count - 1) * max(1, size // 12)
        start_x = (size - total_bars_w) // 2
        base_y = int(size * 0.78)
        heights = [int(size * 0.28), int(size * 0.46), int(size * 0.36)]

        for i, h in enumerate(heights):
            x = start_x + i * (bar_w + max(1, size // 12))
            draw.rectangle([x, base_y - h, x + bar_w - 1, base_y], fill=FG_COLOR)

        images.append(img)

    # Save as PNG (first image at largest size)
    images[-1].save(output_path, format="PNG")
