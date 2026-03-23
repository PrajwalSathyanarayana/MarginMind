import tempfile
import io
import base64
from shutil import which
from pathlib import Path
import fitz
import pdfplumber

try:
    import numpy as np
except ImportError:
    np = None

try:
    import cv2
except ImportError:
    cv2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None


TESSERACT_AVAILABLE = bool(pytesseract and Image and which("tesseract"))

if pytesseract and Image and not TESSERACT_AVAILABLE:
    # Fallback for shells where Homebrew path is not exported.
    for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if Path(candidate).exists():
            pytesseract.pytesseract.tesseract_cmd = candidate
            TESSERACT_AVAILABLE = True
            break


def _safe_ocr_text_from_bytes(image_bytes: bytes) -> str:
    if not TESSERACT_AVAILABLE:
        return ""
    try:
        pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return pytesseract.image_to_string(pil_image) or ""
    except Exception:
        return ""


def _decode_image_to_bgr(image_bytes: bytes):
    if not np:
        return None, 0, 0

    # Fast path for common formats supported by OpenCV.
    if cv2:
        np_img = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
        if decoded is not None:
            h, w = decoded.shape[:2]
            return decoded, w, h

    # Fallback path for formats OpenCV may not decode well on macOS (e.g., HEIC).
    if Image:
        try:
            pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
            rgb = np.array(pil_image)
            if cv2:
                bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
            else:
                bgr = rgb
            h, w = bgr.shape[:2]
            return bgr, w, h
        except Exception:
            return None, 0, 0

    return None, 0, 0


def _pixmap_png_bytes(page: fitz.Page, zoom: float = 2.0) -> bytes:
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)
    return pix.tobytes("png")


def _safe_ocr_text_from_pdf_page(page: fitz.Page) -> str:
    return _safe_ocr_text_from_bytes(_pixmap_png_bytes(page))


def _bytes_to_data_url(image_bytes: bytes, mime: str = "image/png") -> str:
    if not image_bytes:
        return ""
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _normalize_bbox(bbox, width: float, height: float) -> dict:
    x0, y0, x1, y1 = bbox
    w = max(1.0, width)
    h = max(1.0, height)
    return {
        "x0": round(max(0.0, x0) / w, 4),
        "y0": round(max(0.0, y0) / h, 4),
        "x1": round(min(w, x1) / w, 4),
        "y1": round(min(h, y1) / h, 4),
    }


def _bbox_iou(a, b) -> float:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b

    ix0 = max(ax0, bx0)
    iy0 = max(ay0, by0)
    ix1 = min(ax1, bx1)
    iy1 = min(ay1, by1)

    iw = max(0, ix1 - ix0)
    ih = max(0, iy1 - iy0)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    a_area = max(1, ax1 - ax0) * max(1, ay1 - ay0)
    b_area = max(1, bx1 - bx0) * max(1, by1 - by0)
    union = a_area + b_area - inter
    return inter / union if union > 0 else 0.0


def _nms_rects(rects, iou_threshold: float = 0.5):
    kept = []
    for rect in rects:
        if any(_bbox_iou(rect, existing) >= iou_threshold for existing in kept):
            continue
        kept.append(rect)
    return kept


def _image_to_ocr_boxes(image) -> list:
    if not TESSERACT_AVAILABLE or image is None:
        return []
    try:
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB) if cv2 else image
        data = pytesseract.image_to_data(
            rgb,
            output_type=pytesseract.Output.DICT,
            config="--oem 3 --psm 6",
        )
    except Exception:
        return []

    boxes = []
    n = len(data.get("text", []))
    for i in range(n):
        text = (data["text"][i] or "").strip()
        try:
            conf = float(data.get("conf", ["-1"])[i])
        except Exception:
            conf = -1.0
        if not text or conf < 35:
            continue
        x, y = int(data["left"][i]), int(data["top"][i])
        w, h = int(data["width"][i]), int(data["height"][i])
        if w < 3 or h < 3:
            continue
        boxes.append((x, y, x + w, y + h))
    return boxes


