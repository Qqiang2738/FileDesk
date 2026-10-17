"""Small, dependency-free reader for the cell values used by FileDesk's print reports.

This reads OpenXML, not pixel/layout content. It intentionally refuses workbook
features it cannot confidently reconstruct (notably uncached formulas).
"""
from __future__ import annotations

import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from .engine import FileDeskError

MAIN='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PKG='http://schemas.openxmlformats.org/package/2006/relationships'
NS={'m':MAIN}
MAX_UNCOMPRESSED=180*1024*1024
MAX_ENTRY=85*1024*1024
MAX_ENTRIES=1200


def col_index(label: str) -> int:
    number=0
    for char in label.upper():number=number*26+ord(char)-64
    return number


def cell_text(node) -> str:
    return ''.join(e.text or '' for e in node.iter(f'{{{MAIN}}}t'))


def read_workbook(path: Path, *, max_rows=12000, max_cols=128, max_cells=250000, max_sheets=8):
    try:
        with zipfile.ZipFile(path) as book:
            infos=book.infolist()
            if len(infos)>MAX_ENTRIES or sum(i.file_size for i in infos)>MAX_UNCOMPRESSED or any(i.file_size>MAX_ENTRY for i in infos):
                raise FileDeskError('Excel 文件结构过大，已为保护本机内存停止处理。')
            names=set(book.namelist())
            if 'xl/workbook.xml' not in names or 'xl/_rels/workbook.xml.rels' not in names:
                raise FileDeskError('不是有效的 XLSX 工作簿。')
            root=ET.fromstring(book.read('xl/workbook.xml'))
            rels=ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
            lookup={r.attrib['Id']:r.attrib.get('Target','') for r in rels if r.tag==f'{{{PKG}}}Relationship'}
            ss=[]
            if 'xl/sharedStrings.xml' in names:
                shared=ET.fromstring(book.read('xl/sharedStrings.xml'))
                ss=[cell_text(item) for item in shared.findall('m:si', NS)]
            fmt={}
            styles=[]
            if 'xl/styles.xml' in names:
                st=ET.fromstring(book.read('xl/styles.xml'))
                nums=st.find('m:numFmts',NS)
                if nums is not None:
                    fmt={int(n.attrib['numFmtId']):n.attrib.get('formatCode','') for n in nums}
                xfs=st.find('m:cellXfs',NS)
                if xfs is not None:
                    styles=[int(x.attrib.get('numFmtId','0')) for x in xfs]
            sheets=root.find('m:sheets',NS)
            if sheets is None:raise FileDeskError('Excel 文件没有工作表。')
            sheet_defs=list(sheets)
            if len(sheet_defs)>max_sheets:raise FileDeskError(f'当前最多处理 {max_sheets} 张工作表。')
            date_1904=(root.find('m:workbookPr',NS) is not None and root.find('m:workbookPr',NS).attrib.get('date1904') in ('1','true'))
            total=0;filled=0;outputs=[]
            for sh in sheet_defs:
                title=sh.attrib.get('name','未命名工作表')
                rid=sh.attrib.get(f'{{{REL}}}id')
                target=lookup.get(rid,'')
                if not target or '://' in target:
                    raise FileDeskError('Excel 内部工作表链接不可用。')
                name=posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl',target))
                if name not in names or not name.startswith('xl/worksheets/'):
                    raise FileDeskError('Excel 内部工作表文件异常。')
                doc=ET.fromstring(book.read(name))
                data=doc.find('m:sheetData',NS)
                if data is None:continue
                cells={};maxr=0;maxc=0
                for row in data.findall('m:row',NS):
                    for c in row.findall('m:c',NS):
                        ref=c.attrib.get('r','')
                        m=re.fullmatch(r'([A-Za-z]+)(\d+)',ref)
                        if not m:
                            continue
                        col=col_index(m.group(1));ri=int(m.group(2))
                        value=c.find('m:v',NS)
                        formula=c.find('m:f',NS)
                        typ=c.attrib.get('t','')
                        raw=value.text if value is not None else None
                        if formula is not None and raw is None and typ != 'inlineStr':
                            raise FileDeskError(f'工作表「{title}」的 {ref} 有未缓存的公式结果，请用 Excel/LibreOffice 重新保存后再转换。')
                        if typ=='inlineStr':
                            element=c.find('m:is',NS)
                            parsed=cell_text(element) if element is not None else ''
                        elif typ=='s':
                            idx=int(raw or '-1')
                            if not 0<=idx<len(ss):raise FileDeskError('Excel 字符串索引异常，无法准确转换。')
                            parsed=ss[idx]
                        elif typ=='b':
                            parsed=(raw=='1')
                        elif typ=='e':
                            raise FileDeskError(f'工作表「{title}」的 {ref} 含公式错误值，请先在 Excel 中修复。')
                        elif typ=='str':
                            parsed=raw or ''
                        elif raw is not None:
                            try:
                                f=float(raw)
                                parsed=int(f) if f.is_integer() else f
                                style_id=int(c.attrib.get('s','0'))
                                fmt_id=styles[style_id] if style_id<len(styles) else 0
                                format_code=fmt.get(fmt_id,'')
                                if re.fullmatch(r'0{2,}',format_code):
                                    parsed=str(int(f)).zfill(len(format_code))
                                elif date_1904 and fmt_id in (14,15,16,17,22):
                                    parsed=f+1462
                            except ValueError:
                                parsed=raw
                        else:
                            if formula is not None:
                                raise FileDeskError(f'工作表「{title}」的 {ref} 有未缓存的公式结果，请用 Excel/LibreOffice 重新保存后再转换。')
                            parsed=''
                        if parsed is not None and parsed!='':
                            if ri>max_rows or col>max_cols:
                                raise FileDeskError(f'工作表「{title}」的数据范围超出本机处理上限（{max_rows:,} 行 / {max_cols} 列），与文件 MB 大小无关；请按工作表或业务范围分批处理。')
                            filled+=1
                            if filled>max_cells:
                                raise FileDeskError(f'有效单元格超过本机安全上限（{max_cells:,} 个）。建议按工作表或业务范围分批处理。')
                            cells[(ri,col)]=parsed
                            maxr=max(maxr,ri);maxc=max(maxc,col)
                total+=maxr*maxc
                if total>1800000:
                    raise FileDeskError('工作表的行列跨度过大，建议清理 Excel 末尾多余格式或分表处理。')
                if maxr and maxc:
                    matrix=[[None for _ in range(maxc)] for _ in range(maxr)]
                    for (ri,col),value in cells.items():matrix[ri-1][col-1]=value
                    outputs.append((title,matrix))
            if not outputs:
                raise FileDeskError('工作簿中没有可以转换的数据。')
            return outputs
    except (zipfile.BadZipFile,ET.ParseError) as exc:
        raise FileDeskError('Excel 文件内部结构损坏，请检查原文件。') from exc
