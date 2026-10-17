"""Reliable, fully local, Chinese-capable PDF export from structured DOCX.

Use when LibreOffice PDF output is corrupted, or for FileDesk's structured Excel
reports.  Content is reflowed, NOT an exact reproduction of arbitrary DOCX page
layout. All text is searchable; CJK glyphs are embedded in the resulting PDF.

The CJK font is provided by the installed PyMuPDF package and never extracted
into the project folder or distributed as a separate font file.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import re

from .engine import FileDeskError


def readable_docx_to_pdf(source: Path, output: Path) -> Path:
    try:
        import pymupdf
        from docx import Document
        from docx.table import Table as WordTable
        from docx.text.paragraph import Paragraph as WordParagraph
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.lib.colors import HexColor
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.platypus import (
            BaseDocTemplate, Frame, PageTemplate, Paragraph, LongTable, TableStyle,
            PageBreak, Spacer, Image as FlowImage,
        )
    except ImportError as exc:
        raise FileDeskError('可读排版引擎未安装完整，请重新运行 start-mac.command 安装项目依赖。') from exc

    source=Path(source); output=Path(output)
    if source.suffix.lower() != '.docx':
        raise FileDeskError('备用排版目前仅支持 .docx。请先将旧版 Word 保存为 .docx。')
    try:
        doc=Document(source)
    except Exception as exc:
        raise FileDeskError('Word 文件无法读取，不能生成可读排版 PDF。') from exc

    # Native .docx charts/SmartArt/embedded objects cannot be preserved by a
    # semantic exporter. Reject instead of silently discarding important data.
    if doc.element.body.xpath('.//*[local-name()="chart" or local-name()="graphicData"]'):
        known_graphics = doc.element.body.xpath('.//*[local-name()="graphicData"]')
        if any('chart' in (node.get('uri') or '').lower() or
               any('diagram' in (node.get('uri') or '').lower() for node in known_graphics)):
            raise FileDeskError('原 Word 含图表或 SmartArt，备用可读排版无法保证保留它们；请用 Word 自带的“导出为 PDF”。')
    if doc.element.body.xpath('.//*[local-name()="tc"]//*[local-name()="blip"]'):
        raise FileDeskError('Word 表格内有图片，备用排版无法保证图片和单元格关系完整；请用 Word 自带的“导出为 PDF”。')
    if doc.element.body.xpath('.//*[local-name()="txbxContent"]'):
        raise FileDeskError('原 Word 含文本框，备用可读排版可能丢失内容；请使用 Word 自带的“导出为 PDF”。')

    font_name='FileDeskCJK'
    if font_name not in pdfmetrics.getRegisteredFontNames():
        font=pymupdf.Font('cjk')   # PyMuPDF's bundled multilingual font.
        pdfmetrics.registerFont(TTFont(font_name, BytesIO(font.buffer)))

    section=doc.sections[0]
    width=float(section.page_width.pt) if section.page_width else 842
    height=float(section.page_height.pt) if section.page_height else 595
    # Prevent pathological custom Word margins from making an unusable frame.
    left=max(32,min(54,float(section.left_margin.pt or 40)))
    right=max(32,min(54,float(section.right_margin.pt or 40)))
    top=max(34,min(58,float(section.top_margin.pt or 46)))
    bottom=max(42,min(62,float(section.bottom_margin.pt or 46)))
    usable=width-left-right
    if usable<220 or height-top-bottom<200:
        width,height,left,right,top,bottom=842,595,42,42,48,48
        usable=width-left-right
    ink=HexColor('#24372D'); green=HexColor('#295946')
    subtle=HexColor('#E6ECE8')

    class FileDeskTemplate(BaseDocTemplate):
        pass

    output.parent.mkdir(parents=True, exist_ok=True)
    template=FileDeskTemplate(str(output),pagesize=(width,height),leftMargin=left,
                              rightMargin=right,topMargin=top,bottomMargin=bottom,
                              pageCompression=1,title=source.stem)
    frame=Frame(left,bottom,usable,height-top-bottom,leftPadding=0,rightPadding=0,
                topPadding=0,bottomPadding=0,id='body')

    def decoration(canvas, doc_template):
        canvas.saveState()
        canvas.setStrokeColor(subtle); canvas.setLineWidth(.35)
        canvas.line(left,bottom-11,width-right,bottom-11)
        canvas.setFillColor(HexColor('#66786F'))
        canvas.setFont(font_name,8)
        canvas.drawRightString(width-right,bottom-23,f'{doc_template.page}')
        canvas.restoreState()

    template.addPageTemplates(PageTemplate(id='main',frames=[frame],onPage=decoration))

    base=ParagraphStyle('filedesk_base',fontName=font_name,fontSize=9.5,
                        leading=14.5,textColor=ink,spaceAfter=6,wordWrap='CJK')
    title=ParagraphStyle('filedesk_title',parent=base,fontSize=17,leading=23,
                         textColor=green,spaceBefore=4,spaceAfter=10)
    header=ParagraphStyle('filedesk_header',parent=base,fontSize=11.5,leading=17,
                          textColor=green,spaceBefore=9,spaceAfter=7)
    cell_style=ParagraphStyle('filedesk_cell',parent=base,fontSize=8.2,leading=12,
                              spaceAfter=0,wordWrap='CJK')
    story=[]
    seen_text=False

    def para_text(text:str) -> str:
        # ReportLab accepts escaped inline markup. Preserve actual line breaks.
        clean=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text or '')
        return escape(clean).replace('\n','<br/>')

    def inline_image(run):
        # Extract ordinary inline pictures without carrying over risky/external
        # links. Floating images are not supported and are rejected below.
        for blip in run._r.xpath('.//*[local-name()="blip"]'):
            rid=blip.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
            if not rid or rid not in doc.part.related_parts:
                continue
            blob=doc.part.related_parts[rid].blob
            try:
                img=FlowImage(BytesIO(blob))
                scale=min(1,usable/max(float(img.drawWidth),1),240/max(float(img.drawHeight),1))
                img.drawWidth*=scale;img.drawHeight*=scale
                story.append(img);story.append(Spacer(1,5))
            except Exception as exc:
                raise FileDeskError('Word 包含无法读取的图片，已停止备用重排，避免丢失内容。') from exc

    for item in doc.iter_inner_content():
        if isinstance(item,WordParagraph):
            # Paragraph-level page breaks from generated smart-Excel reports.
            breaks=item._p.xpath('.//*[local-name()="br" and @*[local-name()="type"]="page"]')
            if breaks:
                story.append(PageBreak())
            if item.text.strip():
                style_name=(item.style.name or '').lower() if item.style else ''
                selected=(title if 'title' in style_name or '标题' in style_name else
                          header if 'heading' in style_name or '标题' in style_name else base)
                if item.text.startswith(('来源数据','明细  /','明细 /','文序  /')):
                    selected=header
                story.append(Paragraph(para_text(item.text),selected))
                seen_text=True
            for run in item.runs:
                inline_image(run)
        elif isinstance(item,WordTable):
            rows=[]
            for row in item.rows:
                cells=[]
                for cell in row.cells:
                    text=cell.text or ''
                    cells.append(Paragraph(para_text(text),cell_style))
                    if text.strip(): seen_text=True
                rows.append(cells)
            if not rows: continue
            count=len(rows[0])
            # Prefer source column proportions; normalize to the available
            # page width without clipping or spilling off the paper.
            spans=[]
            for i in range(count):
                raw=item.columns[i].width.pt if i<len(item.columns) and item.columns[i].width else None
                spans.append(max(16,float(raw)) if raw else 1.0)
            total=sum(spans)
            widths=[usable*x/total for x in spans]
            grid=LongTable(rows,colWidths=widths,repeatRows=1 if len(rows)>1 else 0,
                           hAlign='LEFT',splitByRow=1,splitInRow=1)
            commands=[('VALIGN',(0,0),(-1,-1),'TOP'),
                      ('LEFTPADDING',(0,0),(-1,-1),6),
                      ('RIGHTPADDING',(0,0),(-1,-1),6),
                      ('TOPPADDING',(0,0),(-1,-1),5),
                      ('BOTTOMPADDING',(0,0),(-1,-1),5),
                      ('GRID',(0,0),(-1,-1),.30,subtle)]
            if len(rows)>1:
                commands.extend([('BACKGROUND',(0,0),(-1,0),HexColor('#E4EEE8')),
                                 ('ROWBACKGROUNDS',(0,1),(-1,-1),
                                  [HexColor('#FFFFFF'),HexColor('#F7FAF8')])])
            grid.setStyle(TableStyle(commands))
            story.append(grid);story.append(Spacer(1,9))
    # Preserve ordinary header/footer text, at document end in reflow mode.
    for sec in doc.sections:
        for region in (sec.header, sec.footer):
            for para in region.paragraphs:
                if para.text.strip():
                    story.append(Paragraph(para_text(para.text),base))
                    seen_text=True
    # Reject shape data that did not produce any flowable representation.
    if not seen_text and not story:
        raise FileDeskError('Word 没有可导出的正文或表格，备用排版不适用于该文件。')
    try:
        template.build(story)
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise FileDeskError('可读排版 PDF 生成失败，请尝试缩小表格或使用 Word 导出 PDF。') from exc
    if not output.is_file() or output.stat().st_size < 1000:
        raise FileDeskError('可读排版没有生成有效 PDF。')
    return output
