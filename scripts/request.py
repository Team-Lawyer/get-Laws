import logging
import os
import re
import sys
from hashlib import md5
from pathlib import Path
from time import time
from typing import Any, List

from common import LINE_RE
from manager import CacheManager, RequestManager
from parsers import ContentParser, HTMLParser, Parser, WordParser

# ======MongoDB 配置
from pymongo import MongoClient
from urllib.parse import quote_plus

Password = quote_plus("lt3370")
Mongo_URI = f"mongodb+srv://lawtry:{Password}@cluster0.qom7j5h.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = MongoClient(Mongo_URI)

# =====Logger 配置
logger = logging.getLogger("Law")
logger.setLevel(logging.DEBUG)

# 输出格式
formatter = logging.Formatter("%(asctime)s:%(levelname)s:%(message)s")
# 控制台输出
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(console_handler)

# 文件解析器（word 或者html）
def find(f, arr: List[Any]) -> Any:
    for item in arr:
        if f(item):
            return item
    raise Exception("not found")

# 判断某一行是否是正文开始
def isStartLine(line: str):
    for reg in LINE_RE:
        if re.match(reg, line):
            return True
    return False


class LawParser(object):
    def __init__(self) -> None:
        self.request = RequestManager()
        self.spec_title = None
        self.parser = [
            HTMLParser(),
            WordParser(),
        ]
        self.content_parser = ContentParser()
        self.cache = CacheManager()
        self.categories = []

        self.mongo_client = client
        self.db = self.mongo_client["lawdb"]


    def __reorder_files(self, files):
        # 必须有 parser
        files = list(
            filter(
                lambda x: x["type"] in self.parser,
                files,
            )
        )
        # 只保留HTML/WORD文件 排序后列表
        if len(files) == 0:
            return []

        if len(files) > 1:
            # 按照 parser 的位置排序， 优先使用级别
            files = sorted(files, key=lambda x: self.parser.index(x["type"]))

        return files

    def is_bypassed_law(self, item) -> bool:
        # 用正则排出 决定、复函、批复等法律
        title = item["title"].replace("中华人民共和国", "")
        if self.spec_title and title in self.spec_title:
            return False
        if re.search(r"的(决定|复函|批复|答复|批复)$", title):
            return True
        return False

    def parse_law(self, item):
        ### 正文文件，找到合适的格式HTML还是DOC 读取内容
        detail = self.request.get_law_detail(item["id"])
        # print(item["id"])
        law_id = item["id"]
        result = detail["result"]
        title = result["title"]
        # 类别
        level = result["level"]

        # 根据 level 确定 collection 名称 🙋🙋🙋🙋🙋
        if level == "宪法":
            collection_name = "constitutions"
        else:
            collection_name = "laws"

        # 获取 collection，MongoDB 会自动创建（不存在时）
        existing_collections = self.db.list_collection_names()
        collection_exists = collection_name in existing_collections
        collection = self.db[collection_name]

        # 检查是否已经存在相同 id，存在则跳过
        if collection_exists:
            if collection.find_one({"_id": law_id}):
                logger.info(f"Document with id {law_id} name {title} already exists in collection [{collection_name}], skipping.")
                return

        files = self.__reorder_files(result["body"])
        logger.debug(f"parsing {title}")
        if len(files) == 0:
            return
        ### 读取 化成三元组 title, desc, content
        for target_file in files:
            parser: Parser = find(lambda x: x == target_file["type"], self.parser)

            ret = parser.parse(result, target_file)
            if not ret:
                logger.error(f"parsing {title} error")
                continue
            # _, desc, content, content_fonts = ret
            _, desc, content = ret
            # filedata = self.content_parser.parse(result, title, desc, content, law_id, content_fonts)
            filedata = self.content_parser.parse(result, title, desc, content, law_id)
            if not filedata:
                continue
            # 写入 MongoDB Atlas
            collection.insert_one(filedata)

            # 如需保留文件写入，可继续写 MD 文件
            output_path = level / self.__get_law_output_path(title, item["publish"])
            logger.debug(f"parsing {title} success")
            self.cache.write_law(output_path, filedata)
            # print("inserting")
            # # 调用cache中的写入函数 写入。md文件
            # output_path = level / self.__get_law_output_path(title, item["publish"])
            # logger.debug(f"parsing {title} success")
            # self.cache.write_law(output_path, filedata)

    def parse_file(self, file_path, publish_at=None):
        # 离线转 从txt转md
        result = {}
        with open(file_path, "r") as f:
            data = list(filter(lambda x: x, map(lambda x: x.strip(), f.readlines())))
        title = data[0]
        filedata = self.content_parser.parse(result, title, data[1], data[2:])
        if not filedata:
            return
        output_path = self.__get_law_output_path(title, publish_at)
        logger.debug(f"parsing {title} success")
        self.cache.write_law(output_path, filedata)

    def get_file_hash(self, title, publish_at=None) -> str:
        # 基于标题和发布日期生成 MD5哈希值 除重
        _hash = md5()
        _hash.update(title.encode("utf8"))
        if publish_at:
            _hash.update(publish_at.encode("utf8"))
        return _hash.digest().hex()[0:8]

    def __get_law_output_path(self, title, publish_at: str) -> Path:
        # 根据标题 和日期生成。md文件
        title = title.replace("中华人民共和国", "")
        ret = Path(".")
        for category in self.categories:
            if title in category["title"]:
                ret = ret / category["category"]
                break
        # hash_hex = self.get_file_hash(title, publish_at)
        if publish_at:
            output_name = f"{title}({publish_at}).md"
        else:
            output_name = f"{title}.md"
        return ret / output_name

    # def lawList(self):
    #     # 遍历60页法律数据，逐条返回
    #     for i in range(1, 60):
    #         ret = self.request.getLawList(i)
    #         arr = ret["result"]["data"]
    #         if len(arr) == 0:
    #             break
    #         yield from arr
    #
    # def run(self):
    #     # 抓取流程 跳过无效条目 下载正文 解析 存储
    #     for i in range(1, 5):
    #         ret = self.request.getLawList(i)
    #         arr = ret["result"]["data"]
    #         if len(arr) == 0:
    #             break
    #         for item in arr:
    #             if "publish" in item and item["publish"]:
    #                 item["publish"] = item["publish"].split(" ")[0]
    #             if self.is_bypassed_law(item):
    #                 continue
    #             # if item["status"] == "9":
    #             # continue
    #             self.parse_law(item)
    #             if self.spec_title is not None:
    #                 exit(1)
    # ─────────── 抓取控制 ───────────
    def lawList(self):
        """生成器：自动翻页到接口返回空数组为止"""
        page = 1
        while True:
            ret = self.request.getLawList(page)
            arr = ret["result"]["data"]
            if not arr:
                break
            yield from arr
            page += 1

    def run(self):
        for item in self.lawList():
            if "publish" in item and item["publish"]:
                item["publish"] = item["publish"].split(" ")[0]
            if self.is_bypassed_law(item):
                continue
            self.parse_law(item)
            if self.spec_title is not None:
                break

    def remove_duplicates(self):
        # 除重复 因为上面用过哈希值
        p = self.cache.OUTPUT_PATH
        lookup = Path("../")
        for file_path in p.glob("*.md"):
            lookup_files = lookup.glob(f"**/**/{file_path.name}")
            lookup_files = filter(lambda x: "scripts" not in x.parts, lookup_files)
            lookup_files = list(lookup_files)
            if len(lookup_files) > 0:
                os.remove(file_path)
                print(f"remove {file_path}")

