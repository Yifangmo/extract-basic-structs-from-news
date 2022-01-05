"""
用于定义匹配实体句子的模板及规则。所有Rule的类名以"Rule"开头，后接编号。所有Rule类需要继承SuperRule
"""
from extract.rule.super_rule import *
from extract.rule.enum_field import *
import re

class Rule1(SuperRule):
    def __init__(self):
        super().__init__()
        # 36氪获悉，<关联方>于<发生时间>连续完成<交易类型>，包括<关联方>投资的<金额><交易类型>，以及<关联方>领投和<关联方>跟投的<金额><交易类型>
        # self.pattern = r"((?P<bp><融资方标签>)?(?P<fc><关联方>))?[^，；<>]*(?:<发生时间>|<披露时间>)?[^，；<>]*(?:完成|获)[^，；]*(?P<ds><金额>)?[^，；<>]*<交易类型>"
        self.pattern = "".join([self.financing_company_pattern[0], "?", self.anychar_notag_pattern, self.date_pattern, 
                                self.anychar_notag_pattern, r"(?:完成|获)", self.anychar_pattern, self.may_be_deal_size_pattern[0], 
                                self.anychar_notag_pattern, self.deal_type_pattern])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2], 
            DEAL_SIZE: self.deal_size_pattern[1]
        })

    def __call__(self, entities_sent, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule2(SuperRule):
    def __init__(self):
        super().__init__()
        # self.pattern = r"((?:(?:<属性名词>的?)?(?:<关联方>)(?:、|和|以?及)?)+)等?(?:机构|基金|(<属性名词>))?(?:联合|重仓加码|共同|独家)?(?:领投|牵头)"
        self.pattern = "".join([self.investors_pattern[0], "(?:联合|重仓加码|共同|独家)?(?:领投|牵头)"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            LEADING_INVESTOR: self.investors_pattern[1], 
        })

    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule3(SuperRule):
    def __init__(self):
        super().__init__()
        # 其中，红杉中国作为老股东继续增持，华平投资则是本轮新进入的领投方。
        # self.pattern = r"((?:(?:<属性名词>的?)?(?:<关联方>)(?:、|和|以?及)?)+)等?(?:机构|基金|则?(以|作为)?(?:<属性名词>)?)?也?(?:联合|共同|继续|同轮|独家|超额)?(?:参与到?|追加)?了?(?:战略)?(?:(?:本轮|本次)(?:投资|融资)|融资|投资|跟投|加持|增持|参投)"
        self.pattern = "".join([self.investors_pattern[0], "也?(?:联合|共同|继续|同轮|独家|超额|持续)?(?:参与到?|追加)?了?(?:战略)?(?:(?:本轮|本次)(?:投资|融资)|融资|投资|跟投|加持|增持|参投|参与)"])
        # self.pattern = "".join([self.investors_pattern[0], "持续参投"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            INVESTOR: self.investors_pattern[1], 
        })

    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule4(SuperRule):
    def __init__(self):
        super().__init__()
        self.pattern = "".join([self.full_financing_company_pattern[0], self.anychar_notag_pattern, "，"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2], 
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule5(SuperRule):
    def __init__(self):
        super().__init__()
        # self.pattern = r"(?P<fc><关联方>)[^，；<>]*签署<交易类型>协议"
        self.pattern = "".join([self.financing_company_pattern[0], self.anychar_notag_pattern, r"签署<交易类型>协议"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2]
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)
    
class Rule6(SuperRule):
    def __init__(self):
        super().__init__()
        # 中俄投资基金进行战略性股权投资
        # self.investors_pattern = r"(?P<i>(?:(?:<属性名词>的?)?(?:<关联方>)(?:、|和|以?及)?)+)等?"
        self.pattern = self.investors_pattern[0] + r"进行<交易类型>"
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({INVESTOR: self.investors_pattern[1]})
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule7(SuperRule):
    def __init__(self):
        super().__init__()        
        # 作为<属性名词>，<关联方>这次选择了直接投资<关联方>。
        # 此前，<关联方>、<关联方>、<关联方>、<关联方>、<关联方>、<关联方>等<属性名词>以<金额>投资「<关联方>」是中国农业科技领域历史上最大的一笔商业融资。
        # self.pattern = r"(?:<属性名词>)?(<关联方>)投资(关联方)"
        self.pattern = "".join([self.investors_pattern[0], "以", self.may_be_deal_size_pattern[0], self.anychar_notag_pattern, r"投资", self.financing_company_pattern[0]])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            INVESTOR: self.investors_pattern[1], 
            DEAL_SIZE: self.may_be_deal_size_pattern[1], 
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2]
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule8(SuperRule):
    def __init__(self):
        super().__init__()
        # 专注于人工智能的农业技术初创公司Intello Labs在由Avaana Capital牵头的一轮融资中筹集了500万美元
        # self.pattern = r"(?P<bp><融资方标签>)?(?P<fc><关联方>)在[^，；]*<交易类型>[^，；<>]*筹集[^，；<>]*(?P<ds><金额>)"
        self.pattern = "".join([self.financing_company_pattern[0], self.anychar_pattern, r"在", self.anychar_pattern, self.deal_type_pattern, self.anychar_notag_pattern, r"筹集", self.anychar_notag_pattern, self.deal_size_pattern[0]])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2], 
            DEAL_SIZE: self.deal_size_pattern[1]
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule9(SuperRule):
    def __init__(self):
        super().__init__()
        # 此次注资，是高瓴创投对去年11月极飞科技12亿元人民币融资的追加投资。
        # "此次注资，是<关联方>对<发生时间><关联方><金额><交易类型>的追加投资。"
        self.pattern = "".join([self.investors_pattern[0], r"对",self.date_pattern, self.financing_company_pattern[0], self.may_be_deal_size_pattern[0], self.may_be_deal_type_pattern, self.anychar_notag_pattern, r"投资"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            INVESTOR: self.investors_pattern[1], 
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2], 
            DEAL_SIZE: self.may_be_deal_size_pattern[1]
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule10(SuperRule):
    def __init__(self):
        super().__init__()
        # Stripe估值达到950亿美元
        self.pattern = "".join([self.financing_company_pattern[0], r"估值达到?(?P<pmv><金额>)"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            FINANCING_COMPANY: self.financing_company_pattern[1],
            POST_MONEY_VALUATION: "pmv"
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule11(SuperRule):
    def __init__(self):
        super().__init__()
        # 本轮投资来自险峰长青。
        self.deal_type_pattern = r"((?:(?:(?:Pre-|pre-)?[A-H]\d?|天使|种子|新一|上一?|本|此|该|两|首)(?:\+)?(?:轮|次)(?:融资|投资)?)|天使投资)"
        self.pattern = "".join([self.deal_type_pattern, r"来自", self.investors_pattern[0]])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({INVESTOR: self.investors_pattern[1]})
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule12(SuperRule):
    def __init__(self):
        super().__init__()
        self.pattern = "".join([self.deal_size_pattern[0], "的?", self.deal_type_pattern])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({DEAL_SIZE: self.deal_size_pattern[1]})
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)
    
class Rule13(SuperRule):
    def __init__(self):
        super().__init__()
        self.pattern = "".join([r"(?:完成|获得?)", self.investors_pattern[0], self.anychar_notag_pattern, self.may_be_deal_size_pattern[0], r"的?", self.deal_type_pattern])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            INVESTOR: self.investors_pattern[1],
            DEAL_SIZE: self.may_be_deal_size_pattern[1],
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)
        
class Rule14(SuperRule):
    def __init__(self):
        super().__init__()
        self.pattern = "".join([self.financing_company_pattern[0], self.anychar_notag_pattern, r"宣布|获|完成", 
                                self.anychar_notag_pattern, r"[，；]", self.anychar_notag_pattern, self.deal_type_pattern])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2], 
        })
        
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)
    
