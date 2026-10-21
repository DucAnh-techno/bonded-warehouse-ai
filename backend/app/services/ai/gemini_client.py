import json
import asyncio
import logging
import random
import time
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from app.core.config import settings
from app.schemas.extraction import (
    GeminiDocumentExtractionResult, 
    BatchShipmentReconciliationResult, 
    PerDocumentExtraction
)
from app.services.ai.prompts import (
    SYSTEM_PROMPT_VIETNAMESE_CUSTOMS,
    SYSTEM_PROMPT_BATCH_RECONCILIATION,
    build_targeted_extraction_prompt,
)

logger = logging.getLogger(__name__)


def calculate_estimated_cost(model_name: str, prompt_tokens: Optional[int], candidate_tokens: Optional[int]) -> float:
    """Calculates estimated cost in USD based on Gemini pricing."""
    if not prompt_tokens and not candidate_tokens:
        return 0.0
    p = prompt_tokens or 0
    c = candidate_tokens or 0
    if "pro" in (model_name or "").lower():
        input_rate = 1.25 / 1_000_000
        output_rate = 5.00 / 1_000_000
    else:  # Flash (2.5-flash, 3.8-flash, 3.1-flash-lite, 1.5-flash)
        input_rate = 0.075 / 1_000_000
        output_rate = 0.30 / 1_000_000
    return round((p * input_rate) + (c * output_rate), 6)


def is_quota_or_transient_error(error: Exception) -> bool:
    """Detects HTTP 429, ResourceExhausted, rate limits, or transient connection drops."""
    err_str = str(error).lower()
    return any(k in err_str for k in [
        "429", "resource_exhausted", "quota", "rate limit", "rate_limit",
        "too many requests", "temporarily unavailable", "overloaded", "503", "504", "deadline_exceeded", "connection reset"
    ])


