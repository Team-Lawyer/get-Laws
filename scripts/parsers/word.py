import logging
import re
from pathlib import Path
from typing import List, Tuple

from common import LINE_RE
from docx import Document
from docx.document import Document as _Document
from docx.oxml import CT_SectPr
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import Table, _Cell, _Row
from docx.text.paragraph import Paragraph
from parsers.base import Parser

logger = logging.getLogger(__name__)

# 检查是否匹配正则化开头
def isStartLine(line: str):
    for reg in LINE_RE:
        if re.match(reg, line):
            return True
    return False


class WordParser(Parser):
    def __init__(self) -> None:
        super().__init__("WORD")

    def iter_block_items(self, parent):
        """
        Generate a reference to each paragraph and table child within *parent*,
        in document order. Each returned value is an instance of either Table or
        Paragraph. *parent* would most commonly be a reference to a main
        Document object, but also works for a _Cell object, which itself can
        contain paragraphs and tables.
        """
        # 便利文档中所有段落与表格 行 列
        if isinstance(parent, _Document):
            parent_elm = parent.element.body
        elif isinstance(parent, _Cell):
            parent_elm = parent._tc
        elif isinstance(parent, _Row):
            parent_elm = parent._tr
        else:
            raise ValueError(f"something's not right {parent} {type(parent)}")
        # 段落 表格
        for child in parent_elm.iterchildren():
            if isinstance(child, CT_P):
                yield Paragraph(child, parent)
            elif isinstance(child, CT_Tbl):
                yield Table(child, parent)

    def parse(self, result, detail) -> Tuple[str, str, List[str]]:
        # 层级 标题 提取
        level = result["level"].strip()
        title = result["title"].strip()
        document = self.request.get_word(detail["path"], Path(level) / title)
        # 文件不存在返回
        if not document:
            logger.warning(f"document {detail['path']} not exists")
            return

        return self.parse_document(document, title)

    def parse_document(self, document, title):

        if not isinstance(document, _Document):
            with open(document, "rb") as f:
                document = Document(f)

        if not isinstance(document, _Document):
            raise Exception("document is not a _Document")

        desc = ""
        content = []
        content_fonts = []
        isDesc = False

        lines = list(filter(lambda x: x, self.iter_block_items(document)))

        def write_row(row):
            arr = ["| "]
            for cell in row.cells:
                text = "\n".join([p.text for p in cell.paragraphs])
                arr.append(f"{text}  |")
            content.append("".join(arr))
            return len(arr) - 1
        dia = False
        hasDesc = False
        prev_font = None
        prev_style = None
        for n, line in enumerate(lines):

            if isinstance(line, Table):
                content.append("<!-- TABLE -->")
                table = line

                size = write_row(table.rows[0])
                content.append("".join(["|"] + ["-----|"] * size))

                """
                | Item         | Price     | # In stock |
                |--------------|-----------|------------|
                | Juicy Apples | 1.99      | *7*        |
                | Bananas      | **1.89**  | 5234       |
                """

                for row in table.rows[1:]:
                    write_row(row)
                content.append("<!-- TABLE END -->")
                continue
            if isinstance(line, Paragraph):
                line = line.text.strip()
            line = re.sub(r"\u3000+", "\u3000", line)
            # print(line)

            # 信息行
            if re.match(r"[（\(]\d{4,4}年\d{1,2}月\d{1,2}日", line):
                isDesc = True
                hasDesc = True

            if isDesc:
                desc += line
            elif n > 0 and not re.match(r"^目\s*录\s*$", line) and dia == False:
                content.append(line)

            elif n > 0 and re.match(r"^目\s*录\s*$", line):
                dia = True
                # print(line)
                content.append(line)
            elif n > 0 and dia == True and line not in content:
                # print("当前行: ",line)
                content.append(line)
            elif n > 0 and dia == True and line in content and line != '':
                # print("在内的当前行: ",line)
                # print(content)
                index = content.index(line)
                # print(index)
                content = content[:index - 1]
                content.append(line)
                dia = False

            # 信息行结束
            if isDesc and re.search("[）\)]$", line):
                isDesc = False
            if isDesc and re.search(r"目.*录", line):
                isDesc = False
            if isDesc and isStartLine(line):
                isDesc = False

            if not hasDesc and re.search("^法释", line):
                hasDesc = True

        return title, desc, content
            # 加粗
            #     if isinstance(line, Paragraph):
            #         line = line.text.strip()
            #         is_bold = any(run.bold for run in line.runs)
            #     else:
            #         line = str(line).strip()
            #         is_bold = False
            #
            #     line = re.sub(r"\u3000+", "\u3000", line)
            #     # print(line)
            #
            #     # 信息行
            #     if re.match(r"[（\(]\d{4,4}年\d{1,2}月\d{1,2}日", line):
            #         isDesc = True
            #         hasDesc = True
            #
            #     if isDesc:
            #         desc += line
            #     elif n > 0 and not re.match(r"^目\s*录\s*$", line) and dia == False:
            #         content.append(line)
            #         content_bolds.append(is_bold)
            #     elif n > 0 and re.match(r"^目\s*录\s*$", line):
            #         dia = True
            #         #print(line)
            #         content.append(line)
            #         content_bolds.append(is_bold)
            #     elif n > 0 and dia == True and line not in content:
            #         # print("当前行: ",line)
            #         content.append(line)
            #         content_bolds.append(is_bold)
            #     elif n > 0 and dia == True and line in content and line != '':
            #         # print("在内的当前行: ",line)
            #         # print(content)
            #         index = content.index(line)
            #         # print(index)
            #         content = content[:index-1]
            #         content_bolds = content_bolds[:index - 1]
            #         content.append(line)
            #         content_bolds.append(is_bold)
            #         dia = False
            #
            #
            #     # 信息行结束
            #     if isDesc and re.search("[）\)]$", line):
            #         isDesc = False
            #     if isDesc and re.search(r"目.*录", line):
            #         isDesc = False
            #     if isDesc and isStartLine(line):
            #         isDesc = False
            #
            #     if not hasDesc and re.search("^法释", line):
            #         hasDesc = True
            #
            # return title, desc, content, content_bolds


            # 字体不一样
            # if isinstance(line, Paragraph):
            #     text = line.text.strip()
            #     if not text:
            #         continue
            #
            #     # 提取字体
            #     font_names = [run.font.name for run in line.runs if run.font.name]
            #     curr_font = font_names[0] if font_names else prev_font
            #
            #     # 提取样式
            #     curr_style = line.style.name if line.style else prev_style
            #
            #     # 如果字体或样式有任何一个不同就标 True
            #     is_diff_font = (curr_font != prev_font) or (curr_style != prev_style)
            #
            #     # 更新
            #     prev_font = curr_font
            #     prev_style = curr_style
            #
            # else:
            #     text = str(line).strip()
            #     if not text:
            #         continue
            #     is_diff_font = False

        #     text = re.sub(r"\u3000+", "\u3000", text).rstrip("\n")
        #
        #     # 信息行
        #     if re.match(r"[（\(]\d{4}年\d{1,2}月\d{1,2}日", text):
        #         isDesc = True
        #         hasDesc = True
        #
        #     if isDesc:
        #         desc += text
        #     elif n > 0 and not re.match(r"^目\s*录\s*$", text) and dia == False:
        #         content.append(text)
        #         content_fonts.append(is_diff_font)
        #     elif n > 0 and re.match(r"^目\s*录\s*$", text):
        #         dia = True
        #         content.append(text)
        #         content_fonts.append(is_diff_font)
        #     elif n > 0 and dia == True and text not in content:
        #         content.append(text)
        #         content_fonts.append(is_diff_font)
        #     elif n > 0 and dia == True and text in content and text != '':
        #         index = content.index(text)
        #         content = content[:index - 1]
        #         content_fonts = content_fonts[:index - 1]
        #         content.append(text)
        #         content_fonts.append(is_diff_font)
        #         dia = False
        #
        #     # 信息行结束
        #     if isDesc and re.search("[）\)]$", text):
        #         isDesc = False
        #     if isDesc and re.search(r"目.*录", text):
        #         isDesc = False
        #     if isDesc and isStartLine(text):
        #         isDesc = False
        #
        #     if not hasDesc and re.search("^法释", text):
        #         hasDesc = True
        #
        # return title, desc, content, content_fonts


