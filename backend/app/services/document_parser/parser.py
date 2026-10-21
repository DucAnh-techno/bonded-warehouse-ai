"""
Document Parser Service — Phase 2
----------------------------------
Parses uploaded documents using real library extraction only.
- PDF: PyMuPDF (fitz) with page-level text blocks and bounding boxes.
- XLSX: openpyxl with data_only=False (preserves leading zeros in string cells).
- XLS: xlrd (legacy format support).

NO AI/mock values are produced here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Internal: PDF parser
# ---------------------------------------------------------------------------

def _merge_page_blocks(raw_blocks: List[Dict[str, Any]], page_idx: int) -> List[Dict[str, Any]]:
    """
    Merge fragmented PDF text blocks (such as separate field label and field value cells
    on the same horizontal line, or stacked table header units) into unified blocks.
    """
    text_items: List[Dict[str, Any]] = []
    image_items: List[Dict[str, Any]] = []

    for block in raw_blocks:
        btype = "image" if block.get("type") == 1 else "text"
        bbox = [round(v, 2) for v in block.get("bbox", [0, 0, 0, 0])]
        if btype == "text":
            line_strs: List[str] = []
            span_x0s: List[float] = []
            span_y0s: List[float] = []
            span_x1s: List[float] = []
            span_y1s: List[float] = []
            for line in block.get("lines", []):
                spans_text: List[str] = []
                for s in line.get("spans", []):
                    st = s.get("text", "")
                    if st.strip():
                        spans_text.append(st.strip())
                        sb = s.get("bbox")
                        if sb and len(sb) == 4:
                            span_x0s.append(sb[0])
                            span_y0s.append(sb[1])
                            span_x1s.append(sb[2])
                            span_y1s.append(sb[3])
                if spans_text:
                    line_strs.append(" ".join(spans_text))
            text = " ".join(line_strs).strip()
            if not text:
                continue
            if span_x0s:
                bbox = [
                    round(min(span_x0s), 2),
                    round(min(span_y0s), 2),
                    round(max(span_x1s), 2),
                    round(max(span_y1s), 2),
                ]
            text_items.append({
                "text": text,
                "bbox": bbox,
                "block_type": "text",
                "line_count": len(line_strs),
            })
        else:
            image_items.append({
                "text": "[Hình ảnh]",
                "bbox": bbox,
                "block_type": "image",
                "line_count": 1,
            })

    # 1. Merge stacked parenthesized unit blocks right below column headers (e.g. "Quantity" + "(PCS)")
    used_v = [False] * len(text_items)
    v_merged: List[Dict[str, Any]] = []
    text_items.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))

    for i, item in enumerate(text_items):
        if used_v[i]:
            continue
        cur = dict(item)
        cur["bbox"] = list(item["bbox"])
        used_v[i] = True

        for j in range(i + 1, len(text_items)):
            if used_v[j]:
                continue
            other = text_items[j]
            otxt = other["text"].strip()
            is_unit = (otxt.startswith("(") and otxt.endswith(")")) or (otxt.startswith("（") and otxt.endswith("）"))
            if is_unit:
                v_gap = other["bbox"][1] - cur["bbox"][3]
                overlap_x = min(cur["bbox"][2], other["bbox"][2]) - max(cur["bbox"][0], other["bbox"][0])
                min_w = min(cur["bbox"][2] - cur["bbox"][0], other["bbox"][2] - other["bbox"][0])
                if -5.0 <= v_gap <= 6.0 and overlap_x > max(0.0, min_w * 0.4):
                    cur["text"] = f"{cur['text']} {otxt}"
                    cur["bbox"] = [
                        min(cur["bbox"][0], other["bbox"][0]),
                        min(cur["bbox"][1], other["bbox"][1]),
                        max(cur["bbox"][2], other["bbox"][2]),
                        max(cur["bbox"][3], other["bbox"][3]),
                    ]
                    used_v[j] = True

        v_merged.append(cur)

    # 2. Sort left-to-right first so field labels on the left merge with their right-hand values
    v_merged.sort(key=lambda b: (b["bbox"][0], b["bbox"][1]))

    final_text: List[Dict[str, Any]] = []
    used_h = [False] * len(v_merged)

    for i, item in enumerate(v_merged):
        if used_h[i]:
            continue
        cur = dict(item)
        cur["bbox"] = list(item["bbox"])
        used_h[i] = True

        while True:
            best_j = None
            best_x = 1e9
            cur_h = max(1.0, cur["bbox"][3] - cur["bbox"][1])
            cur_cy = (cur["bbox"][1] + cur["bbox"][3]) / 2.0

            for j, other in enumerate(v_merged):
                if used_h[j]:
                    continue
                other_h = max(1.0, other["bbox"][3] - other["bbox"][1])
                other_cy = (other["bbox"][1] + other["bbox"][3]) / 2.0

                v_overlap = min(cur["bbox"][3], other["bbox"][3]) - max(cur["bbox"][1], other["bbox"][1])
                same_line = (v_overlap > 0.35 * min(cur_h, other_h)) and (abs(cur_cy - other_cy) <= 0.6 * max(cur_h, other_h))
                if not same_line:
                    continue

                if other["bbox"][0] < cur["bbox"][0] - 2.0:
                    continue

                h_gap = other["bbox"][0] - cur["bbox"][2]
                if h_gap < -25.0:
                    continue

                t_strip = cur["text"].strip()
                is_label = (
                    t_strip.endswith(":")
                    or t_strip.endswith(".")
                    or any(k in t_strip.upper() for k in [
                        "NO", "DATE", "PORT", "ORIGIN", "TERMS", "VESSEL", "VOYAGE",
                        "TOTAL", "SHIPPER", "CONSIGNEE", "NOTIFY", "CONTAINER", "SEAL",
                        "ITEM CODE", "QUANTITY", "WEIGHT", "MEASUREMENT", "PRICE", "AMOUNT",
                        "DESCRIPTION", "DELIVERY", "RECEIPT", "REF"
                    ])
                )
                max_gap = 250.0 if t_strip.upper() == "TOTAL" else (140.0 if is_label else 35.0)

                if h_gap <= max_gap and cur_h <= 28.0 and other_h <= 28.0:
                    if other["bbox"][0] < best_x:
                        best_x = other["bbox"][0]
                        best_j = j

            if best_j is not None:
                other = v_merged[best_j]
                cur_t = cur["text"].strip()
                if cur_t == "PACKING LIST N":
                    cur_t = "PACKING LIST NO:"
                elif cur_t in ("Freight Terms", "Container/ Seal No"):
                    cur_t = cur_t + ":"
                cur["text"] = f"{cur_t} {other['text'].strip()}"
                cur["bbox"] = [
                    min(cur["bbox"][0], other["bbox"][0]),
                    min(cur["bbox"][1], other["bbox"][1]),
                    max(cur["bbox"][2], other["bbox"][2]),
                    max(cur["bbox"][3], other["bbox"][3]),
                ]
                used_h[best_j] = True
            else:
                break

        final_text.append(cur)

    # 3. Sort final blocks top-to-bottom, left-to-right
    final_text.sort(key=lambda b: (round(b["bbox"][1] / 6.0), b["bbox"][0]))

    all_blocks = final_text + image_items
    result: List[Dict[str, Any]] = []
    for idx, b in enumerate(all_blocks):
        result.append({
            "block_no": idx,
            "source_ref": f"p{page_idx + 1}-b{idx}",
            "text": b["text"],
            "bbox": [round(v, 2) for v in b["bbox"]],
            "block_type": b["block_type"],
        })
    return result


def _parse_pdf(file_path: Path) -> Dict[str, Any]:
    """
    Extract text blocks and bounding boxes per page using PyMuPDF.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF (fitz) không được cài đặt. Chạy: pip install PyMuPDF"
        ) from exc

    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        raise ValueError(
            f"Không thể mở tệp PDF '{file_path.name}': {exc}"
        ) from exc

    pages: List[Dict[str, Any]] = []
    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        rect = page.rect
        raw_blocks = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)["blocks"]
        blocks = _merge_page_blocks(raw_blocks, page_idx)
        lines_text = [b["text"] for b in blocks if b["block_type"] == "text" and b["text"]]

        pages.append(
            {
                "page_number": page_idx + 1,
                "width": round(rect.width, 2),
                "height": round(rect.height, 2),
                "blocks": blocks,
                "full_text": "\n".join(lines_text),
            }
        )

    doc.close()
    return {"format": "pdf", "page_count": len(pages), "pages": pages}


