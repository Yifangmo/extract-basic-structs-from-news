#!/usr/bin/env python
"""从句子中抽取出多个与模板匹配的结构体
"""
from ..reqner import get_ner_predict
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
        self.label_str_map = {
            LABEL_RELATED_PARTY: "<关联方>",
            LABEL_AMOUNT: "<金额>",
            LABEL_ATTR_NOUN: "<属性名词>",
            LABEL_OCCURRENCE_DATE: "<发生时间>",
            LABEL_DISCLOSE_DATE: "<披露时间>",
            LABEL_DEAL_TYPE: "<交易类型>",
            LABEL_BUSINESS_PROF: "<融资方标签>"
        }
        self.validate_deal_type_reobj = re.compile(
            (
                r"(((pre-)?[A-H]\d?(\++|＋+|plus)?)|天使|种子|战略|新一|IPO)(轮|系列轮|系列(?!轮))((?![融投]资|投融资)|([融投]资|投融资)(?!人|者|方|机构))|"
                r"(上一?|首|两|三|四|五)轮((?![融投]资|投融资)|(([融投]资|投融资)(?!人|者|方|机构)))|"
                r"(天使|种子|战略|风险|IPO|股权|新一|上一|(新一|上一?|首|两|三|四|五)次)([融投]资|投融资)(?!人|者|方|机构)|"
                r"(本|此|该)(轮|次)([融投]资|投融资)|"
                r"(本|此|该)(轮|次)(?=的?(领投|跟投|参投))|"
                r"[融投]资(?!人|者|方|机构)"
            ), re.I
        )
        self.invalid_repl_dt_reobj = re.compile(r"两|三|四|五|(?<![a-zA-Z])\d")
        self.repl_deal_type_reobj = re.compile(r"(轮|次|笔|轮战略|系列轮?)?(投资|融资)|投融资")
        self.english_name_reobj = re.compile(r"([A-Za-z\d]{3,}(?:\s[A-Za-z\d]+)*)")
        self.noalias_reobj = re.compile(r"隶属|领投|估值|股票代码")
        self.alias_token_reobj = re.compile(r"(?:简称|英文名|下称)：?")
        self.date_reobj = re.compile(r"\d{1,2}月\d{1,2}日|年\d{1,2}月")
        self.verb_reobj = re.compile(r"获|完成")
        self.rules = rules
        
    def __call__(self, sent):
        sent = normalize_sentence(sent)
        resp = get_ner_predict(sent)
        if resp["error_message"] or not "labels_indexes" in resp["response"]:
            print(resp["error_message"], ": ", sent)
            return
        labels_indexes = resp["response"]["labels_indexes"]
        sentence_struct_info = {
            "match_result": [],
            "sent": sent,
            "labels_indexes": labels_indexes,
            "labels_value": [[sent[li[0]:li[1]], li[2]] for li in labels_indexes]
        }

        # 验证deal_type实体的有效性，将错误的或无用的deal_type实体去除
        self.validate_deal_type(sentence_struct_info)

        # 获取子句index_span到实际交易类型的映射
        self.get_dtspan_dict(sentence_struct_info)
        
        # 生成span到date的映射，优先更准确的时间
        self.get_date_span_dict(sentence_struct_info)

        # 将句子转为实体句子
        self.get_entities_sent(sentence_struct_info)
        
        entities_sent, attr_noun_dict = sentence_struct_info["entities_sent"], sentence_struct_info["attr_noun_dict"]
        match_result = []
        # 用不同的模板匹配实体句子，获取字段到实际值对应在实体句子的index_span的映射
        for func in self.rules:
            match_result += func(entities_sent, attr_noun_dict)
        sentence_struct_info["match_result"] = match_result
        print("match_result: ", match_result)

        # 将实际值对应的在实体句子上的index_span转为实际值
        self.adjust_field(sentence_struct_info)
        
        # 获取未使用的标签信息
        self.get_labels_unused(sentence_struct_info)
        
        del sentence_struct_info["attr_noun_dict"], sentence_struct_info["original_index2entities"], sentence_struct_info["entities_index2original"]
        
        return sentence_struct_info
                  
    def validate_deal_type(self, sentence_struct_info: dict):
        sent, labels_indexes = sentence_struct_info["sent"], sentence_struct_info["labels_indexes"]
        new_labels_indexes, labels_unused = [], []
        
        for i, li in enumerate(labels_indexes):
            label_content = sent[li[0]:li[1]]
            if li[2] != self.label_deal_type:
                new_labels_indexes.append(li)
                continue

            if not self.validate_deal_type_reobj.search(re.sub(r"\s","", label_content)):
                labels_unused.append([label_content, li[2]])
                continue
            
            # 该公司成立以来获得的第三次融资(无用)
            if label_content.startswith("第"):
                labels_unused.append([label_content, li[2]])
                continue
            
            # 此轮本来只打算融资6000-8000万美元
            if re.match(r"融资|投资", label_content) and i+1 < len(labels_indexes) and labels_indexes[i+1][0] == li[1] and labels_indexes[i+1][2] == "金额":
                labels_unused.append([label_content, li[2]])
                continue
            
            clause_pos_span = get_clause_span(sent, li[0], li[1])
            # 本轮融资由深圳高新投战略投资(无用)
            if label_content.endswith("投资") and not self.verb_reobj.search(sent, clause_pos_span[0], li[0]):
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
                continue
            
            new_labels_indexes.append(li)
        sentence_struct_info["labels_indexes"], sentence_struct_info["labels_unused"] = new_labels_indexes, labels_unused

    # 返回clause_idx_span到实际交易事件和时间的映射
    def get_dtspan_dict(self, sentence_struct_info: dict):
        sent, labels_indexes = sentence_struct_info["sent"], sentence_struct_info["labels_indexes"]

        # 获取实际交易类型到交易类型实体spans（可能一个实际交易类型对应多个交易类型实体）的映射、交易类型实体与金额对
        real_dt2label_dts, dt_amount_pair = get_real_dt2label_dts(sent, labels_indexes, self.repl_deal_type_reobj, self.invalid_repl_dt_reobj)
        
        idxspan2real_dts = {(0, len(sent)): list(real_dt2label_dts.keys())}
        
        if len(real_dt2label_dts) > 0:
            separators = ["；", "，", "、"]
            # 划分span为尽可能小单位，以尽可能使得每个span最多只有一个real_dt，最小的单位为"、"分割的短句的span
            idxspan2real_dts = divide_real_dts_span(sent, idxspan2real_dts, real_dt2label_dts, separators)
        
        # 使前面未被span覆盖的时间标签被其后面的dt_span覆盖，因为前面的时间很大可能是其后real_dt相关的时间
        forward_extend_dtspan(sent, labels_indexes, idxspan2real_dts)
        
        # 向后扩展span，使所有span邻接，合并以"、"分割但无金额的span
        backward_extend_dtspan(sent, idxspan2real_dts, real_dt2label_dts, dt_amount_pair)
        
        # 对无交易类型的情况加指代交易类型
        spans = idxspan2real_dts.keys()
        for span in spans:
            real_dts = idxspan2real_dts[span]
            if len(real_dts) == 0:
                matches = self.validate_deal_type_reobj.finditer(sent, span[0], span[1])
                for m in matches:
                    mspan = m.span()
                    is_valid = True
                    for li in labels_indexes:
                        # "维港投资"中的"投资"不是交易类型
                        if li[2] == self.label_related_party and mspan[0] >= li[0] and mspan[1] <= li[1]:
                            is_valid = False
                            break
                        if li[0] > mspan[1]:
                            break
                    if is_valid:
                        idxspan2real_dts[span] = [m.group()]
                        break
                
        # 根据span排序重新生成dict
        idxspan2real_dts = {i[0]:i[1] for i in sorted(idxspan2real_dts.items())}
        
        sentence_struct_info["idxspan2real_dts"], sentence_struct_info["real_dt2label_dts"] = idxspan2real_dts, real_dt2label_dts

    # 生成span到date的映射，优先更准确的时间
    def get_date_span_dict(self, sentence_struct_info: dict):
        sent = sentence_struct_info["sent"]
        labels_indexes = sentence_struct_info["labels_indexes"]
        idxspan2real_dts = sentence_struct_info["idxspan2real_dts"]
        idxspan2dates = {}
        for i, li in enumerate(labels_indexes):
            if li[2] == self.label_dcs_date:
                label_content = sent[li[0]:li[1]]
                for span in idxspan2real_dts:
                    if li[0] >= span[0] and li[1] <= span[1]:
                        if span not in idxspan2dates:
                            idxspan2dates[span] = {}
                        if "disclosed_dates" not in idxspan2dates[span]:
                            idxspan2dates[span]["disclosed_dates"] = [(li[0],li[1])]
                        else:
                            pre_span = idxspan2dates[span]["disclosed_dates"][0]
                            pre = sent[pre_span[0]:pre_span[1]]
                            if not self.date_reobj.search(pre):
                                idxspan2dates[span]["disclosed_dates"][0] = (li[0],li[1])
                            elif self.date_reobj.search(label_content):
                                idxspan2dates[span]["disclosed_dates"].append((li[0],li[1]))
            if li[2] == self.label_occ_date:
                label_content = sent[li[0]:li[1]]
                for span in idxspan2real_dts:
                    if li[0] >= span[0] and li[1] <= span[1]:
                        if span not in idxspan2dates:
                            idxspan2dates[span] = {}
                        if "occurrence_dates" not in idxspan2dates[span]:
                            idxspan2dates[span]["occurrence_dates"] = [(li[0],li[1])]
                        else:
                            pre_span = idxspan2dates[span]["occurrence_dates"][0]
                            pre = sent[pre_span[0]:pre_span[1]]
                            if not self.date_reobj.search(pre):
                                idxspan2dates[span]["occurrence_dates"][0] = (li[0],li[1])
                            elif self.date_reobj.search(label_content):
                                idxspan2dates[span]["occurrence_dates"].append((li[0],li[1]))
        sentence_struct_info["idxspan2dates"] = idxspan2dates

    def get_entities_sent(self, sentence_struct_info: dict):
        sent = sentence_struct_info["sent"]
        labels_indexes = sentence_struct_info["labels_indexes"]
        # 小句原索引范围到实际交易类型的映射
        idxspan2real_dts = sentence_struct_info["idxspan2real_dts"]
        # 小句原索引范围到日期信息的映射
        idxspan2dates = sentence_struct_info["idxspan2dates"]
        
        entities_sent, entities_index2original, alias, attr_noun_dict, original_index2entities = "", {}, {}, {}, {}
        # 标签替换前后首索引差值
        replaced_list = []
        idx_diff = 0
        start = 0
        
        # 将sent的span转为entities_sent的span，ori为original
        ori_spans = list(idxspan2real_dts.keys())
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
            label_length = len(self.label_str_map[label[2]])
            entities_index2original[(label_start_idx, label_start_idx + label_length)] = (label[0], label[1])
            original_index2entities[(label[0], label[1])] = (label_start_idx, label_start_idx + label_length)
            idx_diff += (label_length - (label[1] - label[0]))
            # 替换为标签
            replaced_list.append(self.label_str_map[label[2]])
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
                    if end == -1 or self.noalias_reobj.search(sent[start+1:end]) or\
                        (i + 1) < len(labels_indexes) and labels_indexes[i+1][1] <= end:
                        continue
                    m = self.alias_token_reobj.search(sent, start+1, end)
                    # “简称|英文名：”后是别名，若无则默认括号内都是别名
                    s = m.end() if m else start+1
                    als = {sent[s:end]}
                    # 处理简称前可能有英文名的情况
                    e = m.start() if m else end
                    m = self.english_name_reobj.search(sent, start+1, e)
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
        new_idxspan2real_dts = {i[1]: idxspan2real_dts[i[0]] for i in zip(ori_spans, new_spans)}
        new_idxspan2dates = {i[1]: idxspan2dates[i[0]] for i in zip(ori_spans, new_spans) if i[0] in idxspan2dates}
        sentence_struct_info["idxspan2real_dts"], sentence_struct_info["idxspan2dates"] = new_idxspan2real_dts, new_idxspan2dates
        
        entities_sent = "".join(replaced_list)
        sentence_struct_info["entities_sent"], sentence_struct_info["entities_index2original"], sentence_struct_info["original_index2entities"], sentence_struct_info["alias"], sentence_struct_info["attr_noun_dict"] = entities_sent, entities_index2original, original_index2entities, alias, attr_noun_dict

    # 填充deal_type，对dates分类，处理关联方别名，统计标签使用情况
    def adjust_field(self, sentence_struct_info):
        # 原句子
        sent = sentence_struct_info["sent"]
        # 小句的index_span到实际交易类型的映射
        idxspan2real_dts = sentence_struct_info["idxspan2real_dts"]
        # 小句的index_span到日期信息的映射
        idxspan2dates = sentence_struct_info["idxspan2dates"]
        # 统计已使用的交易类型标签时使用
        real_dt2label_dts = sentence_struct_info["real_dt2label_dts"]
        # 模板匹配结果
        match_result = sentence_struct_info["match_result"]
        # 实体句子实体index_span到原句子index_span的映射
        entities_index2original = sentence_struct_info["entities_index2original"]
        # 原句子实体index_span到实体句子index_span的映射
        original_index2entities = sentence_struct_info["original_index2entities"]
        # 别名信息
        alias = sentence_struct_info["alias"]
        # 使用过的标签idx_span集合
        total_labels_used = set({})
        
        # 从所有的match_result中获取fc信息
        financing_company_info = get_financing_company_info(match_result, sent, entities_index2original, alias, total_labels_used)
        
        new_match_result = []
        # 填充每个match_result对应的deal_type和日期信息，并将结构体的span字段值替换为实际值
        for mr in match_result:
            mr_struct = mr["struct"]
            mr_span = mr["match_span"]
            for span, real_dts in idxspan2real_dts.items():
                if span[0] <= mr_span[0] and mr_span[1] <= span[1]:
                    # TODO if len(real_dts) == 0 的情况
                    for real_dt in real_dts:
                        if len(financing_company_info)==0 and len(real_dts) > 1:
                            break
                        # 新的match_result_struct
                        nmr_struct = {}
                        nmr = {"struct": nmr_struct,"from_rule": mr["from_rule"]}
                        # 添加使用过的deal_type和date标签以及填充date
                        if real_dt in real_dt2label_dts:
                            for label_dt in real_dt2label_dts[real_dt]:
                                total_labels_used.add(original_index2entities[label_dt])
                        nmr_struct["deal_type"] = real_dt
                        if span in idxspan2dates:
                            for field_name, date_spans in idxspan2dates[span].items():
                                date_span = date_spans[0]
                                nmr_struct[field_name] = sent[date_span[0]:date_span[1]]
                                total_labels_used.add(original_index2entities[date_span])
                        
                        # 如果有融资方信息就填充
                        if len(financing_company_info)!=0:
                            for k, v in financing_company_info[list(financing_company_info.keys())[0]].items():
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
                                elif k == "finacial_advisers":
                                    total_labels_used.update(v)
                                    finacial_advisers = get_field_value(sent, entities_index2original, v)
                                    nmr_struct["finacial_advisers"] = finacial_advisers
                        new_match_result.append(nmr)
                        
        sentence_struct_info["total_labels_used"] = total_labels_used
        sentence_struct_info["match_result"] = new_match_result
        return

    def get_labels_unused(self, sentence_struct_info):
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