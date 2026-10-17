"""Bounded, row-streaming CSV/XLSX reader for FileDesk large table jobs.

Sheet XML is parsed incrementally; no worksheet-sized list/dict is created.
Limits are explicit to keep a local process from exhausting memory/disk.
"""
from __future__ import annotations

import csv
import posixpath
import re
import xml.etree.ElementTree as ET
import zipfile
from contextlib import contextmanager
from pathlib import Path

from .engine import FileDeskError
from .xlsx_reader import MAIN, REL, PKG, NS, cell_text, col_index

MAX_ROWS = 50000
MAX_COLS = 128
MAX_CELLS = 2500000
MAX_SHEETS = 8
MAX_EXPANDED = 768 * 1024 * 1024
MAX_ENTRY = 600 * 1024 * 1024


def _xlsx_sheet_rows(book, member, strings, styles, formats, date_1904):
    with book.open(member) as fh:
        it = ET.iterparse(fh, events=('start', 'end'))
        _, root = next(it)
        for event, elem in it:
            if event != 'end' or elem.tag != f'{{{MAIN}}}row':
                continue
            line = int(elem.attrib.get('r', '0'))
            values = {}
            for c in elem.findall('m:c', NS):
                ref = c.attrib.get('r', '')
                m = re.fullmatch(r'([A-Za-z]+)(\d+)', ref)
                if not m:
                    continue
                col = col_index(m.group(1))
                typ = c.attrib.get('t', '')
                raw_node = c.find('m:v', NS)
                raw = raw_node.text if raw_node is not None else None
                formula = c.find('m:f', NS)
                if formula is not None and raw is None and typ != 'inlineStr':
                    raise FileDeskError(f'单元格 {ref} 的公式没有缓存计算结果，请在 Excel 中重新保存。')
                if typ == 'inlineStr':
                    node = c.find('m:is', NS)
                    value = cell_text(node) if node is not None else ''
                elif typ == 's':
                    try:
                        value = strings[int(raw)]
                    except (ValueError, IndexError, TypeError) as exc:
                        raise FileDeskError(f'单元格 {ref} 的字符串索引错误。') from exc
                elif typ == 'b':
                    value = raw == '1'
                elif typ == 'e':
                    raise FileDeskError(f'单元格 {ref} 有公式错误，请先修复原文件。')
                elif typ == 'str':
                    value = raw or ''
                elif raw is not None:
                    try:
                        f = float(raw)
                        value = int(f) if f.is_integer() else f
                        si = int(c.attrib.get('s', '0'))
                        fmt_id = styles[si] if si < len(styles) else 0
                        fmt_code = formats.get(fmt_id, '')
                        if re.fullmatch(r'0{2,}', fmt_code):
                            value = str(int(f)).zfill(len(fmt_code))
                        elif date_1904 and fmt_id in (14, 15, 16, 17, 22):
                            value = f + 1462
                    except ValueError:
                        value = raw
                else:
                    value = ''
                if value is not None and value != '':
                    if col > MAX_COLS or line > MAX_ROWS:
                        raise FileDeskError(f'超大表格单表最多处理 {MAX_ROWS:,} 行 / {MAX_COLS} 列；可按业务范围拆分。')
                    values[col - 1] = value
            if values:
                yield line, values
            elem.clear()
            root.clear()


def _shared_strings(book):
    if 'xl/sharedStrings.xml' not in book.namelist():
        return []
    strings = []
    with book.open('xl/sharedStrings.xml') as stream:
        it = ET.iterparse(stream, events=('start', 'end'))
        _, root = next(it)
        for event, elem in it:
            if event == 'end' and elem.tag == f'{{{MAIN}}}si':
                strings.append(cell_text(elem))
                elem.clear()
                root.clear()
    return strings


