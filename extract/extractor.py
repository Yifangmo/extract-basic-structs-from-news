#!/usr/bin/env python
"""
基础结构体抽取器，将句子经过处理变成实体句子，并依据传进来的rules与实体句子所匹配的结果生成基础结构体
"""
from .reqner import get_ner_predict
from extract.extractor_funcs import *
from .labelstr import *
import re

class DictExtractor(object):
    def __init__(self, *rules):
        self.label_related_party = LABEL_RELATED_PARTY
        self.label_amount = LABEL_AMOUNT
        self.label_attr_noun = LABEL_ATTR_NOUN
        self.label_occ_date = LABEL_OCCURRENCE_DATE
        self.label_dcs_date = LABEL_DISCLOSE_DATE
        self.label_deal_type = LABEL_DEAL_TYPE
        self.label_business_prof = LABEL_BUSINESS_PROF
        self.__label_str_map = {
            LABEL_RELATED_PARTY: "<关联方>",
            LABEL_AMOUNT: "<金额>",
            LABEL_ATTR_NOUN: "<属性名词>",
            LABEL_OCCURRENCE_DATE: "<发生时间>",
            LABEL_DISCLOSE_DATE: "<披露时间>",
            LABEL_DEAL_TYPE: "<交易类型>",
            LABEL_BUSINESS_PROF: "<融资方标签>"
        }
        self.__validate_deal_type_reobj = re.compile(
            (
                r"(((pre-)?[A-H]\d?(\++|＋+|plus)?)|天使|种子|战略|新一|IPO)(轮|系列轮|系列(?!轮))((?![融投增]资|投融资)|([融投增]资|投融资)(?!人|者|方|机构))|"
                r"(上一?|首|两|三|四|五)轮((?![融投增]资|投融资)|(([融投增]资|投融资)(?!人|者|方|机构)))|"
                r"(天使|种子|战略|风险|IPO|股权|新一|上一|(新一|上一?|首|两|三|四|五)次)([融投增]资|投融资)(?!人|者|方|机构)|"
                r"(本|此|该)(轮|次)([融投增]资|投融资)?|"
                # r"(本|此|该)(轮|次)(?=的?(领投|跟投|参投))|"
                r"[融投增]资(?!人|者|方|机构)"
            ), re.I
        )
        self.__secondary_deal_type_reobj = re.compile(
            (
                r"((pre-)?[A-H]\d?(\++|＋+|plus)?|天使|种子|战略|新一|IPO)(轮|系列轮|系列)([融投增]资|投融资)?|"
                r"(天使|种子|战略|风险|IPO|股权|新一|上一|(新一|上一?|首|两|三|四|五)次)([融投增]资|投融资)?"
            ), re.I
        )
        self.__invalid_repl_dt_reobj = re.compile(r"两|三|四|五|(?<![a-zA-Z])\d")
        self.__repl_deal_type_reobj = re.compile(r"(轮|次|笔|轮战略|系列轮?)?(投资|融资)|投融资")
        self.__english_name_reobj = re.compile(r"([A-Za-z\d]{3,}(?:\s[A-Za-z\d]+)*)")
        self.__noalias_reobj = re.compile(r"隶属|领投|估值|股票代码|报道|有限合伙")
        self.__alias_token_reobj = re.compile(r"(?:简称|英文名|下称)：?")
        self.__date_reobj = re.compile(r"(?<!\d)\d{1,2}月(\d{1,2}日)?|(?<!\d)\d{1,4}年(\d{1,2}月(\d{1,2}日)?)?")
        self.__verb_reobj = re.compile(r"获|完成")
        self.__rules = rules
        
    def __call__(self, sent, sent_ctx: dict=None):
        sent = normalize_sentence(sent)
        resp = get_ner_predict(sent)
        if resp["error_message"] or not "labels_indexes" in resp["response"]:
            print(resp["error_message"], ": ", sent)
            return
        labels_indexes = resp["response"]["labels_indexes"]
        sentence_struct_info = {
            "match_results": [],
            "sent": sent,
            "labels_indexes": labels_indexes,
            "labels_value": [[sent[li[0]:li[1]], li[2]] for li in labels_indexes],
            "sent_ctx": sent_ctx
        }

        # 验证deal_type实体的有效性，将错误的或无用的deal_type实体去除
        self.__validate_deal_type(sentence_struct_info)
        
        # 验证deal_tate实体的有效性，修正或去除缺漏的deal_date实体
        self.__validate_deal_date(sentence_struct_info)
        
        # 实际交易类型到交易类型实体spans（可能一个实际交易类型对应多个交易类型实体）的映射
        self.__get_real_dt2label_dts(sentence_struct_info)

        # 获取子句index_span到实际交易类型的映射
        self.__get_dt_span_dict(sentence_struct_info)
        
        # 获取子句index_span(索引范围)到date的映射，优先更准确的时间
        self.__get_date_span_dict(sentence_struct_info)

        # 将句子转为实体句子
        self.__get_entities_sent(sentence_struct_info)
        
        entities_sent, attr_noun_dict = sentence_struct_info["entities_sent"], sentence_struct_info["attr_noun_dict"]
        match_results = []
        # 用不同的模板匹配实体句子，获取字段到实际值对应在实体句子的index_span的映射
        for func in self.__rules:
            match_results += func(entities_sent, attr_noun_dict)
        sentence_struct_info["match_results"] = match_results
        # print("match_results: ", match_results)
        
        # match_results中获取fc信息
        self.__get_fc_info_span_dict(sentence_struct_info)

        # 将实际值对应的在实体句子上的index_span转为实际值
        self.__adjust_field(sentence_struct_info)
        
        # 获取未使用的标签信息
        self.__get_labels_unused(sentence_struct_info)
        
        del sentence_struct_info["attr_noun_dict"], sentence_struct_info["original_index2entities"], sentence_struct_info["entities_index2original"]
        
        return sentence_struct_info
    
    def get_match_results(self, sent):
        sentence_struct_info = self(sent)
        structs = []
        for mr in sentence_struct_info["match_results"]:
            structs.append(mr["struct"])
        return structs

    def __validate_deal_type(self, sentence_struct_info: dict):
        sent, labels_indexes = sentence_struct_info["sent"], sentence_struct_info["labels_indexes"]
        new_labels_indexes, labels_unused = [], []
        
        for i, li in enumerate(labels_indexes):
            label_content = sent[li[0]:li[1]]
            clause_span = get_clause_span(sent, li[0], li[1])
            if li[2] != self.label_deal_type:
                if li[2] == self.label_business_prof:
                    # 信宸资本完成对电动车充电产品企业Intramco的战略投资
                    if "对" in sent[clause_span[0]:li[0]]:
                        new_labels_indexes.append(li)
                        continue
                    # 钱币鉴定企业“公博评级”获国风文化电商平台“玩物得志App”千万元A轮战略投资
                    if "获" in sent[clause_span[0]:li[0]]:
                        labels_unused.append([label_content, li[2]])
                        continue
                    # Despegar还宣布与总部位于阿布扎比的投资公司Waha Capital达成协议
                    if i > 0:
                        j = i - 1
                        invalid = False
                        while j >= 0:
                            if labels_indexes[j][0] >= clause_span[0] and labels_indexes[j][2] == self.label_related_party:
                                invalid = True
                                break
                            if labels_indexes[j][0] < clause_span[0]:
                                break
                            j -= 1
                        if invalid:
                            labels_unused.append([label_content, li[2]])
                            continue
                new_labels_indexes.append(li)
                continue

            if not self.__validate_deal_type_reobj.search(re.sub(r"\s","", label_content)):
                labels_unused.append([label_content, li[2]])
                continue
            
            # 该公司成立以来获得的第三次融资(无用)
            if label_content.startswith("第") and not "获" in sent[clause_span[0]:li[0]]:
                labels_unused.append([label_content, li[2]])
                continue
            
            # 此轮本来只打算融资6000-8000万美元
            if re.match(r"融资|投资", label_content) and i+1 < len(labels_indexes) and labels_indexes[i+1][0] == li[1] and labels_indexes[i+1][2] == "金额":
                labels_unused.append([label_content, li[2]])
                continue
            
            clause_pos_span = get_clause_span(sent, li[0], li[1])
            # 本轮融资由深圳高新投战略投资(无用)
            if label_content.endswith("投资") and not self.__verb_reobj.search(sent, clause_pos_span[0], li[0]):
                labels_unused.append([label_content, li[2]])
                continue
            
            # 继2018年完成2.4亿A轮、2019年3月完成20亿人民币B轮、2020年8月和10月分别完成25亿人民币C轮和战略融资后(有用)
            # 这是继去年Pre-A轮以及今年4月A轮之后(无用)
            if "继" in sent[clause_pos_span[0]:li[0]] and "后" in sent[li[1]:clause_pos_span[1]]:
                isunuse = True
                for j in range(i, -1, -1):
                    if labels_indexes[j][0] < clause_pos_span[0]:
                        break
                    if labels_indexes[j][2] == self.label_amount:
                        isunuse = False
                        break
                if isunuse:
                    labels_unused.append([label_content, li[2]])
                else:
                    new_labels_indexes.append(li)
                continue
            
            new_labels_indexes.append(li)
        sentence_struct_info["labels_indexes"], sentence_struct_info["labels_unused"] = new_labels_indexes, labels_unused
    
    def __validate_deal_date(self, sentence_struct_info: dict):
        sent, labels_indexes = sentence_struct_info["sent"], sentence_struct_info["labels_indexes"]
        new_labels_indexes, labels_unused = [], []
        for li in labels_indexes:
            label_content = sent[li[0]:li[1]]
            if li[2] == self.label_dcs_date or li[2] == self.label_occ_date:
                cl_span = get_clause_span(sent, li[0], li[1])
                matches = self.__date_reobj.finditer(sent, cl_span[0], cl_span[1])
                for m in matches:
                    sp = m.span()
                    if sp[0]<=li[0] and sp[1]>=li[1]:
                        li[0], li[1]= sp[0], sp[1]
                        break
                if li[1] - li[0] > 1:
                    new_labels_indexes.append(li)
                else:
                    labels_unused.append([label_content, li[2]])
            else:
                new_labels_indexes.append(li)
        sentence_struct_info["labels_indexes"], sentence_struct_info["labels_unused"] = new_labels_indexes, labels_unused

    def __get_real_dt2label_dts(self, sentence_struct_info: dict):
        """
        获取实际交易类型到交易类型实体spans的映射（可能一个实际交易类型对应多个交易类型实体）、交易类型实体与金额对
        """
        sent, labels_indexes = sentence_struct_info["sent"], sentence_struct_info["labels_indexes"]
        real_dt2label_dts, dt_amount_pair, total_labels_used = {}, {}, set({})

        # 标签交易类型到替换后交易类型, 替换后交易类型到实际交易类型
        label_dt2repl_dt, repl_dt2real_dt = {}, {}
        for i, li in enumerate(labels_indexes):
            label_content = sent[li[0]:li[1]]
            if li[2] == LABEL_DEAL_TYPE:
                repl_dt = self.__repl_deal_type_reobj.sub("", label_content)
                # 此类交易类型实体只用于匹配模板来获取融资方信息，不作为实际交易事件，也不为之划分span
                if self.__invalid_repl_dt_reobj.search(repl_dt):
                    continue
                # 励销云宣布完成新一轮2000万美元B轮融资
                if i > 1 and labels_indexes[i-1][2]==LABEL_AMOUNT and labels_indexes[i-2][2]==LABEL_DEAL_TYPE:
                    pre_label_dt_content = sent[labels_indexes[i-2][0]:labels_indexes[i-2][1]]
                    pre_li_span = (labels_indexes[i-2][0], labels_indexes[i-2][1])
                    if pre_li_span in label_dt2repl_dt:
                        pre_repl_dt = label_dt2repl_dt[pre_li_span]
                        del label_dt2repl_dt[pre_li_span]
                        total_labels_used.add(pre_li_span)
                        # 新一轮2000万美元B轮融资
                        if re.search(r"[A-Za-z]", repl_dt):
                            # 将原有的 新一 替换为 B
                            label_dt2repl_dt[(li[0],li[1])] = repl_dt
                            # 删除原有的repl_dt，避免同一交易事件（real_dt）有多个repl_dt
                            del repl_dt2real_dt[pre_repl_dt]
                            # 将实际交易类型由新一轮替换为B轮融资
                            if label_content.endswith("融资") or not pre_label_dt_content.endswith("融资"):
                                repl_dt2real_dt[repl_dt] = label_content
                        # B轮2000万美元新融资 | B轮2000万美元融资
                        else:
                            label_dt2repl_dt[(li[0],li[1])] = pre_repl_dt
                            # 将实际交易类型由B轮替换为B轮融资
                            if label_content.endswith("融资") and not pre_label_dt_content.endswith("融资"):
                                repl_dt2real_dt[pre_repl_dt] = pre_label_dt_content + label_content
                        continue
                # "B+轮战略融资" 和 "B+轮投资"
                if repl_dt in repl_dt2real_dt:
                    label_dt2repl_dt[(li[0], li[1])] = repl_dt
                    pre_real_dt = repl_dt2real_dt[repl_dt]
                    ult_real_dt = label_content
                    # 优先取融资结尾的，再取长度更长的
                    if pre_real_dt.endswith("融资"):
                        ult_real_dt = pre_real_dt
                    if pre_real_dt != label_content:
                        if label_content.endswith("融资") and len(pre_real_dt) < len(label_content):
                            ult_real_dt = label_content
                    else:
                        if len(pre_real_dt) >= len(label_content):
                            ult_real_dt = pre_real_dt
                    if ult_real_dt != pre_real_dt:
                        repl_dt2real_dt[repl_dt] = ult_real_dt
                    continue
                
                if i > 0 and labels_indexes[i-1][2]==LABEL_AMOUNT and li[0] - labels_indexes[i-1][1] < 2:
                    dt_amount_pair[(li[0],li[1])] = (labels_indexes[i-1][0],labels_indexes[i-1][1])
                
                label_dt2repl_dt[(li[0], li[1])] = repl_dt
                repl_dt2real_dt[repl_dt] = label_content
        
        for label_dt, repl_dt in label_dt2repl_dt.items():
                real_dt = repl_dt2real_dt[repl_dt]
                if real_dt not in real_dt2label_dts:
                    real_dt2label_dts[real_dt] = [label_dt]
                else:
                    real_dt2label_dts[real_dt].append(label_dt)
        
        sentence_struct_info["real_dt2label_dts"], sentence_struct_info["dt_amount_pair"], sentence_struct_info["total_labels_used"] = real_dt2label_dts, dt_amount_pair, total_labels_used

    def __get_dt_span_dict(self, sentence_struct_info: dict):
        """返回clause_idx_span到实际交易事件和时间的映射

        Args:
            sentence_struct_info (dict): [description]
        """
        sent, labels_indexes, sent_ctx = sentence_struct_info["sent"], sentence_struct_info["labels_indexes"], sentence_struct_info["sent_ctx"]
        # 实际交易类型到交易类型实体spans（可能一个实际交易类型对应多个交易类型实体）的映射
        real_dt2label_dts = sentence_struct_info["real_dt2label_dts"]
        
        # 金额与交易类型pair
        dt_amount_pair = sentence_struct_info["dt_amount_pair"]
        
        clause_span2real_dts = {(0, len(sent)): list(real_dt2label_dts)}
        
        if len(real_dt2label_dts) > 0:
            separators = ["；", "，", "、", "及"]
            # 划分span为尽可能小单位，以尽可能使得每个span最多只有一个real_dt，最小的单位为"、"分割的短句的span
            clause_span2real_dts = divide_real_dts_span(sent, clause_span2real_dts, real_dt2label_dts, separators)
        # 使前面未被span覆盖的时间标签被其后面的dt_span覆盖，因为前面的时间很大可能是其后real_dt相关的时间
        forward_extend_dtspan(sent, labels_indexes, clause_span2real_dts)
        
        # 向后扩展span，使所有span邻接，合并以"、"、"及"分割但无金额的span
        backward_extend_dtspan(sent, clause_span2real_dts, real_dt2label_dts, dt_amount_pair)
        print("="*50)
        print("sent: ", sent)
        print("sent_ctx", sent_ctx)
        print("pre clause_span2real_dts: ", clause_span2real_dts)
        
        # 将real_dt转为由str转为(span[0], span[1], str)的形式
        clause_spans = clause_span2real_dts.keys()
        for cl_span in clause_spans:
            real_dts = clause_span2real_dts[cl_span]
            new_real_dts = []
            for real_dt in real_dts:
                label_dts = real_dt2label_dts[real_dt]
                for label_dt in label_dts:
                    if cl_span[0] <= label_dt[0] and cl_span[1] >= label_dt[1]:
                        new_real_dts.append((label_dt[0], label_dt[1], real_dt))
                        break
            clause_span2real_dts[cl_span] = new_real_dts
        
        # 对无交易类型的情况添加句子上下文sent_ctx里的交易类型
        if len(clause_span2real_dts) == 1:
            first_span = next(iter(clause_span2real_dts))
            if len(clause_span2real_dts[first_span]) == 0:
                # 有就填交易类型
                if sent_ctx and "deal_type" in sent_ctx:
                    clause_span2real_dts[first_span].append((-1,-1,sent_ctx["deal_type"]))
                # 无就从属性名词找交易类型
                else:
                    # TODO
                    for li in labels_indexes:
                        label_content = sent[li[0]:li[1]]
                        if li[2] == self.label_attr_noun:
                            match = self.__secondary_deal_type_reobj.search(label_content)
                            if match:
                                sp = match.span()
                                clause_span2real_dts[first_span] = [(sp[0], sp[1], match.group())]
                                break
        # 根据span排序重新生成dict
        clause_span2real_dts = {i[0]:i[1] for i in sorted(clause_span2real_dts.items())}
        
        sentence_struct_info["clause_span2real_dts"], sentence_struct_info["real_dt2label_dts"] = clause_span2real_dts, real_dt2label_dts

    def __get_date_span_dict(self, sentence_struct_info: dict):
        """生成span到date的映射，优先更准确的时间，每个span对应于交易类型的span

        Args:
            sentence_struct_info (dict): [句子结构化信息]
        """
        sent = sentence_struct_info["sent"]
        labels_indexes = sentence_struct_info["labels_indexes"]
        clause_span2real_dts = sentence_struct_info["clause_span2real_dts"]
        clause_span2dates = {}
        for i, li in enumerate(labels_indexes):
            if li[2] == self.label_dcs_date:
                label_content = sent[li[0]:li[1]]
                for span in clause_span2real_dts:
                    if li[0] >= span[0] and li[1] <= span[1]:
                        if span not in clause_span2dates:
                            clause_span2dates[span] = {}
                        if "disclosed_dates" not in clause_span2dates[span]:
                            clause_span2dates[span]["disclosed_dates"] = [(li[0],li[1])]
                        else:
                            pre_span = clause_span2dates[span]["disclosed_dates"][0]
                            pre = sent[pre_span[0]:pre_span[1]]
                            if not self.__date_reobj.search(pre):
                                clause_span2dates[span]["disclosed_dates"][0] = (li[0],li[1])
                            elif self.__date_reobj.search(label_content):
                                clause_span2dates[span]["disclosed_dates"].append((li[0],li[1]))
            if li[2] == self.label_occ_date:
                label_content = sent[li[0]:li[1]]
                for span in clause_span2real_dts:
                    if li[0] >= span[0] and li[1] <= span[1]:
                        if span not in clause_span2dates:
                            clause_span2dates[span] = {}
                        if "occurrence_dates" not in clause_span2dates[span]:
                            clause_span2dates[span]["occurrence_dates"] = [(li[0],li[1])]
                        else:
                            pre_span = clause_span2dates[span]["occurrence_dates"][0]
                            pre = sent[pre_span[0]:pre_span[1]]
                            if not self.__date_reobj.search(pre):
                                clause_span2dates[span]["occurrence_dates"][0] = (li[0],li[1])
                            elif self.__date_reobj.search(label_content):
                                clause_span2dates[span]["occurrence_dates"].append((li[0],li[1]))
        sentence_struct_info["clause_span2dates"] = clause_span2dates

    def __get_entities_sent(self, sentence_struct_info: dict):
        sent = sentence_struct_info["sent"]
        labels_indexes = sentence_struct_info["labels_indexes"]
        # 子句原索引范围到实际交易类型的映射
        clause_span2real_dts = sentence_struct_info["clause_span2real_dts"]
        # 子句原索引范围到日期信息的映射
        clause_span2dates = sentence_struct_info["clause_span2dates"]
        
        entities_sent, entities_index2original, alias, attr_noun_dict, original_index2entities = "", {}, {}, {}, {}
        # 标签替换前后首索引差值
        replaced_list = []
        idx_diff = 0
        start = 0
        
        # 将sent的span转为entities_sent的span，ori为original
        ori_spans = list(clause_span2real_dts.keys())
        new_spans = []
        ori_spans_idx = 0
        span_start_diff = 0
        span_start = ori_spans[ori_spans_idx][0]
        span_end = ori_spans[ori_spans_idx][1]
        
        for i, label in enumerate(labels_indexes):
            label_content = sent[label[0]:label[1]]
            replaced_list.append(sent[start:label[0]])
            
            # 将sent的span转为entities_sent的span
            while label[0] >= span_end:
                new_span_start = span_start + span_start_diff
                new_span_end = span_end + idx_diff
                new_spans.append((new_span_start, new_span_end))
                ori_spans_idx += 1
                if ori_spans_idx == len(ori_spans):
                    break
                span_start = ori_spans[ori_spans_idx][0]
                span_end = ori_spans[ori_spans_idx][1]
                pass
            # 更新新旧span的start值的差值
            if label[1] >= span_start and i > 0 and labels_indexes[i - 1][1] < span_start:
                span_start_diff = idx_diff
            # 生成标签索引映射
            label_start_idx = label[0]+idx_diff
            label_length = len(self.__label_str_map[label[2]])
            entities_index2original[(label_start_idx, label_start_idx + label_length)] = (label[0], label[1])
            original_index2entities[(label[0], label[1])] = (label_start_idx, label_start_idx + label_length)
            idx_diff += (label_length - (label[1] - label[0]))
            # 替换为标签
            replaced_list.append(self.__label_str_map[label[2]])
            start = label[1]
            
            # 生成属性名词span到origin str的dict
            if label[2] == self.label_attr_noun:
                attr_noun_dict[(label_start_idx, label_start_idx + label_length)] = label_content
                continue
            # 去除融资方标签和关联方标签之间的任何字符
            if label[2] == self.label_business_prof and (i + 1) < len(labels_indexes) and labels_indexes[i + 1][2] == "关联方":
                idx_diff -= (labels_indexes[i + 1][0] - start)
                start = labels_indexes[i + 1][0]
                continue
            # 处理关联方后的括号内别名
            if label[2] == self.label_related_party:
                related_party = sent[label[0]:label[1]]
                alias[related_party] = {related_party}
                if start < len(sent) and sent[start] == "（":
                    end = sent.find("）", start)
                    # 排除一些情况，包括括号内有实体的情况
                    if end == -1 or self.__noalias_reobj.search(sent[start+1:end]) or\
                        (i + 1) < len(labels_indexes) and labels_indexes[i+1][1] <= end:
                        continue
                    m = self.__alias_token_reobj.search(sent, start+1, end)
                    # “简称|英文名：”后是别名，若无则默认括号内都是别名
                    s = m.end() if m else start+1
                    als = {sent[s:end]}
                    # 处理简称前可能有英文名的情况
                    e = m.start() if m else end
                    m = self.__english_name_reobj.search(sent, start+1, e)
                    if m:
                        als.add(sent[m.start():m.end()])
                    alias[related_party] |= als
                    # 移除括号及其内容，方便后续模板设计
                    idx_diff -= (end + 1 - start)
                    start = end + 1
        
        replaced_list.append(sent[start:])
        new_span_start = span_start + span_start_diff
        new_span_end = span_end + idx_diff
        new_spans.append((new_span_start, new_span_end))
        new_clause_span2real_dts = {i[1]: clause_span2real_dts[i[0]] for i in zip(ori_spans, new_spans)}
        new_clause_span2dates = {i[1]: clause_span2dates[i[0]] for i in zip(ori_spans, new_spans) if i[0] in clause_span2dates}
        sentence_struct_info["clause_span2real_dts"], sentence_struct_info["clause_span2dates"] = new_clause_span2real_dts, new_clause_span2dates
        
        entities_sent = "".join(replaced_list)
        # 将之前的使用过的标签在原句子的索引转为实体句子的索引
        sentence_struct_info["total_labels_used"] = {original_index2entities[i] for i in sentence_struct_info["total_labels_used"]}
        print("entities_sent: ", entities_sent)
        sentence_struct_info["entities_sent"], sentence_struct_info["entities_index2original"], sentence_struct_info["original_index2entities"], sentence_struct_info["alias"], sentence_struct_info["attr_noun_dict"] = entities_sent, entities_index2original, original_index2entities, alias, attr_noun_dict
    
    def __get_fc_info_span_dict(self, sentence_struct_info):
        """
        从match_results中获取fc信息，先后按有deal_type且离deal_type最近的、有business_profile的、sent_ctx优先级来选择
        """
        # 子句的index_span到实际交易类型的映射
        clause_span2real_dts = sentence_struct_info["clause_span2real_dts"]
        # 原句子
        sent = sentence_struct_info["sent"]
        # 别名信息
        alias = sentence_struct_info["alias"]
        # 模板匹配结果
        match_results = sentence_struct_info["match_results"]
        # 实体句子实体index_span到原句子index_span的映射
        entities_index2original = sentence_struct_info["entities_index2original"]
        # 句子的上下文信息，里面有交易类型和融资方信息
        sent_ctx = sentence_struct_info["sent_ctx"]
        # 使用过的标签idx_span集合
        total_labels_used = set({})
        
        # 获取交易类型在实体句子的索引范围
        clause_span2fc_info = {}

        fc_span2fc_info = {}
        for mr in match_results:
            mr_struct = mr["struct"]
            if "financing_company" in mr_struct:
                fc_span = mr_struct["financing_company"]
                ori_fc_span = entities_index2original[fc_span]
                del mr_struct["financing_company"]
                total_labels_used.add(fc_span)
                fc_name = get_field_value(sent, entities_index2original, fc_span)
                fc_names = get_classified_alias(alias[fc_name])
                fc = {}
                for k, v in fc_names.items():
                    fc[k] = v
                bp = None
                if "business_profile" in mr_struct:
                    bp_span = mr_struct["business_profile"]
                    del mr_struct["business_profile"]
                    total_labels_used.add(bp_span)
                    bp = get_field_value(sent, entities_index2original, bp_span)
                fc_span2fc_info[ori_fc_span] = {"business_profile": bp, "financing_company": fc} if bp else {"financing_company": fc}
        
        for cl_span, real_dts in clause_span2real_dts.items():
            if len(real_dts) > 0:
                # 只取第一个
                real_dt_ori_span = real_dts[0][0:2]
                if real_dt_ori_span == (-1,-1):
                    if sent_ctx and "fc_name" in sent_ctx and sent_ctx["fc_name"]:
                        fc_info = {"financing_company": {"primary_name": sent_ctx["fc_name"]}}
                        clause_span2fc_info[cl_span] = {"fc_info": fc_info, "fc_span": (-1,-1)}
                    break
                fc_spans = list(fc_span2fc_info)
                for fc_span in fc_spans:
                    fc_info = fc_span2fc_info[fc_span]
                    fc_name = fc_info["financing_company"]["primary_name"]
                    if cl_span[0] <= fc_span[0] and cl_span[1] >= fc_span[1]:
                        del fc_span2fc_info[fc_span]
                        if cl_span not in clause_span2fc_info:
                            clause_span2fc_info[cl_span] = {"fc_info": fc_info, "fc_span": fc_span}
                        elif not re.match(r"[本此该]?公司", fc_name):
                            pre_fc_info = clause_span2fc_info[cl_span]
                            pre_fc_span = pre_fc_info["fc_span"]
                            # 取离交易类型更近的融资方信息
                            if min(abs(real_dt_ori_span[0] - fc_span[1]), abs(real_dt_ori_span[1] - fc_span[0])) < \
                                min(abs(real_dt_ori_span[0] - pre_fc_span[1]), abs(real_dt_ori_span[1] - pre_fc_span[0])):
                                clause_span2fc_info[cl_span] = {"fc_info": fc_info, "fc_span": fc_span}
        # 向后或者向前扩展span
        if len(clause_span2real_dts) > 1 and len(clause_span2fc_info) > 0:
            cl_spans = clause_span2real_dts.keys()
            pre_fc_info = list(clause_span2fc_info.values())[0]
            for cl_span in cl_spans:
                if cl_span not in clause_span2fc_info:
                        clause_span2fc_info[cl_span] = pre_fc_info
                else:
                    pre_fc_info = clause_span2fc_info[cl_span]
        print("clause_span2fc_info: ", clause_span2fc_info)
        sentence_struct_info["clause_span2fc_info"], sentence_struct_info["total_labels_used"] = clause_span2fc_info, total_labels_used

    # 填充deal_type，对dates分类，处理关联方别名，统计标签使用情况
    def __adjust_field(self, sentence_struct_info):
        # 原句子
        sent = sentence_struct_info["sent"]
        # 子句的index_span到实际交易类型的映射
        clause_span2real_dts = sentence_struct_info["clause_span2real_dts"]
        # 子句的index_span到融资方信息的映射
        clause_span2fc_info = sentence_struct_info["clause_span2fc_info"]
        print("clause_span2real_dts: ", clause_span2real_dts)
        print("="*50)
        # 子句的index_span到日期信息的映射
        clause_span2dates = sentence_struct_info["clause_span2dates"]
        # 实际交易类型到交易类型实体的映射，统计已使用的交易类型标签时使用
        real_dt2label_dts = sentence_struct_info["real_dt2label_dts"]
        # 模板匹配结果
        match_results = sentence_struct_info["match_results"]
        # 实体句子的实体index_span到原句子index_span的映射
        entities_index2original = sentence_struct_info["entities_index2original"]
        # 原句子实体index_span到实体句子index_span的映射
        original_index2entities = sentence_struct_info["original_index2entities"]
        # 别名信息
        alias = sentence_struct_info["alias"]
        # 使用过的标签idx_span集合
        total_labels_used = sentence_struct_info["total_labels_used"]
        
        new_match_results = []
        # 填充每个match_results对应的deal_type和日期信息，并将结构体的span字段值替换为实际值
        for mr in match_results:
            mr_struct = mr["struct"]
            mr_span = mr["match_span"]
            for cl_span, real_dts in clause_span2real_dts.items():
                if cl_span[0] <= mr_span[0] and mr_span[1] <= cl_span[1]:
                    # TODO if len(real_dts) == 0 的情况
                    
                    financing_company_info = clause_span2fc_info[cl_span]["fc_info"] if cl_span in clause_span2fc_info else None
                    for real_dt in real_dts:
                        # 新的match_results_struct
                        nmr_struct = {}
                        nmr = {"struct": nmr_struct,"from_rule": mr["from_rule"]}
                        # 添加使用过的deal_type和date标签以及填充date
                        if real_dt[2] in real_dt2label_dts:
                            for label_dt in real_dt2label_dts[real_dt[2]]:
                                total_labels_used.add(original_index2entities[label_dt])
                        nmr_struct["deal_type"] = real_dt[2]
                        if cl_span in clause_span2dates:
                            for field_name, date_spans in clause_span2dates[cl_span].items():
                                date_span = date_spans[0]
                                nmr_struct[field_name] = sent[date_span[0]:date_span[1]]
                                total_labels_used.add(original_index2entities[date_span])
                        
                        # 如果有融资方信息就填充
                        if financing_company_info:
                            for k, v in financing_company_info.items():
                                nmr_struct[k] = v
                                
                        # 如果只有一个real_deal_type，意味着其他信息可区分，继续填充其他信息
                        if len(real_dts) == 1:
                            for k, v in mr_struct.items():
                                if isinstance(v, tuple):
                                    total_labels_used.add(v)
                                    # 跳过属性名词不填
                                    if k != "attr_noun":
                                        nmr_struct[k] = get_field_value(sent, entities_index2original, v)
                                # 填充投资方信息（多个）
                                elif k == "investors":
                                    total_labels_used.update(v)
                                    investors = []
                                    is_leading_investor = mr_struct["is_leading_investor"] if "is_leading_investor" in mr_struct else False
                                    i_names = get_field_value(sent, entities_index2original, v)
                                    for i_name in i_names:
                                        investor = {}
                                        # 获取全名、别名信息
                                        names = get_classified_alias(alias[i_name])
                                        for k, v in names.items():
                                            investor[k] = v
                                        investor["is_leading_investor"] = is_leading_investor
                                        investors.append(investor)
                                    nmr_struct["investors"] = investors
                                elif k == "financial_advisers":
                                    total_labels_used.update(v)
                                    financial_advisers = get_field_value(sent, entities_index2original, v)
                                    nmr_struct["financial_advisers"] = financial_advisers
                        new_match_results.append(nmr)
                        
        sentence_struct_info["total_labels_used"] = total_labels_used
        sentence_struct_info["match_results"] = new_match_results
        return

    def __get_labels_unused(self, sentence_struct_info):
        # 原句子
        sent = sentence_struct_info["sent"]
        # 实体句子
        entities_sent = sentence_struct_info["entities_sent"]
        # 实体句子实体index_span到原句子index_span的映射
        entities_index2original = sentence_struct_info["entities_index2original"]
        total_labels = set(entities_index2original.keys())
        total_labels_used = sentence_struct_info["total_labels_used"]
        
        total_labels_unused = total_labels - total_labels_used
        labels_unused = sentence_struct_info["labels_unused"]
        for i in sorted(total_labels_unused):
            if i in entities_index2original:
                sent_index = entities_index2original[i]
                labels_unused.append([sent[sent_index[0]:sent_index[1]], entities_sent[i[0]+1:i[1]-1]])
            else:
                print("实体索引映射错误：({},{})".format(i[0], i[1]))
        sentence_struct_info["labels_unused"]=labels_unused
        sentence_struct_info["labels_unused_count"] = len(labels_unused)