def build_xlwj_params(codes: list[str]) -> list[tuple[str, str]]:
    """把 ['01','02',...] 构造成多重 xlwj 参数"""
    return [("xlwj", code) for code in codes]


def main():
    req = LawParser()

    # 需要抓的分类代码（01 宪法，02–08 普通法律/行政法规/司法解释...）
    codes = ["01"] # , "02", "03", "04", "05", "06", "07", "08"]
    req.request.params = build_xlwj_params(codes)

    # 1–9 类：法律、行政法规、地方性法规、司法解释 ...
    req.request.searchType = "1,2,3,4,5,6,7,8,9"
    req.request.req_time = int(time() * 1000)

    args = sys.argv[1:]
    if args:
        # 离线模式：python scripts/request.py file.txt 2024-01-01
        req.parse_file(Path(args[0]), args[1] if len(args) > 1 else None)
        return

    try:
        req.run()
    except KeyboardInterrupt:
        logger.info("keyboard interrupt")
    finally:
        req.remove_duplicates()

# def main():
#     req = LawParser()
#     args = sys.argv[1:]
#     if args:
#         req.parse_file(args[0], args[1])
#         return
#     req.request.searchType = "1,2,3,4,5,6,7,8,9"
#     # req.request.searchType = 'title;vague'
#     req.request.params = [
#         ("xlwj", "01"),
#         # ("type", "公安部规章")
#         ("xlwj", ["02", "03", "04", "05", "06", "07", "08"])  # 法律法规
#         # ("xlwj", ["07"]),
#         #  ("fgbt", "消防法"),
#         # ("fgxlwj", "xzfg"),  # 行政法规
#         # ('type', 'sfjs'),
#         # ("zdjg", "4028814858a4d78b0158a50f344e0048&4028814858a4d78b0158a50fa2ba004c"), #北京
#         # ("zdjg", "4028814858b9b8e50158bed591680061&4028814858b9b8e50158bed64efb0065"), #河南
#         # ("zdjg", "4028814858b9b8e50158bec45e9a002d&4028814858b9b8e50158bec500350031"), # 上海
#         # ("zdjg", "4028814858b9b8e50158bec5c28a0035&4028814858b9b8e50158bec6abbf0039"), # 江苏
#         # ("zdjg", "4028814858b9b8e50158bec7c42f003d&4028814858b9b8e50158beca3c590041"), # 浙江
#         # ("zdjg", "4028814858b9b8e50158bed40f6d0059&4028814858b9b8e50158bed4987a005d"),  # 山东
#         # ("zdjg", "4028814858b9b8e50158bef1d72600b9&4028814858b9b8e50158bef2706800bd"), # 陕西省
#         # (
#         #     "zdjg",
#         #     "4028814858b9b8e50158beda43a50079&4028814858b9b8e50158bedab7ea007d",
#         # ),  # 广东
#         # (
#         #     "zdjg",
#         #     "4028814858b9b8e50158bee5863c0091&4028814858b9b8e50158bee9a3aa0095",
#         # )  # 重庆
#     ]
#     # req.request.req_time = 1647659481879
#     req.request.req_time = int(time() * 1000)
#     # req.spec_title = "反有组织犯罪法"
#     try:
#         req.run()
#     except KeyboardInterrupt:
#         logger.info("keyboard interrupt")
#     finally:
#         req.remove_duplicates()


if __name__ == "__main__":
    main()
