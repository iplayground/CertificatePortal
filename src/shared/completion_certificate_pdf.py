from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Final

import pikepdf
import qrcode
from PIL import Image
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


PDF_TEMPLATE_DIR: Final[Path] = Path(__file__).resolve().parent / "pdf_templates"
DEFAULT_COMPLETION_CERTIFICATE_TEMPLATE: Final[Path] = (
    PDF_TEMPLATE_DIR / "completion_certificate_template_20260503.pdf"
)

PDF_CJK_FONT_NAME: Final[str] = "STSong-Light"
PDF_CJK_BOLD_FONT_NAME: Final[str] = "IPG-HeitiTC-Medium"
PDF_CJK_BOLD_FALLBACK_FONT_NAME: Final[str] = "HYGothic-Medium"
PDF_CJK_BOLD_FONT_PATH: Final[Path] = Path("/System/Library/Fonts/STHeiti Medium.ttc")
PDF_LATIN_FONT_NAME: Final[str] = "Helvetica"
PDF_LATIN_BOLD_FONT_NAME: Final[str] = "Helvetica-Bold"
PDF_TEXT_COLOR: Final[tuple[float, float, float]] = (0.13, 0.10, 0.09)
PDF_ACCENT_TEXT_COLOR: Final[tuple[float, float, float]] = (
    0x38 / 255,
    0x3D / 255,
    0x89 / 255,
)
PDF_WHITE_COLOR: Final[tuple[float, float, float]] = (1, 1, 1)

COMPLETION_CERTIFICATE_COPY: Final[dict[str, dict[str, str]]] = {
    "zh-TW": {
        "title": "完訓證明",
        "number_label": "證明編號",
        "organization_label": "任職單位",
        "statement_prefix": "茲證明已參與並完成「",
        "statement_suffix": "」，特發此證明。",
        "event_period_label": "活動期間",
        "completion_hours_label": "完訓時數",
        "completion_hours_unit": "小時",
        "font_name": PDF_CJK_FONT_NAME,
        "latin_font_name": PDF_LATIN_FONT_NAME,
        "title_font_name": PDF_CJK_BOLD_FONT_NAME,
        "title_latin_font_name": PDF_LATIN_BOLD_FONT_NAME,
        "title_font_size": "40",
    },
    "en-US": {
        "title": "Certificate of Completion",
        "number_label": "Certificate No.",
        "organization_label": "Organization",
        "statement_prefix": 'This certifies completion of "',
        "statement_suffix": '".',
        "event_period_label": "Event Period",
        "completion_hours_label": "Duration",
        "completion_hours_unit": "hours",
        "font_name": PDF_LATIN_FONT_NAME,
        "latin_font_name": PDF_LATIN_FONT_NAME,
        "title_font_name": PDF_LATIN_BOLD_FONT_NAME,
        "title_latin_font_name": PDF_LATIN_BOLD_FONT_NAME,
        "title_font_size": "38",
    },
}

FIELD_POSITIONS: Final[dict[str, tuple[float, float]]] = {
    "certificate_title": (47.8, 520),
    "certificate_number": (52.0, 493),
    "recipient_name": (420, 312),
    "organization": (420, 275),
    "completion_statement": (420, 235),
    "event_period": (420, 208),
    "completion_hours": (420, 184),
    "qr_code": (28, 23),
    "seal": (621, 82),
}

FIELD_SIZES: Final[dict[str, float]] = {
    "qr_code": 58,
    "seal": 150,
}


@dataclass(frozen=True)
class CompletionCertificatePdfData:
    certificate_number: str
    recipient_name: str
    organization: str
    event_name: str
    event_period_text: str
    completion_hours: int
    issued_date_text: str
    verification_url: str
    locale: str = "zh-TW"
    seal_image_path: Path | None = None


