
"""
一些关键字的包装器，用于调用MergeEngine
"""
from merge import KeyWrapper

class PrimaryNameWrapper(KeyWrapper):
    def __init__(self, value: str):
        super().__init__(value)
        
    def __eq__(self, __o: object):
        if self.value == __o.value:
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
