"""
所有Rule类的父类
"""
import re
from extract.rule.enum_field import *

RULE_CONSTRUCT_ATTR_NAME = "field_name2tag_name"
RULE_PRE_CONSTRUCT_ATTR_NAME = "attr_reobjs2field_name"
RULE_REOBJ_ATTR_NAME = "reobj"
RULE_ATTR_VALUE_ATTR_NAME = "attr_value"

class SuperRule(object):
    """
    定义一些共用的模板碎片让子类组合使用；定义一个共用的构造match_result方法让子类回调
    """
    def __init__(self):
        self.financing_company_pattern = (r"(?:(?P<bp><融资方标签>)?(?P<fc><关联方>))", "bp", "fc")
        self.full_financing_company_pattern = (r"(?:(?P<bp><融资方标签>)(?P<fc><关联方>))", "bp", "fc")
        self.investors_pattern = (r"(?P<i>(?:(?:<属性名词>的?)?(?:<关联方>)(?:（<属性名词>）)?(?:、|和|以?及)?)+)等?(?:机构|基金|则?(?:以|作为)?(?:<属性名词>))?", "i")
        self.may_be_deal_size_pattern = (r"(?P<ds><金额>)?", "ds")
        self.single_rp_pattern = (r"(?P<rp><关联方>)?", "rp")
        self.deal_size_pattern = (r"(?P<ds><金额>)", "ds")
        self.may_be_deal_type_pattern = r"(?:<交易类型>)?"
        self.deal_type_pattern = r"<交易类型>"
        self.date_pattern = r"(?:<发生时间>|<披露时间>)?"
        self.attr_noun_pattern = (r"(?P<attr><属性名词>)", "attr")
        self.anychar_pattern = r"[^，；]*?"
        self.anychar_notag_pattern = r"[^，；<>]*?"
    
    def construct(self, entities_sent: str, attr_noun_dict):
        """构造匹配结果

        Args:
            entities_sent (str): 实体句子
            attr_noun_dict (dict): 属性名词在实体句子的span到原值的映射

        Returns:
            list: 返回匹配结果的结构体，结构体的各字段的值用span表示
        """
        reobj = self.get_reobj()
        field_name2tag_name = self.get_field_name2tag_name()
        match_result = []
        if not reobj or not field_name2tag_name:
            return match_result
        matches = reobj.finditer(entities_sent)
        attr_reobj2field_name = self.get_attr_reobj2field_name()
        attr_value_tag = self.get_attr_value_tag_name()
        for match in matches:
            mr = None
            if attr_reobj2field_name and attr_value_tag:
                attr_noun_span = match.span(field_name2tag_name[ATTRIBUTE_NOUN])
                if attr_noun_span != (-1, -1):
                    attr_noun_content = attr_noun_dict[attr_noun_span]
                    for attr_reobj, field_name in attr_reobj2field_name.items():
                        new_field_name2tag_name = {k:v for k, v in field_name2tag_name.items()}
                        if attr_reobj.search(attr_noun_content):
                            new_field_name2tag_name[field_name] = attr_value_tag
                            mr = self.__construct(entities_sent, match, new_field_name2tag_name)
            else:
                mr = self.__construct(entities_sent, match, field_name2tag_name)
            if mr:
                match_result.append(mr)
        return match_result
    
    def __construct(self, entities_sent, match, field_name2tag_name):
        is_leading_investor = True if LEADING_INVESTOR in field_name2tag_name else (False if INVESTOR in field_name2tag_name else None)
        struct = {}
        if is_leading_investor != None:
            struct["is_leading_investor"] = is_leading_investor
        for field_name, tag_name in field_name2tag_name.items():
            sp = match.span(tag_name)
            if sp != (-1, -1):
                if field_name in (INVESTOR, LEADING_INVESTOR, FINANCIAL_ADVISERS):
                    struct[enum_field_dict[field_name]] = self.get_multi_value_idx_spans(entities_sent, sp, "<关联方>")
                    continue
                struct[enum_field_dict[field_name]] = sp
        if len(struct) > 0:
            mr = {"struct": struct}
            mr["match_span"] = match.span()
            mr["from_rule"] = self.__class__.__name__
            return mr
        return None

    def set_field_name2tag_name(self, __value: dict):
        setattr(self, RULE_CONSTRUCT_ATTR_NAME, __value)
        
    def get_field_name2tag_name(self):
        return getattr(self, RULE_CONSTRUCT_ATTR_NAME, None)

    def set_attr_reobj2field_name(self, __value: dict):
        setattr(self, RULE_PRE_CONSTRUCT_ATTR_NAME, __value)
        
    def get_attr_reobj2field_name(self):
        return getattr(self, RULE_PRE_CONSTRUCT_ATTR_NAME, None)

    def set_attr_value_tag_name(self, __value):
        setattr(self, RULE_ATTR_VALUE_ATTR_NAME, __value)
        
    def get_attr_value_tag_name(self):
        return getattr(self, RULE_ATTR_VALUE_ATTR_NAME, None)

    def set_reobj(self, __value):
        setattr(self, RULE_REOBJ_ATTR_NAME, __value)
        
    def get_reobj(self):
        return getattr(self, RULE_REOBJ_ATTR_NAME, None)

    def get_multi_value_idx_spans(self, entities_sent: str, pos_span: tuple, match_for: str):
        res = []
        list_reobj = re.compile(match_for)
        matches = list_reobj.finditer(entities_sent, pos_span[0], pos_span[1])
        for m in matches:
            res.append(m.span())
        return res