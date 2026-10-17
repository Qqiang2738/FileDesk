"""Table-aware, fully local PDF -> editable Word reconstruction.

PDF has no standard document semantics. This exporter reconstructs detectable
ruled tables from their cell geometry and preserves other readable text as
paragraphs. It never advertises visual pixel fidelity or OCR capability.
"""
from __future__ import annotations

from pathlib import Path
import re

from .engine import FileDeskError


def _cell_text(page, rect) -> str:
    raw = page.get_textbox(rect).strip()
    # Hard-wrapped serial numbers should not acquire spaces or newlines.
    raw = re.sub(r'(?<=\d)\s*\n\s*(?=\d)', '', raw)
    raw = re.sub(r'[ \t]*\n[ \t]*', ' ', raw)
    return re.sub(r'[ \t]{2,}', ' ', raw).strip()


def pdf_tables_to_docx(source: Path, output: Path) -> Path:
    try:
        import pymupdf
        from docx import Document
        from docx.shared import Pt
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
        from docx.enum.text import WD_BREAK
        from docx.oxml import OxmlElement
        from docx.oxml.ns import qn
    except ImportError as exc:
        raise FileDeskError('PDF 表格转换引擎不完整。请重新执行 start-mac.command 安装依赖。') from exc

    pdf = None
    try:
        pdf = pymupdf.open(str(source))
        if pdf.needs_pass:
            raise FileDeskError('PDF 已加密，请先解锁。')
        if len(pdf) < 1 or len(pdf) > 150:
            raise FileDeskError('可编辑重建支持 1–150 页的 PDF。')
        doc = Document()
        section = doc.sections[0]
        # Keep the page geometry whenever all pages share the same orientation.
        first = pdf[0]
        section.page_width = Pt(first.rect.width)
        section.page_height = Pt(first.rect.height)
        section.left_margin = Pt(27)
        section.right_margin = Pt(27)
        section.top_margin = Pt(26)
        section.bottom_margin = Pt(28)
        normal = doc.styles['Normal']
        normal.font.name = 'Arial'
        normal.font.size = Pt(8.5)
        normal.paragraph_format.space_after = Pt(3)
        normal.paragraph_format.line_spacing = 1.06
        real_text = False
        any_table = False

        for page_index, page in enumerate(pdf):
            if page_index:
                paragraph = doc.add_paragraph()
                paragraph.add_run().add_break(WD_BREAK.PAGE)
            # PyMuPDF's finder uses drawn grid lines, not guessed whitespace.
            # Missing or scanned table grids remain a documented limitation.
            candidates = page.find_tables().tables
            candidates = sorted((table for table in candidates if
                                 table.row_count >= 2 and table.col_count >= 2),
                                key=lambda table: table.bbox[1])
            rects = [pymupdf.Rect(table.bbox) for table in candidates]
            elements = []
            for table in candidates:
                elements.append((table.bbox[1], 'table', table))
            # Extract non-table text by line geometry; do not duplicate table
            # content through page.extract_text or inflate the Word page count.
            for block in page.get_text('dict')['blocks']:
                if 'lines' not in block:
                    continue
                for line in block['lines']:
                    line_box = pymupdf.Rect(line['bbox'])
                    center = (line_box.x0+line_box.x1)/2, (line_box.y0+line_box.y1)/2
                    if any(area.contains(pymupdf.Point(center)) for area in rects):
                        continue
                    if line_box.y0 > page.rect.height - 35:
                        # Repeated PDF footer is not document body.
                        continue
                    content = ''.join(span.get('text','') for span in line['spans']).strip()
                    if content:
                        size = max((span.get('size', 8.5) for span in line['spans']),default=8.5)
                        elements.append((line_box.y0, 'line', (content, size)))
            elements.sort(key=lambda item: item[0])
            for _, kind, value in elements:
                if kind == 'line':
                    content, size = value
                    para=doc.add_paragraph()
                    r=para.add_run(content)
                    r.font.size=Pt(min(15,max(8,size*0.95)))
                    if size >= 13:
                        r.bold = True
                        para.paragraph_format.space_after=Pt(5)
                    real_text = True
                    continue
                table=value
                any_table=True
                t=doc.add_table(rows=table.row_count, cols=table.col_count)
                t.style='Table Grid'
                t.alignment=WD_TABLE_ALIGNMENT.CENTER
                t.autofit=False
                available=float(section.page_width.pt-section.left_margin.pt-section.right_margin.pt)
                raw_width=max(1,float(table.bbox[2]-table.bbox[0]))
                widths=[]
                for col in range(table.col_count):
                    row_box=next((row.cells[col] for row in table.rows if row.cells[col]),None)
                    widths.append((row_box[2]-row_box[0]) if row_box else raw_width/table.col_count)
                total=max(1,sum(widths))
                # Prevent tiny columns when a PDF has inaccurate geometry.
                normalized=[available*(w/total) for w in widths]
                for c,width in enumerate(normalized):
                    t.columns[c].width=Pt(width)
                for ri,row in enumerate(table.rows):
                    for ci,rect in enumerate(row.cells):
                        cell=t.cell(ri,ci)
                        cell.width=Pt(normalized[ci])
                        cell.vertical_alignment=WD_CELL_VERTICAL_ALIGNMENT.CENTER
                        txt=_cell_text(page,pymupdf.Rect(rect)) if rect else ''
                        # Fix digit groups split by damaged PDF font encoding only in
                        # code/id columns. Never remove spacing from free text.
                        key = ''
                        if table.col_count >= 5 and table.row_count > 1:
                            key = _cell_text(page, pymupdf.Rect(table.rows[0].cells[ci])) if table.rows[0].cells[ci] else ''
                        elif ci % 2 == 1 and row.cells[ci-1]:
                            key = _cell_text(page, pymupdf.Rect(row.cells[ci-1]))
                        if any(label in key for label in ('清单编号','产品编号','材料编号','订单编号')):
                            txt = re.sub(r'(?<=\d) (?=\d)', '', txt)
                        cell.text=txt
                        real_text|=bool(txt)
                        for para in cell.paragraphs:
                            para.paragraph_format.space_after=Pt(0)
                            for run in para.runs:
                                run.font.size=Pt(8.4 if table.col_count >= 6 else 9.0)
                                run.bold=ri==0 and table.col_count >= 5
                                if ri==0 and table.col_count >=5:
                                    run.font.color.rgb=__import__('docx').shared.RGBColor(255,255,255)
                        # Quiet borders and contextual field-label background.
                        tcpr=cell._tc.get_or_add_tcPr()
                        borders=tcpr.find(qn('w:tcBorders'))
                        if borders is None:
                            borders=OxmlElement('w:tcBorders');tcpr.append(borders)
                        for edge in ('top','bottom','left','right'):
                            side=borders.find(qn('w:'+edge))
                            if side is None:
                                side=OxmlElement('w:'+edge);borders.append(side)
                            side.set(qn('w:val'),'single')
                            side.set(qn('w:sz'),'4')
                            side.set(qn('w:color'),'D5E3D9')
                        shade = ('315B47' if ri==0 and table.col_count >=5 else
                                 'F0F5F1' if table.col_count==4 and ci in (0,2) else None)
                        if shade:
                            shd=OxmlElement('w:shd');shd.set(qn('w:fill'),shade);tcpr.append(shd)
                if table.col_count >=5 and table.row_count > 1:
                    # Repeat headers only for actual tabular data, not 4-column
                    # source key/value summaries whose first row isn't a header.
                    trpr=t.rows[0]._tr.get_or_add_trPr()
                    trpr.append(OxmlElement('w:tblHeader'))
                doc.add_paragraph().paragraph_format.space_after=Pt(0)

        if not real_text:
            raise FileDeskError('该 PDF 没有可读取文字；扫描件需先进行 OCR。')
        output.parent.mkdir(parents=True,exist_ok=True)
        doc.save(output)
        return output
    except FileDeskError:
        raise
    except Exception as exc:
        raise FileDeskError('PDF 表格重建失败。请尝试文本模式，或上传原始 Excel / Word 文件。') from exc
    finally:
        if pdf is not None:
            pdf.close()
