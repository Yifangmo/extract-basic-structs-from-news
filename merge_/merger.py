"""
dict融合器，通过调用MergeEngine来融合，但在调用MergeEngine前需要对deal_type处理并构造合适的实参
"""
from merge import MergeEngine, MAX_LENGTH_FILTER, SAVE_ALL_FILTER
from merge_.keywrappers import PrimaryNameWrapper
import re

class DictMerger():
    def __init__(self):
        self.repl_deal_type_reobj = re.compile(r"(轮|次|笔|轮战略)?([投融增]资)|投融资")
        self.refer_deal_type_reobj = re.compile(r"(本|此|该)")
        self.keys = {
            'deal_type': None, 
            'financing_company': None, 
            'investors.primary_name': PrimaryNameWrapper, 
            'financing_company.primary_name': PrimaryNameWrapper
        }
        self.__date_reobj = re.compile(r"(\d{1,2}月)?\d{1,2}日|年?\d{1,2}月")
        self.is_leading_investor_filter = lambda s : True in s
        # self.date_filter = lambda s: s - {i for i in s if not self.__date_reobj.search(i)}
        self.date_filter = SAVE_ALL_FILTER
        self.full_name_filter = MAX_LENGTH_FILTER
        self.deal_size_filter = SAVE_ALL_FILTER
        self.business_profile_filter = SAVE_ALL_FILTER
        self.post_money_valuation_filter = SAVE_ALL_FILTER
        self.pre_money_valuation_filter = SAVE_ALL_FILTER
        self.filters_dict={
            'investors.is_leading_investor': self.is_leading_investor_filter,
            'financing_company.full_name': self.full_name_filter,
            'investors.full_name': self.full_name_filter,
            'business_profile': self.business_profile_filter,
            'disclosed_dates': self.date_filter,
            'deal_size': self.deal_size_filter,
            'post_money_valuation': self.post_money_valuation_filter,
            'pre_money_valuation': self.pre_money_valuation_filter,
        }
        self.mergeengine = MergeEngine()
        pass
    
    def __call__(self, match_result: list):
        match_result = self.__merge_deal_type(match_result)
        merge_result = self.mergeengine.handle(match_result, self.keys, self.filters_dict)
        return merge_result

    def __merge_deal_type(self, match_result: list):
        deal_type2match_result = {}
        refer_dt_match_results = []
        # 存放“融资”这类不确定交易类型的匹配结果
        swing_dt_match_results = []
        repl_dt_dict = {}
        for mr in match_result:
            if "deal_type" not in mr:
                refer_dt_match_results.append(mr)
                continue
            dt = mr["deal_type"]
            if dt == "融资":
                swing_dt_match_results.append(mr)
            elif dt in deal_type2match_result:
                deal_type2match_result[dt].append(mr)
            elif self.refer_deal_type_reobj.search(dt):
                refer_dt_match_results.append(mr)
            else:
                repl_dt = self.repl_deal_type_reobj.sub("",dt)
                if repl_dt in repl_dt_dict:
                    pre_dt = repl_dt_dict[repl_dt]
                    ult_dt = None
                    # 筛选出更好的交易类型
                    if len(pre_dt) > len(dt):
                        ult_dt = pre_dt
                    elif len(pre_dt) < len(dt):
                        ult_dt = dt
                    else:
                        if dt.endswith("融资"):
                            ult_dt = dt
                        else:
                            ult_dt = pre_dt
                    if ult_dt == pre_dt:
                        mr["deal_type"] = ult_dt
                        deal_type2match_result[ult_dt].append(mr)
                    else:
                        pre_mr = deal_type2match_result[pre_dt]
                        del deal_type2match_result[pre_dt]
                        for mr in pre_mr:
                            mr["deal_type"] = ult_dt
                        pre_mr.append(mr)
                        deal_type2match_result[ult_dt] = pre_mr
                        repl_dt_dict[repl_dt] = ult_dt
                else:
                    repl_dt_dict[repl_dt] = dt
                    deal_type2match_result[dt] = [mr]
        
        # 尝试将引用交易类型转为实际交易类型
        for mr in refer_dt_match_results:
            tmp_dt = None
            if len(deal_type2match_result) == 1:
                tmp_dt = list(deal_type2match_result.keys())[0]
            # 找出与之最近的并且在前面的real_dt
            else:
                if mr in match_result:
                    mpos = match_result.index(mr)
                    pos_diff = 100
                    for dt, omr in deal_type2match_result.items():
                        if mr in match_result:
                            mpos = match_result.index(mr)
                            opos = match_result.index(omr[0])
                            pd = (mpos - opos)
                            if pd <= pos_diff and pd >= 0:
                                pos_diff = pd
                                tmp_dt = dt
            if tmp_dt:
                mr["deal_type"] = tmp_dt
                deal_type2match_result[tmp_dt].append(mr)
        
        # 处理“融资”这种漂浮不定的类型
        if len(deal_type2match_result) == 1:
            dt = list(deal_type2match_result.keys())[0]
            for mr in swing_dt_match_results:
                mr["deal_type"] = dt
                deal_type2match_result[dt].append(mr)
        else:
            deal_type2match_result["融资"] = swing_dt_match_results
        res = []
        for dt, mr in deal_type2match_result.items():
            res += mr
        return res
