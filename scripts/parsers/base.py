from abc import ABC, abstractmethod
from typing import List, Tuple
from manager.request import RequestManager


# 抽象类 统一接口 子类 HTMLParser/wordparser 都实现parse()方法
class Parser(ABC):
    def __init__(self, parse_type) -> None:
        super().__init__()
        self.request = RequestManager()
        self.parse_type = parse_type

    @abstractmethod
    def parse(self, result, detail) -> Tuple[str, str, List[str]]:
        pass

    def __eq__(self, __o: object) -> bool:
        return __o == self.parse_type
