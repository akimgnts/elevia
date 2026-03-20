from __future__ import annotations

from api.utils.pdf_text import PdfTextError, extract_text_from_pdf

from .contracts import FileIngestionResult, PipelineHTTPError, TextExtractionResult
from .ingestion_stage import is_pdf


def extract_profile_text(ingestion: FileIngestionResult) -> TextExtractionResult:
    if is_pdf(ingestion.content_type, ingestion.filename):
        try:
            cv_text = extract_text_from_pdf(ingestion.data)
        except PdfTextError as exc:
            raise PipelineHTTPError(
                status_code=422,
                detail={
                    "error": exc.message,
                    "code": exc.code,
                    "hint": "Try a text-layer PDF or paste the CV text at /profile/parse-baseline",
                    "request_id": ingestion.request_id,
                },
            ) from exc
    else:
        cv_text = ingestion.data.decode("utf-8", errors="ignore")

    cv_text = cv_text.strip()
    if not cv_text:
        raise PipelineHTTPError(
            status_code=422,
            detail={
                "error": "No text extracted from file",
                "request_id": ingestion.request_id,
            },
        )

    return TextExtractionResult(
        request_id=ingestion.request_id,
        filename=ingestion.filename,
        content_type=ingestion.content_type,
        cv_text=cv_text,
        warnings=[],
    )
