from __future__ import annotations

from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET

from docx import Document as DocxDocument
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter


def extract_pptx_text(path: Path) -> str:
    """Extract text from PowerPoint presentations (.pptx) natively."""
    slides_text: list[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            slide_names = sorted(
                [name for name in z.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")],
                key=lambda x: int("".join(filter(str.isdigit, Path(x).stem)) or 0)
            )
            for idx, slide_name in enumerate(slide_names, 1):
                xml_content = z.read(slide_name)
                tree = ET.fromstring(xml_content)
                # Find all a:t elements in drawingML
                texts = [
                    node.text.strip()
                    for node in tree.iter()
                    if node.tag.endswith("}t") and node.text and node.text.strip()
                ]
                if texts:
                    slides_text.append(f"--- Slide {idx} ---\n" + "\n".join(texts))
    except Exception as exc:
        raise ValueError(f"Could not parse PowerPoint file: {exc}")
    return "\n\n".join(slides_text)


import logging
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


def _extract_pdf_with_ocr(path: Path, max_pages: int = 40) -> str:
    """Fallback OCR for scanned, handwritten, or vectorized PDFs with 0 embedded text."""
    try:
        import fitz
    except ImportError:
        logger.warning("fitz (PyMuPDF) not available for PDF OCR")
        return ""

    ocr_bin = Path(__file__).resolve().parents[2] / "ocr_tool"
    if not ocr_bin.exists():
        logger.warning(f"Native OCR binary not found at {ocr_bin}")
        return ""

    logger.info(f"Initiating automatic native OCR on scanned/vectorized PDF: {path.name}")
    try:
        doc = fitz.open(str(path))
        total_pages = len(doc)
        pages_to_process = min(total_pages, max_pages)

        def process_page(idx: int):
            try:
                page = doc[idx]
                pix = page.get_pixmap(dpi=120)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                    tmp_path = Path(f.name)
                pix.save(str(tmp_path))
                res = subprocess.run([str(ocr_bin), str(tmp_path)], capture_output=True, text=True, timeout=20)
                text = res.stdout.strip()
                tmp_path.unlink(missing_ok=True)
                if text:
                    return idx + 1, f"--- Page {idx + 1} ---\n{text}"
            except Exception as e:
                logger.warning(f"OCR failed on page {idx + 1}: {e}")
            return idx + 1, ""

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(process_page, range(pages_to_process)))

        results.sort(key=lambda x: x[0])
        extracted_pages = [txt for _, txt in results if txt]
        logger.info(f"OCR completed: extracted text from {len(extracted_pages)}/{pages_to_process} pages")
        return "\n\n".join(extracted_pages)
    except Exception as exc:
        logger.error(f"Error during PDF OCR: {exc}", exc_info=True)
        return ""


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        # 1. Try PyMuPDF (fitz) for high performance digital text extraction
        try:
            import fitz
            doc = fitz.open(str(path))
            pages = []
            for idx in range(len(doc)):
                t = doc[idx].get_text() or ""
                if t.strip():
                    pages.append(f"--- Page {idx + 1} ---\n{t.strip()}")
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass

        # 2. Try pypdf fallback
        try:
            reader = PdfReader(str(path))
            pages = []
            for idx, page in enumerate(reader.pages, 1):
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(f"--- Page {idx} ---\n{page_text.strip()}")
            if pages:
                return "\n\n".join(pages)
        except Exception:
            pass

        # 3. If no digital text found (e.g. scanned/handwritten notes), use native OCR
        ocr_text = _extract_pdf_with_ocr(path)
        if ocr_text.strip():
            return ocr_text

        raise ValueError("No text could be extracted from the file (file is empty or unreadable)")

    if suffix == ".docx":
        doc = DocxDocument(str(path))
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs)

    if suffix == ".pptx":
        return extract_pptx_text(path)

    if suffix in {".txt", ".md", ".text"}:
        return path.read_text(encoding="utf-8", errors="ignore")

    raise ValueError(f"Unsupported file type: {suffix}")



def chunk_text(text: str, chunk_size: int = 900, overlap: int = 150) -> list[str]:
    cleaned = text.strip()
    if not cleaned:
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n---", "\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_text(cleaned)
    return [c.strip() for c in chunks if c.strip()]