@contextmanager
def sheets(path: Path):
    """Yield (name, iterator of (original row number, {zero-indexed col: value}))."""
    if path.suffix.lower() == '.csv':
        stream = None
        try:
            for encoding in ('utf-8-sig', 'utf-16', 'gb18030'):
                try:
                    handle = path.open('r', encoding=encoding, newline='')
                    sample = handle.read(32768)
                    handle.seek(0)
                    if '\x00' in sample:
                        handle.close()
                        continue
                    stream = handle
                    break
                except UnicodeError:
                    handle.close()
            if stream is None:
                raise FileDeskError('CSV 编码无法识别，请另存为 UTF-8 或 GB18030。')
            try:
                dialect = csv.Sniffer().sniff(sample, delimiters=',;\t|')
            except csv.Error:
                dialect = csv.excel
            def rows():
                count = 0
                for n, raw in enumerate(csv.reader(stream, dialect), 1):
                    count += 1
                    if n > MAX_ROWS:
                        raise FileDeskError(f'CSV 超过 {MAX_ROWS:,} 行，请分批处理。')
                    if len(raw) > MAX_COLS:
                        raise FileDeskError(f'CSV 超过 {MAX_COLS} 列，请分批处理。')
                    yield n, {i: v for i, v in enumerate(raw) if v}
            yield [('CSV 数据', rows())]
        finally:
            if stream:
                stream.close()
        return
    try:
        with zipfile.ZipFile(path) as book:
            entries = book.infolist()
            if len(entries) > 4000 or sum(e.file_size for e in entries) > MAX_EXPANDED or any(e.file_size > MAX_ENTRY for e in entries):
                raise FileDeskError('工作簿解压体积超过本机安全范围（768 MB），请按工作表分批处理。')
            names = set(book.namelist())
            if 'xl/workbook.xml' not in names or 'xl/_rels/workbook.xml.rels' not in names:
                raise FileDeskError('不是有效的 XLSX 文件。')
            root = ET.fromstring(book.read('xl/workbook.xml'))
            relations = ET.fromstring(book.read('xl/_rels/workbook.xml.rels'))
            lookup = {r.attrib['Id']: r.attrib.get('Target', '') for r in relations if r.tag == f'{{{PKG}}}Relationship'}
            sheet_root = root.find('m:sheets', NS)
            if sheet_root is None or not list(sheet_root):
                raise FileDeskError('工作簿没有工作表。')
            if len(sheet_root) > MAX_SHEETS:
                raise FileDeskError(f'一次最多处理 {MAX_SHEETS} 张工作表。')
            strings = _shared_strings(book)
            fmts = {}
            styles = []
            if 'xl/styles.xml' in names:
                st = ET.fromstring(book.read('xl/styles.xml'))
                formats = st.find('m:numFmts', NS)
                if formats is not None:
                    fmts = {int(x.attrib['numFmtId']): x.attrib.get('formatCode', '') for x in formats}
                xfs = st.find('m:cellXfs', NS)
                if xfs is not None:
                    styles = [int(x.attrib.get('numFmtId', 0)) for x in xfs]
            prop = root.find('m:workbookPr', NS)
            date_1904 = prop is not None and prop.attrib.get('date1904') in ('1', 'true')
            found = []
            for sh in sheet_root:
                name = sh.attrib.get('name', '未命名工作表')
                target = lookup.get(sh.attrib.get(f'{{{REL}}}id'), '')
                if not target or '://' in target:
                    raise FileDeskError('工作表链接无效。')
                member = posixpath.normpath(target.lstrip('/') if target.startswith('/') else posixpath.join('xl', target))
                if member not in names or not member.startswith('xl/worksheets/'):
                    raise FileDeskError('工作表路径无效。')
                found.append((name, _xlsx_sheet_rows(book, member, strings, styles, fmts, date_1904)))
            yield found
    except (zipfile.BadZipFile, ET.ParseError) as exc:
        raise FileDeskError('表格文件结构损坏，无法安全读取。') from exc
