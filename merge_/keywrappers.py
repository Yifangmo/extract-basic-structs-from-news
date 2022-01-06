import re
"""
一些关键字的包装器，用于调用MergeEngine
"""
from merge import KeyWrapper

class PrimaryNameWrapper(KeyWrapper):
    def __init__(self, value: str):
        self.__refer_reobj = re.compile(r"本?公司")
        super().__init__(value)
        
    def __eq__(self, __o: object):
        if self.value == __o.value or self.__refer_reobj.match(self.value) or self.__refer_reobj.match(__o.value):
            return True
        v1 = self.value.upper()
        v2 = __o.value.upper()
        if v1.find(v2) != -1 or v2.find(v1) != -1:
            return True
        return False
    
    def __hash__(self) -> int:
        return 0
    
    
    def __lt__(self, __x: str) -> bool:
        sv = self.value
        xv = __x.value
        if self.__refer_reobj.match(xv):
            return True
        if self.__refer_reobj.match(sv):
            return False
        setxv = set(xv)
        setsv = set(sv)
        if setsv.issubset(setxv):
            return True
        if setxv.issubset(setsv):
            return False
        if len(sv) < len(xv):
            return False
        elif len(sv) > len(xv):
            return True
        else:
            if sv.isupper():
                return True
            if xv.isupper():
                return False
        return True
