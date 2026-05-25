from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.shared import completion_certificate_pdf as certificate_pdf
from src.shared.completion_certificate_pdf import (
    CompletionCertificatePdfData,
    render_completion_certificate_pdf,
)


DEFAULT_OUTPUT_DIR = Path(
    "/private/tmp/document-assets/volunteer-service-cert/previews/pdf"
)
DEFAULT_LOCAL_SEAL_PATH = Path(
    "/private/tmp/document-assets/shared/organization-seal.png"
)
DEFAULT_WATERMARK_FONT_PATH = REPO_ROOT / "src/shared/pdf_fonts/STHeiti-Medium.ttc"
PREVIEW_CERTIFICATE_NUMBER = "000000000-00"
PREVIEW_WATERMARK_TEXT = "示意樣張 SAMPLE"
PREVIEW_WATERMARK_COLOR = (145, 72, 115)
PREVIEW_WATERMARK_ALPHA = 76
PREVIEW_WATERMARK_STROKE_ALPHA = 72
PREVIEW_WATERMARK_FONT_SIZE = 76
PREVIEW_WATERMARK_ROTATION_DEGREES = -25

VOLUNTEER_SERVICE_CERTIFICATE_COPY = {
    "zh-TW": {
        "title": "志工服務證明",
        "number_label": "證明編號",
        "organization_label": "",
        "statement_prefix": "茲證明於「",
        "statement_suffix": "」擔任志工服務，特發此證明。",
        "event_period_label": "服務期間",
        "completion_hours_label": "服務時數",
        "completion_hours_unit": "小時",
    },
    "en-US": {
        "title": "Certificate of Volunteer Service",
        "number_label": "Certificate No.",
        "organization_label": "",
        "statement_prefix": "This certifies volunteer service for \"",
        "statement_suffix": "\".",
        "event_period_label": "Service Period",
        "completion_hours_label": "Service Hours",
        "completion_hours_unit": "hours",
    },
}

PREVIEW_NAMES = {
    "zh-TW": {
        "name": "林小強",
        "badgeName": "全村的希望",
        "nameWithBadge": "林小強（全村的希望）",
        "organization": "村口整合有限公司",
        "event_name": "iPlayground",
        "event_period": "yyyy/MM/dd - yyyy/MM/dd",
        "issued_date": "2026 / 05 / 11",
    },
    "en-US": {
        "name": "John Appleseed",
        "badgeName": "The Chosen One",
        "nameWithBadge": "John Appleseed (The Chosen One)",
        "organization": "BobaBug Labs, Totally Real Inc.",
        "event_name": "iPlayground",
        "event_period": "mmm dd, yyyy - mmm dd, yyyy",
        "issued_date": "May 11, 2026",
    },
}