def _extract_figures_from_pdf_page(page: fitz.Page, page_num: int) -> list:
    figures = []
    raw = page.get_text("rawdict")
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)

    for idx, block in enumerate(raw.get("blocks", [])):
        if block.get("type") != 1:
            continue
        bbox = block.get("bbox")
        if not bbox or len(bbox) != 4:
            continue

        x0, y0, x1, y1 = bbox
        bw = max(0.0, x1 - x0)
        bh = max(0.0, y1 - y0)
        area = bw * bh

        # Skip very tiny embedded images (icons/noise).
        if area < 2_500:
            continue

        figures.append({
            "id": f"figure-p{page_num}-{idx + 1}",
            "page_num": page_num,
            "type": "figure",
            "bbox": _normalize_bbox((x0, y0, x1, y1), page_width, page_height),
            "width": int(round(bw)),
            "height": int(round(bh)),
            "source": "pdf_embedded_image",
            "preview_data_url": "",
        })

    # Generate lightweight preview images from the detected figure bbox.
    for figure in figures:
        bbox = figure.get("bbox", {})
        clip = fitz.Rect(
            float(bbox.get("x0", 0.0)) * page_width,
            float(bbox.get("y0", 0.0)) * page_height,
            float(bbox.get("x1", 1.0)) * page_width,
            float(bbox.get("y1", 1.0)) * page_height,
        )
        if clip.width < 2 or clip.height < 2:
            continue
        try:
            pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), clip=clip, alpha=False)
            figure["preview_data_url"] = _bytes_to_data_url(pix.tobytes("png"), "image/png")
        except Exception:
            figure["preview_data_url"] = ""

    return figures


def _extract_tables_from_image_bytes(image_bytes: bytes) -> list:
    if not cv2 or not np:
        return []

    image, w, h = _decode_image_to_bgr(image_bytes)
    if image is None:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    bw = cv2.adaptiveThreshold(
        ~gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,
        -10,
    )

    h, w = gray.shape
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 30), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 30)))

    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel)
    table_mask = cv2.add(horizontal, vertical)

    contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    candidate_rects = []
    image_area = max(1, w * h)

    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        if cw < 120 or ch < 60:
            continue
        if area / image_area > 0.75:
            continue
        if x <= 3 and y <= 3 and (x + cw) >= (w - 3) and (y + ch) >= (h - 3):
            continue
        candidate_rects.append((x, y, x + cw, y + ch))

    candidate_rects.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    rects = _nms_rects(candidate_rects, iou_threshold=0.5)
    tables = []

    for idx, rect in enumerate(rects, start=1):
        x, y, x1, y1 = rect
        cw = x1 - x
        ch = y1 - y
        crop = image[y:y + ch, x:x + cw]
        table_text = ""
        if TESSERACT_AVAILABLE:
            try:
                table_text = pytesseract.image_to_string(crop)
            except Exception:
                table_text = ""

        rows = []
        for line in (table_text or "").splitlines():
            cleaned = line.strip()
            if not cleaned:
                continue
            cells = [cell for cell in cleaned.replace("\t", "  ").split("  ") if cell.strip()]
            rows.append(cells if cells else [cleaned])

        joined = " ".join(" ".join(row) for row in rows).strip()
        alpha_num_count = sum(ch.isalnum() for ch in joined)
        if TESSERACT_AVAILABLE and alpha_num_count < 8:
            continue

        if TESSERACT_AVAILABLE and len(rows) < 2:
            continue

        tables.append({
            "page_num": 1,
            "data": rows if rows else [["Detected table region"]],
            "bbox": {
                "x0": round(x / max(1, w), 4),
                "y0": round(y / max(1, h), 4),
                "x1": round((x + cw) / max(1, w), 4),
                "y1": round((y + ch) / max(1, h), 4),
            },
        })

    if not tables and not TESSERACT_AVAILABLE:
        for rect in rects[:3]:
            x, y, x1, y1 = rect
            tables.append({
                "page_num": 1,
                "data": [["Detected table region (OCR unavailable)"]],
                "bbox": {
                    "x0": round(x / max(1, w), 4),
                    "y0": round(y / max(1, h), 4),
                    "x1": round(x1 / max(1, w), 4),
                    "y1": round(y1 / max(1, h), 4),
                },
            })

    return tables


