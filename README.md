# Extract Basic Structs From News

从新闻中抽取基础结构体

## 抽取基础结构体的步骤
以下步骤实现在extract.extractor.DictExtractor中，从其方法__call__开始

- 先对输入的句子做规范化处理，包括去除无用的空白字符和引号、替换英文标点为中文标点等等
- 请求ner
- 验证deal_type实体的有效性，将错误的或无用的deal_type实体去除
- 获取子句origin_index_span(原索引范围)到实际交易类型的映射，一个实际交易类型可能对应零个、一个或多个交易类型实体
- 获取子句origin_index_span(索引范围)到date的映射，会优先更准确的时间，该span与交易类型的span的一一对应的
- 将句子转为实体句子，与此同时，这步还会做以下处理：
    - 提取关联方别名信息，并去除括号
    - 去除融资方标签和关联方标签之间的任何字符，简化后续模板设计
    - 将第4，5步中的origin_index_span转为实体句子的index_span，origin_index_span是相对于原句子的，而不是实体句子的，这样处理后才能在后续判断实体句子的某个match是否在实际交易类型的index_span中
- 走规则，获取匹配结果match_result，每个句子可能有多个匹配后生成的结构体，结构体的字段值用在实体句子的索引范围表示，匹配结果里没有填充交易类型和日期，仅仅包含整个match的索引范围
- 调整字段值，将索引范围转为实际值，同时填充交易类型和日期，并统一填充融资方信息。

## 目录结构

- 抽取基础结构体的逻辑在extract包中
    - extractor模块中包含一个实现抽取逻辑的类DictExtractor，该类的__call__方法实现了上述的步骤。调用该类的对象时需要传入一个句子，返回一个sentence_struct_info的结构体，该结构里的“match_result”字段对应的值才是抽取出的基础结构体，其他字段是辅助及统计信息之用。
    - extractor_funcs模块中是DictExtractor要调用的函数，各函数的作用在函数签名下有说明
    - labelstr模块定义了ner标签的字符串常量
    - reqner模块定义请求外部ner的函数
    - rule包里面定义模板规则
        - super_rule模块包含所有模板规则的父类SuperRule，SuperRule定义了一些共用的模板碎片，子类通过将这些碎片和其他特定字符组成模板，调用父类的set_reobj方法设置模板，并调用其他set方法设置字段名和分组tag的关系，若模板涉及属性名词，则需要另外设置对属性名词内容的模板等等
        - rules模块定义各种规则，通过规则里面的模板匹配各类句式

- 生成融合结构体的逻辑在merge_包中
    - merger模块中定义了一个类DictMerger，其是用于调用外部merge_engine的方法来实现结构体融合，该类在调用merge_engine前需要构造传递的参数，如关键字包装器和非关键字过滤器。调用DictMerger对象时需要传入待融合结构体的列表。
    - keywrappers模块中定义关键值包装器