def render_completion_certificate_pdf(
    data: CompletionCertificatePdfData,
    output_path: Path,
    *,
    template_path: Path = DEFAULT_COMPLETION_CERTIFICATE_TEMPLATE,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pikepdf.open(template_path) as template_pdf:
        if len(template_pdf.pages) != 1:
            raise ValueError(
                "Completion certificate template must contain exactly one page."
            )

        page = template_pdf.pages[0]
        page_width = float(page.mediabox[2]) - float(page.mediabox[0])
        page_height = float(page.mediabox[3]) - float(page.mediabox[1])
        overlay_pdf = build_completion_certificate_overlay(data, page_width, page_height)
        with pikepdf.open(overlay_pdf) as overlay:
            page.add_overlay(overlay.pages[0], push_stack=True, shrink=False, expand=False)

        template_pdf.save(output_path)

    return output_path


def format_completion_certificate_number(
    registration_number: int | str,
    registration_id: str,
) -> str:
    normalized_number = str(registration_number).strip()
    normalized_id = registration_id.strip()
    if not normalized_number or not normalized_id:
        raise ValueError("Certificate number requires registration number and ID.")
    return f"{normalized_id}-{normalized_number}"


def build_completion_certificate_overlay(
    data: CompletionCertificatePdfData,
    page_width: float,
    page_height: float,
) -> BytesIO:
    cjk_bold_font_name = register_completion_certificate_fonts()

    buffer = BytesIO()
    overlay = canvas.Canvas(buffer, pagesize=(page_width, page_height))
    set_fill_color(overlay, PDF_TEXT_COLOR)
    copy = resolve_completion_certificate_copy(data.locale)
    font_name = copy["font_name"]
    latin_font_name = copy["latin_font_name"]
    title_font_name = (
        cjk_bold_font_name if copy["title_font_name"] == PDF_CJK_BOLD_FONT_NAME else copy["title_font_name"]
    )

    draw_text(
        overlay,
        copy["title"],
        FIELD_POSITIONS["certificate_title"],
        int(copy["title_font_size"]),
        title_font_name,
        copy["title_latin_font_name"],
    )
    draw_text(
        overlay,
        f"{copy['number_label']}: {data.certificate_number}",
        FIELD_POSITIONS["certificate_number"],
        14,
        font_name,
        latin_font_name,
    )
    draw_centered_text(
        overlay,
        data.recipient_name,
        FIELD_POSITIONS["recipient_name"],
        32,
        font_name,
        latin_font_name,
    )

    if data.organization.strip():
        draw_centered_text(
            overlay,
            f"{copy['organization_label']}: {data.organization.strip()}",
            FIELD_POSITIONS["organization"],
            16,
            font_name,
            latin_font_name,
        )

    draw_centered_completion_statement(
        overlay,
        copy["statement_prefix"],
        data.event_name,
        copy["statement_suffix"],
        FIELD_POSITIONS["completion_statement"],
        17,
        font_name,
        latin_font_name,
    )
    if data.event_period_text.strip():
        set_fill_color(overlay, PDF_ACCENT_TEXT_COLOR)
        draw_centered_text(
            overlay,
            f"{copy['event_period_label']}: {data.event_period_text.strip()}",
            FIELD_POSITIONS["event_period"],
            16,
            font_name,
            latin_font_name,
        )
    set_fill_color(overlay, PDF_ACCENT_TEXT_COLOR)
    draw_centered_text(
        overlay,
        (
            f"{copy['completion_hours_label']}: "
            f"{max(0, data.completion_hours)} {copy['completion_hours_unit']}"
        ),
        FIELD_POSITIONS["completion_hours"],
        16,
        font_name,
        latin_font_name,
    )
    set_fill_color(overlay, PDF_TEXT_COLOR)
    if data.seal_image_path is not None:
        draw_image(
            overlay,
            data.seal_image_path,
            FIELD_POSITIONS["seal"],
            size=FIELD_SIZES["seal"],
        )
    draw_qr_code(
        overlay,
        data.verification_url,
        FIELD_POSITIONS["qr_code"],
        size=FIELD_SIZES["qr_code"],
        color=(255, 255, 255, 255),
        background_alpha=0,
    )

    overlay.save()
    buffer.seek(0)
    return buffer


def register_completion_certificate_fonts() -> str:
    pdfmetrics.registerFont(UnicodeCIDFont(PDF_CJK_FONT_NAME))

    if PDF_CJK_BOLD_FONT_PATH.exists():
        pdfmetrics.registerFont(
            TTFont(
                PDF_CJK_BOLD_FONT_NAME,
                str(PDF_CJK_BOLD_FONT_PATH),
                subfontIndex=0,
            )
        )
        return PDF_CJK_BOLD_FONT_NAME

    pdfmetrics.registerFont(UnicodeCIDFont(PDF_CJK_BOLD_FALLBACK_FONT_NAME))
    return PDF_CJK_BOLD_FALLBACK_FONT_NAME


def resolve_completion_certificate_copy(locale: str) -> dict[str, str]:
    return COMPLETION_CERTIFICATE_COPY.get(locale, COMPLETION_CERTIFICATE_COPY["zh-TW"])


def set_fill_color(
    overlay: canvas.Canvas,
    color: tuple[float, float, float],
) -> None:
    overlay.setFillColorRGB(*color)


def draw_text(
    overlay: canvas.Canvas,
    text: str,
    position: tuple[float, float],
    font_size: int,
    font_name: str,
    latin_font_name: str,
) -> None:
    draw_mixed_font_text(
        overlay,
        text,
        position[0],
        position[1],
        font_size,
        font_name,
        latin_font_name,
    )


def draw_centered_text(
    overlay: canvas.Canvas,
    text: str,
    position: tuple[float, float],
    font_size: int,
    font_name: str,
    latin_font_name: str,
) -> None:
    text_width = mixed_font_string_width(text, font_name, latin_font_name, font_size)
    draw_mixed_font_text(
        overlay,
        text,
        position[0] - (text_width / 2),
        position[1],
        font_size,
        font_name,
        latin_font_name,
    )


def draw_centered_completion_statement(
    overlay: canvas.Canvas,
    prefix: str,
    event_name: str,
    suffix: str,
    position: tuple[float, float],
    font_size: int,
    font_name: str,
    latin_font_name: str,
) -> None:
    event_font_size = font_size + 5
    segments = [
        (prefix, font_name, latin_font_name, font_size, PDF_TEXT_COLOR),
        (
            event_name,
            font_name,
            latin_font_name,
            event_font_size,
            PDF_ACCENT_TEXT_COLOR,
        ),
        (suffix, font_name, latin_font_name, font_size, PDF_TEXT_COLOR),
    ]
    text_width = sum(
        mixed_font_string_width(text, cjk_font_name, latin_font, segment_font_size)
        for text, cjk_font_name, latin_font, segment_font_size, _ in segments
    )
    cursor_x = position[0] - (text_width / 2)
    for text, cjk_font_name, latin_font, segment_font_size, color in segments:
        set_fill_color(overlay, color)
        cursor_x = draw_mixed_font_text(
            overlay,
            text,
            cursor_x,
            position[1],
            segment_font_size,
            cjk_font_name,
            latin_font,
        )
    set_fill_color(overlay, PDF_TEXT_COLOR)


def draw_mixed_font_text(
    overlay: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    font_size: int,
    cjk_font_name: str,
    latin_font_name: str,
) -> float:
    cursor_x = x
    for run_text, run_font in split_mixed_font_runs(text, cjk_font_name, latin_font_name):
        overlay.setFont(run_font, font_size)
        overlay.drawString(cursor_x, y, run_text)
        cursor_x += overlay.stringWidth(run_text, run_font, font_size)
    return cursor_x


def mixed_font_string_width(
    text: str,
    cjk_font_name: str,
    latin_font_name: str,
    font_size: int,
) -> float:
    return sum(
        pdfmetrics.stringWidth(run_text, run_font, font_size)
        for run_text, run_font in split_mixed_font_runs(
            text,
            cjk_font_name,
            latin_font_name,
        )
    )


def split_mixed_font_runs(
    text: str,
    cjk_font_name: str,
    latin_font_name: str,
) -> list[tuple[str, str]]:
    runs: list[tuple[str, str]] = []
    current_text = ""
    current_font = ""

    for character in text:
        font_name = latin_font_name if should_use_latin_font(character) else cjk_font_name
        if current_text and font_name != current_font:
            runs.append((current_text, current_font))
            current_text = ""
        current_text += character
        current_font = font_name

    if current_text:
        runs.append((current_text, current_font))

    return runs


def should_use_latin_font(character: str) -> bool:
    codepoint = ord(character)
    return 0x20 <= codepoint <= 0x7E


def draw_qr_code(
    overlay: canvas.Canvas,
    value: str,
    position: tuple[float, float],
    *,
    size: int,
    color: tuple[int, int, int, int] = (0, 0, 0, 255),
    background_alpha: int = 255,
) -> None:
    qr = qrcode.QRCode(border=2)
    qr.add_data(value)
    qr.make(fit=True)
    qr_mask = qr.make_image(fill_color="black", back_color="white").convert("L")
    qr_image = Image.new("RGBA", qr_mask.size, (255, 255, 255, background_alpha))
    qr_pixels = qr_image.load()
    mask_pixels = qr_mask.load()
    for y in range(qr_mask.height):
        for x in range(qr_mask.width):
            if mask_pixels[x, y] < 128:
                qr_pixels[x, y] = color
    image_buffer = BytesIO()
    qr_image.save(image_buffer, format="PNG")
    image_buffer.seek(0)
    overlay.drawImage(
        ImageReader(image_buffer),
        position[0],
        position[1],
        width=size,
        height=size,
        mask="auto",
    )


def draw_image(
    overlay: canvas.Canvas,
    image_path: Path,
    position: tuple[float, float],
    *,
    size: float,
) -> None:
    overlay.drawImage(
        ImageReader(str(image_path)),
        position[0],
        position[1],
        width=size,
        height=size,
        mask="auto",
    )