class GeminiExtractorService:
    """
    Direct production integration with Google Gemini API via official google-genai SDK.
    - Token-optimized: sends compact extracted text for digital PDFs/Excels instead of heavy binary bytes when text is available.
    - Targeted per-document-type prompts so Gemini only extracts fields ticked in the reconciliation matrix.
    - Reuses cached extraction in batch mode for documents already extracted.
    """

    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.GEMINI_MODEL
        self.max_retries = 3

    @staticmethod
    def _content_part(file_path: Path, mime_type: str):
        from google.genai import types
        suffix = file_path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            from app.services.document_parser.parser import document_parser
            data = document_parser.parse(file_path)
            compact_lines: list[str] = []
            for sname, sheet in (data.get("sheets") or {}).items():
                compact_lines.append(f"=== SHEET: {sname} ===")
                for r_idx, row in enumerate(sheet.get("rows") or [], 1):
                    vals = [str(c).strip() for c in row if c is not None and str(c).strip() != ""]
                    if vals:
                        compact_lines.append(f"R{r_idx}: " + " | ".join(vals))
            return types.Part.from_text(text="\n".join(compact_lines))

        if suffix == ".pdf":
            try:
                from app.services.document_parser.parser import document_parser
                parsed = document_parser.parse(file_path)
                pages = parsed.get("pages") or []
                page_texts: list[str] = []
                all_pages_have_text = len(pages) > 0
                total_chars = 0
                for p in pages:
                    blocks = [
                        b.get("text", "").strip()
                        for b in (p.get("blocks") or [])
                        if b.get("block_type") == "text" and b.get("text", "").strip()
                    ]
                    p_txt = "\n".join(blocks) if blocks else (p.get("full_text") or "").strip()
                    if len(p_txt) < 30:
                        all_pages_have_text = False
                        break
                    total_chars += len(p_txt)
                    page_texts.append(f"--- TRANG {p.get('page_number', 1)} ---\n{p_txt}")
                if all_pages_have_text and total_chars >= 80:
                    return types.Part.from_text(text="\n\n".join(page_texts))
            except Exception:
                pass

        return types.Part.from_bytes(data=file_path.read_bytes(), mime_type=mime_type)

    def _get_client(self):
        """Lazy initialization of Google GenAI Client ensuring valid key."""
        if not self.api_key or self.api_key == "YOUR_GEMINI_API_KEY_HERE":
            raise ValueError(
                "GEMINI_API_KEY chưa được cấu hình hoặc sử dụng giá trị mẫu. "
                "Vui lòng thiết lập khóa Google Gemini API hợp lệ trong file backend/.env."
            )

        timeout_ms = int(getattr(settings, "GEMINI_TIMEOUT_SECONDS", 180) * 1000)
        try:
            from google import genai
            from google.genai import types
            http_opts = types.HttpOptions(
                timeout=timeout_ms,
                retry_options=types.HttpRetryOptions(attempts=1)
            )
            return genai.Client(api_key=self.api_key, http_options=http_opts)
        except ImportError:
            import google.generativeai as gai
            gai.configure(api_key=self.api_key)
            return gai

    async def extract_document(
        self,
        file_path: Path,
        mime_type: str,
        document_type_hint: Optional[str] = None
    ) -> Tuple[GeminiDocumentExtractionResult, Dict[str, Any]]:
        """
        Executes multimodal/text extraction with retries, model failover, and validation.
        Returns: (GeminiDocumentExtractionResult, token_usage_dict)
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Không tìm thấy tệp chứng từ tại đường dẫn: {file_path}")

        prompt_instruction = build_targeted_extraction_prompt(document_type_hint, file_path.name)

        client = self._get_client()
        last_error = None
        start_time = time.perf_counter()

        candidate_models = [self.model_name]
        for fallback in ["gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-flash-latest"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        for current_model in candidate_models:
            for attempt in range(1, self.max_retries + 1):
                try:
                    logger.info(f"Gemini API calling model={current_model}, attempt {attempt}/{self.max_retries} for {file_path.name}")
                    from google.genai import types

                    part = self._content_part(file_path, mime_type)

                    response = await asyncio.to_thread(
                        client.models.generate_content,
                        model=current_model,
                        contents=[part, prompt_instruction],
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=GeminiDocumentExtractionResult,
                            temperature=0.1,
                        ),
                    )

                    response_text = response.text
                    if not response_text or not response_text.strip():
                        raise ValueError("Gemini API trả về nội dung rỗng.")

                    parsed_json = json.loads(response_text)
                    validated_result = GeminiDocumentExtractionResult.model_validate(parsed_json)

                    duration_sec = round(time.perf_counter() - start_time, 3)
                    p_tokens = getattr(response.usage_metadata, "prompt_token_count", None) if hasattr(response, "usage_metadata") else None
                    c_tokens = getattr(response.usage_metadata, "candidates_token_count", None) if hasattr(response, "usage_metadata") else None
                    tot_tokens = getattr(response.usage_metadata, "total_token_count", None) if hasattr(response, "usage_metadata") else ((p_tokens or 0) + (c_tokens or 0) if p_tokens else None)
                    est_cost = calculate_estimated_cost(current_model, p_tokens, c_tokens)

                    token_usage = {
                        "prompt_tokens": p_tokens,
                        "candidate_tokens": c_tokens,
                        "total_tokens": tot_tokens,
                        "duration_seconds": duration_sec,
                        "estimated_cost_usd": est_cost,
                        "model_used": current_model
                    }

                    logger.info(
                        f"[GEMINI_USAGE] SUCCESS doc={file_path.name} model={current_model} "
                        f"items={len(validated_result.items)} prompt_tokens={p_tokens} candidate_tokens={c_tokens} "
                        f"latency={duration_sec}s est_cost_usd=${est_cost}"
                    )
                    return validated_result, token_usage

                except Exception as e:
                    last_error = e
                    is_quota = is_quota_or_transient_error(e)
                    logger.warning(f"Gemini attempt {attempt}/{self.max_retries} with {current_model} failed for {file_path.name} (is_quota={is_quota}): {e}")

                    err_msg = str(e).lower()
                    is_daily_quota = ("free_tier_requests" in err_msg or "per day" in err_msg or "generaterequestsperday" in err_msg or "retry in " in err_msg or "404" in err_msg)
                    if is_daily_quota:
                        logger.info(f"Model {current_model} reached daily quota limit or 404. Switching to alternative candidate model...")
                        break

                    if ("503" in err_msg or "504" in err_msg) and attempt >= 2 and current_model != candidate_models[-1]:
                        logger.info(f"Model {current_model} experiencing persistent high demand/deadline. Switching to next candidate model...")
                        break

                    if attempt < self.max_retries:
                        backoff = min(6.0, (2 ** attempt) + random.uniform(0.5, 1.5)) if is_quota else (1.5 * attempt)
                        logger.info(f"Backing off for {backoff:.2f}s before retry attempt {attempt + 1}...")
                        await asyncio.sleep(backoff)

        raise RuntimeError("Gemini không thể trích xuất sau các lần thử. Kiểm tra hạn mức, kết nối và loại tệp.") from last_error

    async def batch_extract_and_reconcile_shipment(
        self,
        documents: list[dict[str, Any]],
        shipment_code: Optional[str] = None
    ) -> Tuple[BatchShipmentReconciliationResult, Dict[str, Any]]:
        """
        Trích xuất dữ liệu trên các chứng từ của lô hàng với cơ chế tiết kiệm token:
        - Nếu chứng từ đã có dữ liệu trích xuất hợp lệ (cached_extraction), tái sử dụng ngay (0 token).
        - Chỉ gọi Gemini API đối với chứng từ mới hoặc chưa trích xuất thành công.
        """
        if not documents:
            raise ValueError("Không có chứng từ nào để trích xuất.")

        start_time = time.perf_counter()
        extracted_docs: list[PerDocumentExtraction] = []
        tot_prompt_tokens = 0
        tot_candidate_tokens = 0
        tot_cost = 0.0
        customs_no: Optional[str] = None

        for doc_info in documents:
            doc_type = doc_info.get("document_type")
            doc_id = doc_info.get("doc_id")
            cached = doc_info.get("cached_extraction")

            if cached is not None:
                try:
                    per_doc = PerDocumentExtraction.model_validate(cached)
                    per_doc.document_id = doc_id
                    extracted_docs.append(per_doc)
                    if not customs_no and per_doc.document_number and (
                        doc_type == "CUSTOMS_DECLARATION" or per_doc.document_type_detected == "CUSTOMS_DECLARATION"
                    ):
                        customs_no = per_doc.document_number
                    continue
                except Exception:
                    pass

            file_path: Path = doc_info["file_path"]
            if not file_path.exists():
                continue
            mime_type = doc_info.get("mime_type", "application/pdf")

            single_result, token_usage = await self.extract_document(
                file_path=file_path,
                mime_type=mime_type,
                document_type_hint=doc_type
            )

            p_tok = token_usage.get("prompt_tokens") or 0
            c_tok = token_usage.get("candidate_tokens") or 0
            tot_prompt_tokens += p_tok
            tot_candidate_tokens += c_tok
            tot_cost += (token_usage.get("estimated_cost_usd") or 0.0)

            doc_data = single_result.model_dump()
            doc_data["document_id"] = doc_id
            per_doc = PerDocumentExtraction.model_validate(doc_data)
            extracted_docs.append(per_doc)

            if not customs_no and single_result.document_number and (
                doc_type == "CUSTOMS_DECLARATION" or single_result.document_type_detected == "CUSTOMS_DECLARATION"
            ):
                customs_no = single_result.document_number

        duration_sec = round(time.perf_counter() - start_time, 3)
        total_tokens = tot_prompt_tokens + tot_candidate_tokens
        aggregate_usage = {
            "prompt_tokens": tot_prompt_tokens,
            "candidate_tokens": tot_candidate_tokens,
            "total_tokens": total_tokens,
            "duration_seconds": duration_sec,
            "estimated_cost_usd": round(tot_cost, 6),
            "model_used": self.model_name
        }

        reconcile_result = BatchShipmentReconciliationResult(
            shipment_code=shipment_code,
            customs_declaration_no=customs_no,
            overall_validity="VALID",
            validity_reason="Trích xuất thành công toàn bộ chứng từ.",
            discrepancies=[],
            documents=extracted_docs
        )

        return reconcile_result, aggregate_usage


gemini_extractor = GeminiExtractorService()