# 与金额相关的属性名词的匹配规则
class Rule15(SuperRule):
    def __init__(self):
        super().__init__()
        self.pattern = "".join([self.financing_company_pattern[0], r"?的?", self.attr_noun_pattern[0], r"(?:已|将)?(?:达到?|为)?了?",self.deal_size_pattern[0]])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            BUSSINESS_PROFLIE: self.financing_company_pattern[1], 
            FINANCING_COMPANY: self.financing_company_pattern[2], 
            ATTRIBUTE_NOUN: self.attr_noun_pattern[1],
        })
        self.set_attr_value_tag_name(self.deal_size_pattern[1])
        self.set_attr_reobj2field_name({
            re.compile(r"(?:总|整体|累计)?融资(?:总?金?额|规模|累计金?额)|规模"): DEAL_SIZE,
            re.compile(r"(?<!投前)估值"): POST_MONEY_VALUATION,
            re.compile(r"投前估值"): PRE_MONEY_VALUATION
        })
    
    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

# 与投资者和财务顾问相关的匹配规则
class Rule18(SuperRule):
    def __init__(self):
        super().__init__()
        # (r"(<属性名词>)还?(?:主要)?(?:为|是|有|囊括|包括|涉及|包?含)((?:(?:<属性名词>的?)?(?:<关联方>)(?:、|和|以?及)?)+)",
        self.pattern = "".join([self.attr_noun_pattern[0], r"还?(?:主要)?(?:为|是|有|囊括|包括|涉及|包?含)",self.investors_pattern[0]])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            ATTRIBUTE_NOUN: self.attr_noun_pattern[1],
        })
        self.set_attr_value_tag_name(self.investors_pattern[1])
        self.set_attr_reobj2field_name({
            re.compile(r"投资方|投资人|投资者|投资机构|参投|跟投"): INVESTOR,
            re.compile(r"领投方?|领投机构"): LEADING_INVESTOR,
            re.compile(r"财务顾问|融资顾问"): FINANCIAL_ADVISERS
        })

    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

