from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).parent
MARK_PATH = ROOT / "aether-mark.png"
FONT_PATH = Path("C:/Windows/Fonts/bahnschrift.ttf")

NAVY = "#020D22"
INK = "#071426"
BLUE = "#168AF5"
WHITE = "#FFFFFF"
SOFT_WHITE = "#F5F8FC"


def cropped_mark() -> Image.Image:
    mark = Image.open(MARK_PATH).convert("RGBA")
    alpha = mark.getchannel("A")
    bounds = alpha.getbbox()
    if bounds is None:
        raise ValueError("The master mark is empty")
    return mark.crop(bounds)


def resized(image: Image.Image, max_width: int, max_height: int) -> Image.Image:
    result = image.copy()
    result.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
    return result


def recolor(image: Image.Image, color: str) -> Image.Image:
    solid = Image.new("RGBA", image.size, color)
    solid.putalpha(image.getchannel("A"))
    return solid


def paste_center(
    canvas: Image.Image,
    image: Image.Image,
    center_x: int,
    center_y: int,
) -> None:
    canvas.alpha_composite(
        image,
        (center_x - image.width // 2, center_y - image.height // 2),
    )


def draw_spaced_text(
    draw: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    color: str,
    spacing: int,
) -> tuple[int, int]:
    x, y = position
    for character in text:
        draw.text((x, y), character, font=font, fill=color)
        character_box = draw.textbbox((x, y), character, font=font)
        x = character_box[2] + spacing
    return x, y


def wordmark_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    spacing: int,
) -> int:
    widths = [
        draw.textlength(character, font=font)
        for character in text
    ]
    return round(sum(widths) + spacing * (len(text) - 1))


def create_monochrome(mark: Image.Image) -> None:
    recolor(mark, WHITE).save(ROOT / "aether-mark-white.png")
    recolor(mark, INK).save(ROOT / "aether-mark-ink.png")


def create_app_icon(
    mark: Image.Image,
    filename: str,
    background: str,
    light_surface: bool,
) -> None:
    canvas = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (48, 48, 976, 976),
        radius=220,
        fill=background,
    )
    icon_mark = resized(mark, 650, 650)
    if light_surface:
        icon_mark = recolor(icon_mark, BLUE)
    paste_center(canvas, icon_mark, 512, 512)
    canvas.save(ROOT / filename)


def create_horizontal(
    mark: Image.Image,
    filename: str,
    text_color: str,
    tagline_color: str,
    background: str | None = None,
) -> None:
    canvas = Image.new(
        "RGBA",
        (2000, 600),
        background if background else (0, 0, 0, 0),
    )
    icon_mark = resized(mark, 430, 430)
    paste_center(canvas, icon_mark, 270, 300)

    draw = ImageDraw.Draw(canvas)
    name_font = ImageFont.truetype(str(FONT_PATH), 142)
    tagline_font = ImageFont.truetype(str(FONT_PATH), 38)
    name = "AETHER"
    name_spacing = 35
    name_x = 580
    name_y = 140
    draw_spaced_text(
        draw,
        (name_x, name_y),
        name,
        name_font,
        text_color,
        name_spacing,
    )

    tagline = "WISP MANAGEMENT SOFTWARE"
    tagline_spacing = 13
    tagline_width = wordmark_width(
        draw,
        tagline,
        tagline_font,
        tagline_spacing,
    )
    name_width = wordmark_width(draw, name, name_font, name_spacing)
    tagline_x = name_x + max(0, (name_width - tagline_width) // 2)
    draw_spaced_text(
        draw,
        (tagline_x, 342),
        tagline,
        tagline_font,
        tagline_color,
        tagline_spacing,
    )
    canvas.save(ROOT / filename)


def create_square_lockup(mark: Image.Image) -> None:
    canvas = Image.new("RGBA", (1600, 1600), NAVY)
    logo = resized(mark, 760, 760)
    paste_center(canvas, logo, 800, 550)
    draw = ImageDraw.Draw(canvas)
    name_font = ImageFont.truetype(str(FONT_PATH), 150)
    tagline_font = ImageFont.truetype(str(FONT_PATH), 40)

    name = "AETHER"
    name_spacing = 42
    name_width = wordmark_width(draw, name, name_font, name_spacing)
    draw_spaced_text(
        draw,
        ((1600 - name_width) // 2, 1010),
        name,
        name_font,
        WHITE,
        name_spacing,
    )
    tagline = "WISP MANAGEMENT SOFTWARE"
    tagline_spacing = 13
    tagline_width = wordmark_width(
        draw,
        tagline,
        tagline_font,
        tagline_spacing,
    )
    draw_spaced_text(
        draw,
        ((1600 - tagline_width) // 2, 1240),
        tagline,
        tagline_font,
        BLUE,
        tagline_spacing,
    )
    canvas.save(ROOT / "aether-lockup-dark.png")


def create_preview() -> None:
    canvas = Image.new("RGB", (1800, 1500), "#CBD5E1")
    draw = ImageDraw.Draw(canvas)
    label_font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 28)
    panels = (
        ("aether-app-icon-dark.png", (80, 70, 500, 500), NAVY),
        ("aether-app-icon-light.png", (660, 70, 500, 500), SOFT_WHITE),
        ("aether-horizontal-on-dark.png", (80, 650, 780, 280), NAVY),
        ("aether-horizontal-on-light.png", (940, 650, 780, 280), SOFT_WHITE),
        ("aether-mark-white.png", (260, 1050, 300, 300), NAVY),
        ("aether-mark-ink.png", (1240, 1050, 300, 300), SOFT_WHITE),
    )
    for filename, (x, y, width, height), background in panels:
        image = Image.open(ROOT / filename).convert("RGBA")
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        panel = Image.new("RGBA", (width, height), background)
        panel.alpha_composite(
            image,
            ((width - image.width) // 2, (height - image.height) // 2),
        )
        canvas.paste(panel.convert("RGB"), (x, y))
        draw.text(
            (x, y + height + 10),
            filename,
            font=label_font,
            fill=INK,
        )
    canvas.save(ROOT / "aether-variants-preview.png")


def main() -> None:
    mark = cropped_mark()
    create_monochrome(mark)
    create_app_icon(mark, "aether-app-icon-dark.png", NAVY, False)
    create_app_icon(mark, "aether-app-icon-light.png", SOFT_WHITE, True)
    create_horizontal(
        mark,
        "aether-horizontal-on-dark.png",
        WHITE,
        BLUE,
        NAVY,
    )
    create_horizontal(
        mark,
        "aether-horizontal-on-light.png",
        INK,
        BLUE,
        SOFT_WHITE,
    )
    create_horizontal(
        mark,
        "aether-horizontal-transparent-dark.png",
        INK,
        BLUE,
    )
    create_horizontal(
        mark,
        "aether-horizontal-transparent-light.png",
        WHITE,
        "#52B6FF",
    )
    create_square_lockup(mark)
    create_preview()


if __name__ == "__main__":
    main()