def main() -> None:
    args = parse_args()
    magick_path = shutil.which("magick") if args.output_format == "png" else None
    if args.output_format == "png" and magick_path is None:
        raise RuntimeError("ImageMagick is required. Expected `magick` on PATH.")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    if args.input_pdf_dir is not None:
        if args.output_format != "png":
            raise ValueError("--input-pdf-dir can only be used with --output-format png.")
        render_existing_pdf_previews_to_png(
            input_pdf_dir=args.input_pdf_dir,
            output_dir=output_dir,
            magick_path=magick_path,
            density=args.density,
        )
        return

    original_copy_resolver = certificate_pdf.get_completion_certificate_pdf_copy
    original_render_settings = {
        locale: settings.copy()
        for locale, settings in certificate_pdf.COMPLETION_CERTIFICATE_RENDER_SETTINGS.items()
    }
    certificate_pdf.get_completion_certificate_pdf_copy = resolve_volunteer_copy
    certificate_pdf.COMPLETION_CERTIFICATE_RENDER_SETTINGS["en-US"]["title_font_size"] = "30"
    try:
        with tempfile.TemporaryDirectory(prefix="ipg-volunteer-previews-") as temp_dir:
            temp_path = Path(temp_dir)
            for locale in ("zh-TW", "en-US"):
                for name_display in ("name", "badgeName", "nameWithBadge"):
                    for organization_display in ("org", "no-org"):
                        output_path = output_dir / f"{locale}-{name_display}-{organization_display}.{args.output_format}"
                        pdf_path = output_path if args.output_format == "pdf" else (
                            temp_path / f"{locale}-{name_display}-{organization_display}.pdf"
                        )
                        render_completion_certificate_pdf(
                            build_preview_data(
                                locale=locale,
                                name_display=name_display,
                                show_organization=organization_display == "org",
                            ),
                            pdf_path,
                        )
                        if args.output_format == "png":
                            render_pdf_to_png(
                                magick_path=magick_path,
                                pdf_path=pdf_path,
                                png_path=output_path,
                                density=args.density,
                            )
                        print(output_path)
    finally:
        certificate_pdf.get_completion_certificate_pdf_copy = original_copy_resolver
        certificate_pdf.COMPLETION_CERTIFICATE_RENDER_SETTINGS.clear()
        certificate_pdf.COMPLETION_CERTIFICATE_RENDER_SETTINGS.update(original_render_settings)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate local volunteer service certificate preview files."
    )
    parser.add_argument(
        "--output-format",
        choices=("pdf", "png"),
        default="pdf",
        help="Preview output format. Default: pdf",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for generated preview files. Default: {DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--input-pdf-dir",
        type=Path,
        default=None,
        help="Render existing PDFs from this directory to PNG, instead of generating new PDFs.",
    )
    parser.add_argument(
        "--density",
        type=int,
        default=180,
        help="ImageMagick PDF render density. Default: 180",
    )
    return parser.parse_args()


def render_existing_pdf_previews_to_png(
    *,
    input_pdf_dir: Path,
    output_dir: Path,
    magick_path: str,
    density: int,
) -> None:
    pdf_paths = sorted(input_pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found in {input_pdf_dir}.")

    for pdf_path in pdf_paths:
        png_path = output_dir / f"{pdf_path.stem}.png"
        render_pdf_to_png(
            magick_path=magick_path,
            pdf_path=pdf_path,
            png_path=png_path,
            density=density,
        )
        print(png_path)


def resolve_volunteer_copy(locale: str) -> dict[str, str]:
    return VOLUNTEER_SERVICE_CERTIFICATE_COPY.get(
        locale,
        VOLUNTEER_SERVICE_CERTIFICATE_COPY["zh-TW"],
    )


def build_preview_data(
    *,
    locale: str,
    name_display: str,
    show_organization: bool,
) -> CompletionCertificatePdfData:
    preview = PREVIEW_NAMES[locale]
    return CompletionCertificatePdfData(
        certificate_number=PREVIEW_CERTIFICATE_NUMBER,
        recipient_name=preview[name_display],
        organization=preview["organization"] if show_organization else "",
        event_name=preview["event_name"],
        event_period_text=preview["event_period"],
        completion_hours=6,
        issued_date_text=preview["issued_date"],
        verification_url="https://cert.iplayground.io/",
        locale=locale,
        seal_image_path=resolve_seal_image_path(),
    )


def resolve_seal_image_path() -> Path | None:
    configured = os.environ.get("COMPLETION_CERTIFICATE_SEAL_IMAGE_PATH", "").strip()
    if not configured:
        if DEFAULT_LOCAL_SEAL_PATH.exists():
            return DEFAULT_LOCAL_SEAL_PATH
    if not configured:
        raise FileNotFoundError(
            "Volunteer service certificate previews require a seal image. Set "
            "COMPLETION_CERTIFICATE_SEAL_IMAGE_PATH or provide "
            f"{DEFAULT_LOCAL_SEAL_PATH}."
        )

    path = Path(configured)
    if not path.exists():
        raise FileNotFoundError(
            f"COMPLETION_CERTIFICATE_SEAL_IMAGE_PATH points to a missing file: {path}"
        )
    return path


def render_pdf_to_png(
    *,
    magick_path: str,
    pdf_path: Path,
    png_path: Path,
    density: int,
) -> None:
    cache_dir = Path("/private/tmp/ipg-certificate-fontconfig-cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    environment = {
        **os.environ,
        "XDG_CACHE_HOME": str(cache_dir),
        "MAGICK_TEMPORARY_PATH": str(cache_dir),
    }
    subprocess.run(
        [
            magick_path,
            "-density",
            str(density),
            str(pdf_path),
            "-background",
            "white",
            "-alpha",
            "remove",
            "-alpha",
            "off",
            "-resize",
            "1600x",
            "-strip",
            "-depth",
            "8",
            str(png_path),
        ],
        check=True,
        env=environment,
    )
    apply_preview_watermark(png_path)


def apply_preview_watermark(png_path: Path) -> None:
    with Image.open(png_path).convert("RGBA") as base_image:
        font = ImageFont.truetype(
            str(DEFAULT_WATERMARK_FONT_PATH),
            PREVIEW_WATERMARK_FONT_SIZE,
            index=0,
        )
        stamp = build_watermark_stamp(font)
        padding = max(base_image.size)
        layer_size = (
            base_image.width + padding * 2,
            base_image.height + padding * 2,
        )
        watermark_layer = Image.new("RGBA", layer_size, (255, 255, 255, 0))

        step_x = int(stamp.width * 1.38)
        step_y = int(stamp.height * 2.05)
        start_y = padding - stamp.height + 24
        start_x = padding - stamp.width + 200
        for y in range(start_y, layer_size[1] + stamp.height, step_y):
            for x in range(start_x, layer_size[0] + stamp.width, step_x):
                watermark_layer.alpha_composite(stamp, (x, y))

        watermark_layer = watermark_layer.rotate(
            PREVIEW_WATERMARK_ROTATION_DEGREES,
            expand=False,
            resample=Image.Resampling.BICUBIC,
        ).crop(
            (
                padding,
                padding,
                padding + base_image.width,
                padding + base_image.height,
            )
        )
        watermarked = Image.alpha_composite(base_image, watermark_layer).convert("RGB")
        watermarked.save(png_path, format="PNG", optimize=True)


def build_watermark_stamp(font: ImageFont.FreeTypeFont) -> Image.Image:
    scratch = Image.new("RGBA", (1, 1), (255, 255, 255, 0))
    scratch_draw = ImageDraw.Draw(scratch)
    bbox = scratch_draw.textbbox((0, 0), PREVIEW_WATERMARK_TEXT, font=font)
    width = bbox[2] - bbox[0] + 96
    height = bbox[3] - bbox[1] + 56
    stamp = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    stamp_draw = ImageDraw.Draw(stamp)
    stamp_draw.text(
        (48 - bbox[0], 28 - bbox[1]),
        PREVIEW_WATERMARK_TEXT,
        font=font,
        fill=(*PREVIEW_WATERMARK_COLOR, PREVIEW_WATERMARK_ALPHA),
        stroke_width=2,
        stroke_fill=(255, 255, 255, PREVIEW_WATERMARK_STROKE_ALPHA),
    )
    return stamp


if __name__ == "__main__":
    main()