# 与投资者和财务顾问相关的匹配规则
class Rule19(SuperRule):
    def __init__(self):
        super().__init__()
        # r"(<属性名词>)的?((?:(?:<属性名词>的?)?(?:<关联方>)(?:、|和|以?及)?)+)"
        self.pattern = "".join([self.attr_noun_pattern[0], r"的?",self.investors_pattern[0]])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            ATTRIBUTE_NOUN: self.attr_noun_pattern[1],
        })
        self.set_attr_value_tag_name(self.investors_pattern[1])
        self.set_attr_reobj2field_name({
            re.compile(r"财务顾问|融资顾问"): FINANCIAL_ADVISERS,
            re.compile(r"领投方?|领投机构"): LEADING_INVESTOR
        })

    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

# 与投资者和财务顾问相关的匹配规则
class Rule20(SuperRule):
    def __init__(self):
        super().__init__()
        # r"((?:(?:<属性名词>的?)?(?:<关联方>)(?:、|和|以?及)?)+)等?(?:作为|在内的|等|则是|则以|(?:继续)?担?任)(<属性名词>)        self.pattern = "".join([self.attr_noun_pattern[0], r"还?(?:主要)?(?:为|是|有|囊括|包括|涉及|包?含)",self.investors_pattern[0]])
        self.pattern = self.investors_pattern[0] + r"(?:作为|在内的|等|则是|则以|(?:继续)?担?任)" + self.attr_noun_pattern[0]
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            ATTRIBUTE_NOUN: self.attr_noun_pattern[1],
        })
        self.set_attr_value_tag_name(self.investors_pattern[1])
        self.set_attr_reobj2field_name({
            re.compile(r"投资方|投资人|投资者|投资机构|参投|跟投"): INVESTOR,
            re.compile(r"领投方?|领投机构"): LEADING_INVESTOR,
            re.compile(r"财务顾问|融资顾问"): FINANCIAL_ADVISERS
        })

    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)

class Rule21(SuperRule):
    def __init__(self):
        super().__init__()
        # 投资方为云九资本、红杉资本中国、前海母基金、磐晟资产、义柏资本（财务顾问）
        self.pattern = "".join([self.single_rp_pattern[0], "（", self.attr_noun_pattern[0], "）"])
        self.set_reobj(re.compile(self.pattern))
        self.set_field_name2tag_name({
            ATTRIBUTE_NOUN: self.attr_noun_pattern[1],
        })
        self.set_attr_value_tag_name(self.single_rp_pattern[1])
        self.set_attr_reobj2field_name({re.compile(r"财务顾问|融资顾问"): FINANCIAL_ADVISERS})

    def __call__(self, entities_sent: str, attr_noun_dict: dict):
        return self.construct(entities_sent, attr_noun_dict)
