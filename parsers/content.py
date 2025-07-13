import logging
import re
from typing import List

from common import INDENT_RE, LINE_START, NUMBER_RE

logger = logging.getLogger(__name__)

#
class ContentParser(object):
    def __filter_content(self, content: List[str]) -> List[str]:
        # 去除目录、公告、冗余行、规范格式
        menu_start = False  # 目录
        menu_at = -1  # 页面
        pattern = ""  # 模式
        filtered_content = []  # 内容
        skip = False
        pattern_re = None  # 正则模式

        for i in range(len(content)):
            # 全角空格替换为半角，统一空格为一个空格
            line = content[i].replace("\u3000", " ").replace("　", " ")
            line = re.sub("\s+", " ", line)
            # 识别目录部分，记录下一行作为参考目录项格式
            if menu_at >= 0 and i == menu_at + 1:
                pattern = line

                for r in INDENT_RE:
                    if re.match(r, line):
                        pattern_re = r.replace(NUMBER_RE, "一")
                        break
                continue
            # 遇到目录开始跳过
            if re.match("目.*录", line):
                menu_start = True
                menu_at = i
                continue
            # 判断目录是否结束多种形式
            if line == pattern:
                menu_start = False

            if menu_start and pattern_re:
                if re.match(pattern_re, line):
                    menu_start = False
            elif menu_start and not pattern_re:
                if re.match(LINE_START, line):
                    menu_start = False
            # 跳过公告页
            if i < 40 and re.match("公\s*告", line):
                skip = True

            # if re.match("^附", line):
            #     break
            # 添加正文内容，遇到第十二条 多少章这类 后面补一个空格
            if not menu_start and not skip:
                content_line = re.sub(
                    f"^(第{NUMBER_RE}{{1,6}}[条章节篇](?:之{NUMBER_RE}{{1,2}})*)\s*",
                    lambda x: x.group(0).strip() + " ",
                    line.strip(),
                )
                filtered_content.append(content_line)
            # 法释 字样结束公告跳过
            if skip and re.match("法释", line):
                skip = False

        return filtered_content

    def __filter_desc(self, desc: str) -> List[str]:
        # 正则提取 X年X月X日根据。。。施行 的这样条目
        desc_arr = re.findall(
            r"(\d{4}年\d{1,2}月\d{1,2}日.*?(?:(?:根据)|(?:通过)|(?:公布)|(?:施行)|(?:）)|(?:　)))",
            desc,
        )
        # 补空格，起施行 转换成 施行
        desc_arr = map(
            lambda line: re.sub(
                "^(\d{4,4}年\d{1,2}月\d{1,2}日)", lambda x: x.group(0) + " ", line
            ),
            desc_arr,
        )
        desc_arr = map(lambda x: x.replace("起施行", "施行"), desc_arr)
        return list(desc_arr)

    def __get_indents(self, content: List[str]) -> List[str]:
        # 遍历正文，第几章第几条 识别
        ret = []
        for line in content:
            for r in INDENT_RE:
                if r not in ret and re.match(r, line):
                    ret.append(r)
                    break
        return ret

    def parse(self, result, title: str, desc, content: List[str], law_id:str) -> List[str]:
        # , content_fonts: List
        desc = self.__filter_desc(desc)
        content = self.__filter_content(content)
        # print(result)
        # print(title)
        # print(desc)
        # print(content)
        # print()
        # id = result["id"]
        # name = result['title']
        header = []
        office = result['office']
        level = result['level']
        status = result['status']
        publish = result['publish']
        expiry = result['expiry']

        intro_title = ""
        intro_lines = []  # 序言

        # chapter_pattern = r"^第[一二三四五六七八九十百千万\d]+章"
        # section_pattern = r"^第[一二三四五六七八九十百千万\d]+节"
        # article_pattern = r"^第[一二三四五六七八九十百千万\d]+条"
        _ws = r"[\s\u3000\u00A0\u000B\u000C\ufeff]*"  # 半/全角空格、NBSP、纵向制表…
        part_pattern = rf"^{_ws}第{_ws}[一二三四五六七八九十百千万\d]+{_ws}编{_ws}.*$"
        subpart_pattern = rf"^{_ws}第{_ws}[一二三四五六七八九十百千万\d]+{_ws}分编{_ws}.*$"
        chapter_pattern = rf"^{_ws}第{_ws}[一二三四五六七八九十百千万\d]+{_ws}章{_ws}.*$"
        section_pattern = rf"^{_ws}第{_ws}[一二三四五六七八九十百千万\d]+{_ws}节{_ws}.*$"
        article_pattern = rf"^{_ws}第{_ws}[一二三四五六七八九十百千万\d]+{_ws}条"

        indents = self.__get_indents(content)

        # header.append(f"# {title}")
        header  += desc

        def clean_title(title:str) -> str:
            idx2 = title.find("（")
            if idx2 != -1:
                print("Find",title[:idx2])
                return title[:idx2]
            else:
                return title

        # for line in content:
        #     flag = False
        #     for indent, r in enumerate(indents, 2):
        #         if re.match(r, line):
        #             header.append(f"{'#' * indent} {line}")
        #             flag = True
        #             break
        #     if not flag:
        #         header.append(line)


        # 提取序言
        preamble_done = False
        cnt = 0
        for line in content:
            cnt += 1

            if re.match(chapter_pattern, line) or re.match(section_pattern, line) or re.match(article_pattern, line):
                preamble_done = True
                # print("当前行:",line)
                # print("当前:",cnt)
                break
            if line.strip() == clean_title(title) or not line.strip():
                continue
            if re.search(r"\d{4}年\d{1,2}月\d{1,2}日.*(根据|通过|公布|施行)", line):
                header.append(line.strip())
            if re.match(r"^序\s*言$", line.strip()):
                intro_title = "序\u3000言"
                continue
            if not re.search(r"\d{4}年\d{1,2}月\d{1,2}日.*(根据|通过|公布|施行)", line) and line.strip() and not preamble_done:
                intro_lines.append(line.strip())

        intro_text = "\n".join(intro_lines).strip()
        # print(cnt)
        content = content[cnt-1:]
        # content_fonts = content_fonts[cnt-1:]
        # print(content)
        # 重新遍历，用来构造章节
        structure = []
        current_part = None  # 编
        current_subpart = None  # 分编
        current_chapter = None  # 章
        current_section = None  # 节
        current_articles = []

        for line in content:
            # 章
            if re.match(chapter_pattern, line):
                if current_section:
                    current_section["articles"] = current_articles
                    current_chapter["sections"].append(current_section)
                    current_section, current_articles = None, []

                if current_chapter:
                    structure.append(current_chapter)

                current_chapter = {
                    "chapter_title": line,
                    # "chapter_context": "",   # ← 已注释掉
                    "sections": []
                }
                continue

            # 节
            if re.match(section_pattern, line):
                if current_chapter is None:
                    current_chapter = {
                        "chapter_title": "",
                        # "chapter_context": "",  # ← 已注释掉
                        "sections": []
                    }
                if current_section:
                    current_section["articles"] = current_articles
                    current_chapter["sections"].append(current_section)

                current_section = {
                    "section_title": line,
                    # "section_context": "",   # ← 已注释掉
                    "articles": []
                }
                current_articles = []
                continue

            # 条
            article_match = re.match(r"^(第[一二三四五六七八九十百千万\d]+条)\s*(.*)", line)
            if article_match:
                if current_chapter is None:
                    current_chapter = {
                        "chapter_title": "",
                        # "chapter_context": "",  # ← 已注释掉
                        "sections": []
                    }
                if current_section is None:
                    current_section = {
                        "section_title": "",
                        # "section_context": "",  # ← 已注释掉
                        "articles": []
                    }
                current_articles.append({
                    "article_title": article_match.group(1),
                    "article_context": article_match.group(2)
                })
                continue

            # 其它正文（只追加到最后一条的 article_context）
            if current_articles:
                current_articles[-1]["article_context"] += line.strip()
            # ↓ 下面这几行与 context 写入相关的也统统可删
            # elif current_section:
            #     current_section["section_context"] += line.strip()
            # elif current_chapter:
            #     current_chapter["chapter_context"] += line.strip()

        # ---------- 收尾 ----------
        if current_section:
            current_section["articles"] = current_articles
            current_chapter["sections"].append(current_section)
        elif current_articles:
            current_chapter["sections"].append({
                "section_title": "",
                # "section_context": "",       # ← 已注释掉
                "articles": current_articles
            })

        if current_chapter:
            structure.append(current_chapter)
        elif current_articles:
            structure.append({
                "chapter_title": "",
                # "chapter_context": "",       # ← 已注释掉
                "sections": [{
                    "section_title": "",
                    # "section_context": "",   # ← 已注释掉
                    "articles": current_articles
                }]
            })
        # for line, is_fonts in zip(content, content_fonts):
        # for line in content:
        #     # ---------- 遇到章 ----------
        #     if re.match(chapter_pattern, line):
        #         # 如果有旧的 section，要收尾到旧 chapter
        #         if current_section:
        #             current_section["articles"] = current_articles
        #             current_chapter["sections"].append(current_section)
        #             current_section = None
        #             current_articles = []
        #
        #         # 如果有旧的 chapter，保存
        #         if current_chapter:
        #             structure.append(current_chapter)
        #
        #         # 新章
        #         current_chapter = {
        #             "chapter_title": line,
        #             "chapter_context": "",
        #             "sections": []
        #         }
        #         current_section = None
        #         current_articles = []
        #         continue
        #
        #     # ---------- 遇到节 ----------
        #     if re.match(section_pattern, line):
        #         # 确保有章，没有就初始化一个空章
        #         if current_chapter is None:
        #             current_chapter = {
        #                 "chapter_title": "",
        #                 "chapter_context": "",
        #                 "sections": []
        #             }
        #
        #         # 如果有旧的 section，保存
        #         if current_section:
        #             current_section["articles"] = current_articles
        #             current_chapter["sections"].append(current_section)
        #
        #         # 新节
        #         current_section = {
        #             "section_title": line,
        #             "section_context": "",
        #             "articles": []
        #         }
        #         current_articles = []
        #         continue
        #
        #     # ---------- 遇到条 ----------
        #     article_match = re.match(r"^(第[一二三四五六七八九十百千万\d]+条)\s*(.*)", line)
        #     if article_match:
        #         #if is_fonts:
        #             #print(is_fonts)
        #             # 是加粗，说明是新的条，正常新建
        #         if current_chapter is None:
        #             current_chapter = {
        #                 "chapter_title": "",
        #                 "chapter_context": "",
        #                 "sections": []
        #             }
        #         if current_section is None:
        #             current_section = {
        #                 "section_title": "",
        #                 "section_context": "",
        #                 "articles": []
        #             }
        #
        #         art_title = article_match.group(1)
        #         art_context = article_match.group(2)
        #         current_articles.append({
        #             "article_title": art_title,
        #             "article_context": art_context
        #         })
        #         # else:
        #         #     # 是条但是非加粗，续写到上一条的正文
        #         #     print(is_fonts)
        #         #     print(line)
        #         #     if current_articles:
        #         #         current_articles[-1]["article_context"] += line.strip()
        #         #     elif current_section:
        #         #         current_section["section_context"] += line.strip()
        #         #     elif current_chapter:
        #         #         current_chapter["chapter_context"] += line.strip()
        #         continue
        #
        #     # ---------- 其它内容（上下文） ----------
        #     if current_articles:
        #         current_articles[-1]["article_context"] += line.strip()
        #     elif current_section:
        #         current_section["section_context"] += line.strip()
        #     elif current_chapter:
        #         current_chapter["chapter_context"] += line.strip()
        #
        # # ---------- 收尾 ----------
        # if current_section:
        #     current_section["articles"] = current_articles
        #     current_chapter["sections"].append(current_section)
        # elif current_articles:
        #     # 有条但没有节
        #     current_chapter["sections"].append({
        #         "section_title": "",
        #         "section_context": "",
        #         "articles": current_articles
        #     })
        #
        # if current_chapter:
        #     structure.append(current_chapter)
        # elif current_articles:
        #     # 只有条，没有章
        #     structure.append({
        #         "chapter_title": "",
        #         "chapter_context": "",
        #         "sections": [
        #             {
        #                 "section_title": "",
        #                 "section_context": "",
        #                 "articles": current_articles
        #             }
        #         ]
        #     })


        # print(str(result.get("id","")))
        # print(title)
        # print(result.get("office",""))
        # print(result.get("publish", "").split(" ")[0])
        # print(result.get("expiry", "").split(" ")[0] if result.get("expiry") else None)
        # print(status)
        # print(result.get("level", ""))
        # print("intro line:",intro_text)
        # print(structure)

        # header = desc

        # 返回 JSON 对象
        return {"_id": law_id,
            "title": title,
            "office": office,
            "publish_date": publish,
            "expired_date": expiry,
            "status": status,
            "level": level,
            "header": header,
            "intro": intro_title,
            "intro_text": intro_text,
            "structure": structure
        }

        # return {
        #     "id": str(result.get("id", "")),  # 可根据需要生成 uuid
        #     "title": title,
        #     "office": result.get("office", ""),
        #     "publish_date": result.get("publish", "").split(" ")[0],
        #     "expired_date": result.get("expiry", "").split(" ")[0] if result.get("expiry") else None,
        #     "status": "有效" if result.get("status") == "1" else "失效",
        #     "level": result.get("level", ""),
        #     "desc": desc_list,
        #     "intro": intro_text,
        #     "structure": structure
        # }

        # 没有序言，也没有，章、没有节、条开始
        # 'chapter' : ''  # 第一章
        # 'content' : ''  # 璀璨文明
        #
        # 'section' : '第一节 主席...'  # 节
        # 'context' : '....'  #..
        #
        # 'aricletitle':'第一条'
        # 'contenxt': '..'



        #第一个括号 放进introduction或者header
        # 'header':'...'
        # 'intr':'...'

