from __future__ import annotations

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.shared.completion_certificate_pdf import (
    CompletionCertificatePdfData,
    format_completion_certificate_number,
    render_completion_certificate_pdf,
)


def main() -> None:
    seal_image_path = Path("/Users/haolee/Downloads/圖片 1.png")
    samples = [
        (
            Path("/private/tmp/ipg_completion_certificate_sample_zh-TW.pdf"),
            CompletionCertificatePdfData(
                certificate_number=format_completion_certificate_number(1, "KKTIX-001"),
                recipient_name="王小明",
                organization="好玩公司",
                event_name="iPlayground 2026",
                event_period_text="2026 / 05 / 03 - 2026 / 05 / 04",
                completion_hours=6,
                issued_date_text="2026 / 05 / 11",
                verification_url="https://certificate.iplayground.io/verify/IPG-2026-0001",
                locale="zh-TW",
                seal_image_path=seal_image_path,
            ),
        ),
        (
            Path("/private/tmp/ipg_completion_certificate_sample_en-US.pdf"),
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
                seal_image_path=seal_image_path,
            ),
        ),
    ]
    for output_path, data in samples:
        render_completion_certificate_pdf(data, output_path)
        print(output_path)


if __name__ == "__main__":
    main()
