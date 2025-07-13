import re
from typing import List, Tuple
from bs4 import BeautifulSoup
from parsers.base import Parser


class HTMLParser(Parser):
    def __init__(self) -> None:
        super().__init__("HTML")

    def parse(self, result, detail) -> Tuple[str, str, List[str]]:
        # html 网页加载内容 没数据返回None
        html_data = self.request.get_html(detail["url"])

        if not html_data:
            return

        # 解析html title 标题
        bs4 = BeautifulSoup(html_data, features="lxml")
        title = bs4.title.text
        # 提取正文段落
        parts = bs4.find("div", class_="law-content").find_all("p")
        content = map(lambda x: x.text.replace("\xa0", " ").strip(), parts)
        # 过滤空行 和 冗余内容
        content = filter(lambda x: x, content)
        content = filter(
            lambda x: not title.startswith(x) and not title.endswith(x), content
        )
        # 转列表 修正标题
        content = list(content)
        if not title and re.match("^中华人民共和国", content[0]):
            title = content[0]
            content = content[1:]
        return title, content[0], content[1:]