def _extract_figures_from_image_bytes(image_bytes: bytes) -> list:
    if not cv2 or not np:
        return []

    image, w, h = _decode_image_to_bgr(image_bytes)
    if image is None:
        return []

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    image_area = max(1, w * h)

    bw = cv2.adaptiveThreshold(
        ~gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        15,
        -10,
    )
    horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(20, w // 30), 1))
    vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, h // 30)))
    horizontal = cv2.morphologyEx(bw, cv2.MORPH_OPEN, horizontal_kernel)
    vertical = cv2.morphologyEx(bw, cv2.MORPH_OPEN, vertical_kernel)
    table_mask = cv2.add(horizontal, vertical)
    non_table = cv2.bitwise_and(gray, gray, mask=cv2.bitwise_not(table_mask))

    edges = cv2.Canny(non_table, 60, 180)
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    h, w = gray.shape
    figures = []
    candidate_rects = []

    for contour in contours:
        x, y, cw, ch = cv2.boundingRect(contour)
        area = cw * ch
        area_ratio = area / image_area
        if area < 20_000:
            continue
        if cw < 120 or ch < 120:
            continue
        if area_ratio < 0.015:
            continue
        if area_ratio > 0.70:
            continue
        if x <= 3 and y <= 3 and (x + cw) >= (w - 3) and (y + ch) >= (h - 3):
            continue
        aspect = cw / max(1.0, ch)
        if aspect < 0.25 or aspect > 4.2:
            continue
        candidate_rects.append((x, y, x + cw, y + ch))

    candidate_rects.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    rects = _nms_rects(candidate_rects, iou_threshold=0.4)

    for rect in rects[:6]:
        x, y, x1, y1 = rect
        cw = x1 - x
        ch = y1 - y

        figures.append({
            "id": "",
            "page_num": 1,
            "type": "figure",
            "bbox": {
                "x0": round(x / max(1, w), 4),
                "y0": round(y / max(1, h), 4),
                "x1": round((x + cw) / max(1, w), 4),
                "y1": round((y + ch) / max(1, h), 4),
            },
            "width": cw,
            "height": ch,
            "source": "image_region",
            "preview_data_url": "",
        })

    top_figures = figures

    for seq, figure in enumerate(top_figures, start=1):
        figure["id"] = f"figure-p1-{seq}"
        bbox = figure.get("bbox", {})
        x0 = int(round(float(bbox.get("x0", 0.0)) * w))
        y0 = int(round(float(bbox.get("y0", 0.0)) * h))
        x1 = int(round(float(bbox.get("x1", 1.0)) * w))
        y1 = int(round(float(bbox.get("y1", 1.0)) * h))
        crop = image[max(0, y0):min(h, y1), max(0, x0):min(w, x1)]
        if crop.size == 0:
            continue
        try:
            ok, encoded = cv2.imencode(".png", crop)
            if ok:
                figure["preview_data_url"] = _bytes_to_data_url(encoded.tobytes(), "image/png")
        except Exception:
            figure["preview_data_url"] = ""

    return top_figures


def _process_pdf(file_content: bytes, job_id: str, filename: str, temp_path: str) -> dict:
    pages = []
    tables = []
    page_images = []
    figures = []

    with pdfplumber.open(temp_path) as pdf:
        for i, page in enumerate(pdf.pages):
            page_num = i + 1
            text = page.extract_text() or ""
            words = [
                {
                    "text": w["text"],
                    "x0": round(w["x0"] / page.width, 4),
                    "y0": round(w["top"] / page.height, 4),
                    "x1": round(w["x1"] / page.width, 4),
                    "y1": round(w["bottom"] / page.height, 4),
                }
                for w in page.extract_words()
            ]

            pages.append({
                "page_num": page_num,
                "text": text,
                "words": words,
                "char_count": len(text),
            })

            raw_tables = page.extract_tables() or []
            for table in raw_tables:
                tables.append({
                    "page_num": page_num,
                    "data": table,
                })

    doc = fitz.open(temp_path)
    try:
        for i in range(len(doc)):
            page_num = i + 1
            page = doc[i]
            pix = page.get_pixmap()
            page_images.append({
                "page_num": page_num,
                "width": pix.width,
                "height": pix.height,
            })

            if not pages[i]["text"].strip():
                pages[i]["text"] = _safe_ocr_text_from_pdf_page(page)
                pages[i]["char_count"] = len(pages[i]["text"])

            figures.extend(_extract_figures_from_pdf_page(page, page_num))
    finally:
        doc.close()

    return {
        "job_id": job_id,
        "status": "done",
        "filename": filename,
        "document_type": "pdf",
        "page_count": len(pages),
        "table_count": len(tables),
        "figure_count": len(figures),
        "pages": pages,
        "tables": tables,
        "figures": figures,
        "page_images": page_images,
    }


def _process_image(file_content: bytes, job_id: str, filename: str) -> dict:
    text = _safe_ocr_text_from_bytes(file_content)
    tables = _extract_tables_from_image_bytes(file_content)
    figures = _extract_figures_from_image_bytes(file_content)

    if not text and not TESSERACT_AVAILABLE:
        text = (
            "OCR text unavailable: system Tesseract is not installed. "
            "Install it with: brew install tesseract"
        )

    if Image:
        try:
            with Image.open(io.BytesIO(file_content)) as img:
                width, height = img.size
        except Exception:
            width, height = 0, 0
    else:
        width, height = 0, 0

    pages = [{
        "page_num": 1,
        "text": text,
        "words": [],
        "char_count": len(text),
    }]

    return {
        "job_id": job_id,
        "status": "done",
        "filename": filename,
        "document_type": "image",
        "page_count": 1,
        "table_count": len(tables),
        "figure_count": len(figures),
        "pages": pages,
        "tables": tables,
        "figures": figures,
        "page_images": [{"page_num": 1, "width": width, "height": height}],
    }


def process(file_content: bytes, job_id: str, filename: str, content_type: str = "") -> dict:
    """
    Main entry point for the Diagrams/Tables modality.
    Called by app.py when a document is uploaded.

    Args:
        file_content : raw bytes of the uploaded PDF
        job_id       : unique ID generated by app.py for this job
        filename     : original filename of the uploaded PDF

    Returns:
        dict with pages, tables, page_images, and mock annotations
    """

    is_pdf = (content_type or "").lower() == "application/pdf" or filename.lower().endswith(".pdf")

    suffix = ".pdf" if is_pdf else Path(filename).suffix or ".img"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp:
        temp_path = temp.name
        temp.write(file_content)

    try:
        if is_pdf:
            result = _process_pdf(file_content, job_id, filename, temp_path)
        else:
            result = _process_image(file_content, job_id, filename)

        # Mock annotations (placeholder for scoring model output).
        # Placeholder for real Gemini feedback — arrives in Milestone 2
        # Schema is identical to what the real Gemini service will return
        # so the frontend can be built against this now without waiting for keys
        mock_annotations = [
            {
                "id":           f"annotation-{job_id[:8]}-001",
                "page":         1,
                "bbox":         {
                    "x":      0.1,
                    "y":      0.2,
                    "width":  0.8,
                    "height": 0.05
                },
                "region_type":  "paragraph",
                "feedback":     "Good structure, but the argument needs more supporting evidence.",
                "confidence":   0.87,
                "needs_review": False,
            }
        ]

        result["annotations"] = mock_annotations
        return result

    finally:
        # Always delete the temp file even if something crashes above
        Path(temp_path).unlink(missing_ok=True)