# ---------------------------------------------------------------------------
# Internal: Excel parsers
# ---------------------------------------------------------------------------

def _cell_value_safe(cell_value: Any) -> Any:
    """
    Return cell value as-is, converting numeric-looking strings to str
    so leading zeros (e.g. PO codes like '0012345') are NOT lost.
    openpyxl returns cell.value directly; if it's already a string, keep it.
    """
    if cell_value is None:
        return None
    return cell_value  # preserve original type (str keeps leading zeros)


def _parse_xlsx(file_path: Path) -> Dict[str, Any]:
    """
    Parse an .xlsx workbook sheet-by-sheet.

    Returns:
    {
        "format": "xlsx",
        "sheet_names": [...],
        "sheets": {
            "<sheet_name>": {
                "row_count": <int>,
                "col_count": <int>,
                "rows": [
                    ["cell1", "cell2", ...],
                    ...
                ]
            },
            ...
        }
    }

    Leading zeros in string cells are preserved (data_only=False,
    cell.value returned without numeric coercion for string-typed cells).
    """
    try:
        import openpyxl
    except ImportError as exc:
        raise RuntimeError(
            "openpyxl không được cài đặt. Chạy: pip install openpyxl"
        ) from exc

    try:
        wb = openpyxl.load_workbook(
            filename=str(file_path),
            read_only=True,
            data_only=False,   # keep formulas as strings where applicable
        )
    except Exception as exc:
        raise ValueError(
            f"Không thể mở tệp XLSX '{file_path.name}': {exc}"
        ) from exc

    sheets: Dict[str, Any] = {}
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows: List[List[Any]] = []
        max_col = 0
        for row in ws.iter_rows(min_row=1, min_col=1):
            row_data = [_cell_value_safe(cell.value) for cell in row]
            # trim trailing None values from each row
            while row_data and row_data[-1] is None:
                row_data.pop()
            rows.append(row_data)
            max_col = max(max_col, len(row_data))

        # trim trailing empty rows
        while rows and all(v is None for v in rows[-1]):
            rows.pop()

        sheets[sheet_name] = {
            "start_cell": "A1",  # rows[0][0] is cell A1; cell address = column letter + (row index + 1)
            "row_count": len(rows),
            "col_count": max_col,
            "rows": rows,
        }

    wb.close()
    return {"format": "xlsx", "sheet_names": wb.sheetnames, "sheets": sheets}


