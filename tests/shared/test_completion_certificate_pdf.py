from pathlib import Path

from PIL import Image
from pypdf import PdfReader

from src.shared.completion_certificate_pdf import (
    CompletionCertificatePdfData,
    DEFAULT_COMPLETION_CERTIFICATE_TEMPLATE,
    PDF_BOLD_FONT_PATH_ENV,
    PDF_REGULAR_FONT_PATH_ENV,
    format_completion_certificate_number,
    register_completion_certificate_fonts,
    render_completion_certificate_pdf,
    resolve_completion_certificate_copy,
)


def test_render_completion_certificate_pdf_writes_single_page_pdf(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "completion-certificate.pdf"

    render_completion_certificate_pdf(
        CompletionCertificatePdfData(
            certificate_number=format_completion_certificate_number(1, "KKTIX-001"),
            recipient_name="王小明",
            organization="好玩公司",
            event_name="iPlayground 2026",
            event_period_text="2026 / 05 / 03 - 2026 / 05 / 04",
            completion_hours=6,
            issued_date_text="2026 / 05 / 11",
            verification_url="https://certificate.iplayground.io/verify/IPG-2026-0001",
        ),
        output_path,
    )

    assert DEFAULT_COMPLETION_CERTIFICATE_TEMPLATE.exists()
    assert output_path.exists()
    output_page = PdfReader(str(output_path)).pages[0]
    output_text = output_page.extract_text()

    assert len(PdfReader(str(output_path)).pages) == 1
    assert "完訓證明" in output_text
    assert "證明編號" in output_text
    assert "KKTIX-001-1" in output_text
    assert "活動期間" in output_text
    assert "2026 / 05 / 03 - 2026 / 05 / 04" in output_text
    assert "完訓時數" in output_text


def test_render_completion_certificate_pdf_supports_english_copy(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "completion-certificate-en.pdf"

    render_completion_certificate_pdf(
        CompletionCertificatePdfData(
            certificate_number=format_completion_certificate_number(1, "KKTIX-001"),
            recipient_name="Ming Wang",
            organization="Fun Software Co.",
            event_name="iPlayground 2026",
            event_period_text="May 3-4, 2026",
            completion_hours=6,
            issued_date_text="May 11, 2026",
            verification_url="https://certificate.iplayground.io/verify/IPG-2026-0001",
            locale="en-US",
        ),
        output_path,
    )

    output_text = PdfReader(str(output_path)).pages[0].extract_text()

    assert "Certificate of Completion" in output_text
    assert "Certificate No.: KKTIX-001-1" in output_text
    assert "Event Period: May 3-4, 2026" in output_text
    assert "Duration: 6 hours" in output_text
    assert "Issue Date" not in output_text


def test_resolve_completion_certificate_copy_uses_locale_catalog() -> None:
    copy = resolve_completion_certificate_copy("en-US")

    assert copy["title"] == "Certificate of Completion"
    assert copy["font_name"] == "Helvetica"


def test_register_completion_certificate_fonts_rejects_missing_configured_font(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        PDF_REGULAR_FONT_PATH_ENV,
        "/missing/ipg-certificate-regular.ttf",
    )
    monkeypatch.delenv(PDF_BOLD_FONT_PATH_ENV, raising=False)

    try:
        register_completion_certificate_fonts()
    except FileNotFoundError as exc:
        assert PDF_REGULAR_FONT_PATH_ENV in str(exc)
    else:
        raise AssertionError("missing configured font path should fail")


def test_render_completion_certificate_pdf_accepts_runtime_seal_image(
    tmp_path: Path,
) -> None:
    seal_path = tmp_path / "seal.png"
    Image.new("RGBA", (24, 24), (255, 0, 0, 180)).save(seal_path)
    output_path = tmp_path / "completion-certificate-with-seal.pdf"

    render_completion_certificate_pdf(
        CompletionCertificatePdfData(
            certificate_number=format_completion_certificate_number(1, "KKTIX-001"),
            recipient_name="王小明",
            organization="好玩公司",
            event_name="iPlayground 2026",
            event_period_text="2026 / 05 / 03 - 2026 / 05 / 04",
            completion_hours=6,
            issued_date_text="2026 / 05 / 11",
            verification_url="https://certificate.iplayground.io/verify/IPG-2026-0001",
            seal_image_path=seal_path,
        ),
        output_path,
    )

    assert output_path.exists()
    assert len(PdfReader(str(output_path)).pages) == 1


def test_format_completion_certificate_number_uses_registration_number_and_id() -> None:
    assert format_completion_certificate_number(12, "KKTIX-987") == "KKTIX-987-12"


def test_completion_certificate_template_keeps_only_static_organizer_text() -> None:
    template_text = PdfReader(str(DEFAULT_COMPLETION_CERTIFICATE_TEMPLATE)).pages[
        0
    ].extract_text()

    assert "主辦單位" in template_text
    assert "完訓證明" not in template_text
    assert "證明編號" not in template_text