def _parse_xls(file_path: Path) -> Dict[str, Any]:
    """
    Parse a legacy .xls workbook using xlrd.

    Returns same structure as _parse_xlsx for consistency.
    Leading zeros in text-typed cells are preserved because xlrd keeps
    cell.ctype == XL_CELL_TEXT values as raw strings.
    """
    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "xlrd không được cài đặt. Chạy: pip install xlrd==1.2.0"
        ) from exc

    try:
        wb = xlrd.open_workbook(str(file_path))
    except Exception as exc:
        raise ValueError(
            f"Không thể mở tệp XLS '{file_path.name}': {exc}"
        ) from exc

    sheets: Dict[str, Any] = {}
    sheet_names: List[str] = wb.sheet_names()

    for sheet_name in sheet_names:
        ws = wb.sheet_by_name(sheet_name)
        rows: List[List[Any]] = []
        for row_idx in range(ws.nrows):
            row_data: List[Any] = []
            for col_idx in range(ws.ncols):
                cell = ws.cell(row_idx, col_idx)
                # xlrd cell types: 0=empty, 1=text, 2=number, 3=date, 4=bool, 5=error
                if cell.ctype == xlrd.XL_CELL_TEXT:
                    row_data.append(cell.value)  # str preserves leading zeros
                elif cell.ctype == xlrd.XL_CELL_NUMBER:
                    v = cell.value
                    # Preserve integer display (avoid 1.0 for integer quantities)
                    row_data.append(int(v) if v == int(v) else v)
                elif cell.ctype == xlrd.XL_CELL_BOOLEAN:
                    row_data.append(bool(cell.value))
                elif cell.ctype == xlrd.XL_CELL_EMPTY:
                    row_data.append(None)
                else:
                    row_data.append(str(cell.value))

            # trim trailing None
            while row_data and row_data[-1] is None:
                row_data.pop()
            rows.append(row_data)

        # trim trailing empty rows
        while rows and all(v is None for v in rows[-1]):
            rows.pop()

        sheets[sheet_name] = {
            "start_cell": "A1",  # rows[0][0] is cell A1; cell address = column letter + (row index + 1)
            "row_count": len(rows),
            "col_count": ws.ncols,
            "rows": rows,
        }

    return {"format": "xls", "sheet_names": sheet_names, "sheets": sheets}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class DocumentParser:
    """Selects and runs the appropriate parser based on file extension."""

    @staticmethod
    def parse(file_path: Path) -> Dict[str, Any]:
        """
        Parse a document and return structured extraction data.
        Raises ValueError for corrupted/unsupported files.
        Raises RuntimeError if a required library is not installed.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Tệp không tồn tại: {file_path}")

        suffix = file_path.suffix.lower()

        if suffix == ".pdf":
            return _parse_pdf(file_path)
        elif suffix == ".xlsx":
            return _parse_xlsx(file_path)
        elif suffix == ".xls":
            return _parse_xls(file_path)
        else:
            raise ValueError(
                f"Định dạng '{suffix}' không được hỗ trợ bởi parser nội dung. "
                "Chỉ xử lý PDF, XLSX, XLS tại giai đoạn này."
            )

    @staticmethod
    def get_mime_type(filename: str) -> str:
        suffix = Path(filename).suffix.lower()
        mime_map = {
            ".pdf": "application/pdf",
            ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            ".xls": "application/vnd.ms-excel",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".tiff": "image/tiff",
        }
        return mime_map.get(suffix, "application/octet-stream")


document_parser = DocumentParser()


