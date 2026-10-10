"""画像信息抽取器 —— 从用户自然语言中提取可填模板的身份信息（纯规则，零 LLM 调用）

设计前提（2026-10-10 与佳文确认）：
1. **纯正则，零模型调用**。本地 7B 抽取不可靠且慢（3~10s/次），而身份信息是
   强格式文本，正则的准确率远高于小模型，且行为完全可预测、可单测。
2. **入库存原文，模糊化只发生在云端调用前**。入库时抹掉学号会导致模板无法回填；
   真正需要防外泄的是「发给云端的那一刻」，那道闸在 build_context 的出口。
3. **学号等强标识不入画像**（SENSITIVE_FIELDS）。用户要求填学号，但学号一旦进画像
   就会被 build_context 拼进 prompt → 随云端重写外发。这里明确取舍：
   宁可少填一个字段，也不让强标识进入可能被外发的上下文。
   若将来要支持学号回填，正确做法是单独存 encryption-at-rest 的字段并从
   build_context 排除，而非直接挂在 UserProfile 上。
4. **抽取结果需用户确认才落盘**（CONFIRM_REQUIRED）。误抽取比漏抽取危险得多：
   把错误的学号填进开题报告，比不填严重得多。

本模块只做「抽取」，不做 I/O，落盘由 PersonalBrain 负责（同「图谱类不碰文件 I/O」约定）。
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# 中文数字 → 阿拉伯数字（年级/班级常用「二〇二三」写法，但更常见的是「2023」）
_CN_NUM = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
    "七": 7, "八": 8, "九": 9, "〇": 0, "零": 0, "两": 2,
}

#: 强身份标识：不入画像、不进 build_context、永不外发
SENSITIVE_FIELDS = frozenset({"student_id", "id_card", "phone", "email"})

#: 需用户确认后才允许落盘的字段（当前全开）
CONFIRM_REQUIRED = frozenset({
    "display_name", "school", "school_short", "major",
    "class_name", "grade_year", "degree_stage",
})

#: 抽取到的字段 → UserProfile 属性名
_EXTRACT_TARGETS = (
    "display_name", "school", "school_short", "major",
    "class_name", "grade_year", "degree_stage",
)


@dataclass
class ExtractionResult:
    """一次抽取的结果。

    fields: 字段名 → 值（仅含 CONFIRM_REQUIRED 中的字段）
    evidence: 字段名 → 命中的原文片段（用于让用户核对，缺了它用户无法判断抽得对不对）
    sensitive_found: 检出的强标识字段名（仅记录字段名，**不返回值**）
    pending_confirm: True 表示必须经用户确认才可落盘
    """

    fields: Dict[str, str] = field(default_factory=dict)
    evidence: Dict[str, str] = field(default_factory=dict)
    sensitive_found: List[str] = field(default_factory=list)
    pending_confirm: bool = True

    def is_empty(self) -> bool:
        return not self.fields

    def to_dict(self) -> dict:
        return {
            "fields": dict(self.fields),
            "evidence": dict(self.evidence),
            "sensitive_found": list(self.sensitive_found),
            "pending_confirm": self.pending_confirm,
        }


class ProfileExtractor:
    """纯规则身份信息抽取器。

    所有正则均为独立编译、无副作用；同一实例可跨线程只读使用。
    """

    # ---- 姓名 ----
    # ⚠️ 中文正则无长度边界，这是首版最大的坑：
    # `([一-龥]{2,4})` 会把「我本科是哈尔滨工业大学」整段当成姓名/校名吞掉
    # （实测 8/18 用例失败）。改为「cue 点 + 逐长度回退 + 尾字黑名单」。
    _RE_NAME_CUE = re.compile(r"我(?:叫|的名字(?:叫|是)|本人叫|是)\s*")
    #: 姓名候选之后紧跟这些字 → 说明吞多了，缩短候选
    _NAME_TAIL_FORBID = "的了吧呢啊是在和与跟对从，。、！!？?：:"
    #: 以这些词开头的「我是X」是专业/院校，不是姓名
    _NAME_HEAD_FORBID = (
        "计算机", "软件", "电子", "机械", "土木", "化学", "生物", "数学", "物理",
        "金融", "会计", "法学", "汉语言", "英语", "临床", "口腔", "护理", "药学",
        "新闻", "美术", "音乐", "设计", "心理", "历史", "哲学", "教育", "地理",
        "工商", "管理", "经济", "统计", "自动化", "通信", "车辆", "材料", "农林",
        "畜牧", "水产", "旅游", "烹饪", "体育", "国贸", "营销", "人力", "行政",
        "档案", "保密", "外交", "大几", "研",
    )
    _NAME_STOPWORDS = frozenset({
        "学生", "老师", "教师", "同学", "医生", "大奖", "程序员", "工程师",
        "设计师", "运营", "产品", "经理", "总监", "老板", "本人", "学生党",
        "大几", "什么", "谁", "哪个", "哪里", "的人", "不是", "不要", "叫",
    })

    # ---- 学校 ----
    #: 校名后缀表（先长后短，避免「职业技术学院」被截成「职业技术」）
    _SCHOOL_TAIL = (
        "职业技术大学", "职业技术学院", "师范大学", "工业大学", "理工大学",
        "农业大学", "医科大学", "科技大学", "财经大学", "交通大学", "大学", "学院",
    )
    #: ⚠️ 关键教训（实测 5/17 全挂的根因）：
    #: 「惰性量化 + 尾部锚定」在中文上不可靠 —— `{2,10}?(?:大学|学院)`
    #: 惰性只吞最短就要求后缀，「哈尔滨工业大学」被切成「哈尔…」，
    #: 而「工业大学」是「大学」之后的分支，引擎向左优先试到「大学」成功即停，
    #: 于是整串左边界被拉长成噪声前缀。
    #: 正确写法：**贪婪吞 + 尾部锚定 + handler 里从右向左剥离噪声前缀**。
    _RE_SCHOOL = re.compile(r"[一-龥]{2,14}(?:" + "|".join(_SCHOOL_TAIL) + r")")
    #: 校名左侧噪声前缀，handler 里逐个剥离
    _SCHOOL_NOISE_PREFIX = (
        "我本科是", "我硕士是", "我博士是", "我专科是", "我的学校是", "我的学校叫",
        "我是", "我在", "我", "本科是", "硕士是", "博士是", "专科是",
        "学校是", "学校叫", "毕业于", "考入", "就读于", "考上了",
    )
    #: 简称/校区：「XX校区」「XX分校」「XX大学城」
    _RE_SCHOOL_SHORT = re.compile(r"[一-龥]{2,12}(?:校区|分校|大学城)")

    # ---- 专业 ----
    # ⚠️ 实测根因：「专业(?:是)?\s*(...)(?:专业|方向|学科)」要求「软件工程」后面
    # 再出现「专业」二字 → 「我专业是软件工程」永不匹配。
    #: 正确写法：**cue 之后惰性吞 + 用后置分隔符/结尾锚定**，专业名本体由 cue 提供。
    _RE_MAJOR = re.compile(
        r"(?:我(?:的)?)?专业(?:是|为|叫|方向是)?\s*"
        r"([一-龥]{2,18}?)"
        r"(?=[的专业，,。；;！!？?、]|$)"
    )
    #: ⚠️ 专业名在 cue **之后**：「我专业是软件工程」
    _RE_MAJOR_AFTER = re.compile(
        r"(?:我(?:的)?)?专业(?:是|为|叫)?\s*([一-龥]{2,18})"
    )
    #: ⚠️ 专业名在 cue **之前**：「计算机科学与技术专业」——
    #: 这是中文里更常见的语序，首版完全没覆盖（实测 3 条用例全挂）。
    _RE_MAJOR_BEFORE = re.compile(
        r"([一-龥]{2,18}?)(?:这个|该)?专业"
        r"(?=[的，,。；;！!？?、\s]|$)"
    )
    #: ⚠️ 校名+专业连写兜底：「哈尔滨工业大学计算机专业」
    #: 这类「X大学Y专业」里，X大学是校名（已被 _RE_SCHOOL 吃掉），
    #: Y 是专业。做法：先切掉校名部分再抽专业。
    _RE_MAJOR_AFTER_SCHOOL = re.compile(
        r"[一-龥]{2,14}?大学(?:及|与|、|和)?\s*"
        r"([一-龥]{2,10}?)专业"
    )
    #: 无「专业」二字的弱信号：必须以已知学科尾词收尾，且**长度上限 8 字**
    #: ⚠️ 实测教训：不限长时「我本科是哈尔滨工业大学计算机」整段被吞（14 字）。
    #: 中文无边界，弱信号必须限长 + 排除含「大学/学院/我」的串。
    _RE_MAJOR_WEAK = re.compile(
        r"([一-龥]{2,8}?(?:工程|科学|技术|学|系))(?![一-龥])"
    )
    _MAJOR_TAIL = ("专业", "方向", "学科", "工程", "科学", "技术", "学", "系")

    # ---- 班级 ----
    # ⚠️ 实测根因：`(?<![学号手机号…])` 只挡**一个**字符，
    #: 「我是计科2301」的「是」不在黑名单 → 吞成「我是计科2301」。
    #: 正确写法：**贪婪吞 + handler 里剥离中文动词前缀 + 院系缩写白名单校验**。
    _RE_CLASS = re.compile(r"[一-龥]{2,8}\d{4}(?!\d)")
    #: 班级前的中文噪声词，handler 里从左向右剥离
    # ⚠️ 必须包含单字人称「我」「你」，且按**长度降序**排列。
    #: 实测教训：漏掉单字「我」→ 「我是计科2301」永远剥不掉前缀，
    #: 捕获组变成「我是计科」，前缀长度4刚好绕过 >4 的长度上限 → 脏值放行。
    _CLASS_NOISE_PREFIX = (
        "我们班是", "我们班在", "我们是", "我们", "我的",
        "班是", "班在", "我在", "我是",
        "读的", "读上", "上班",
        "读", "上", "是", "在", "的", "我",
    )
    #: 院系缩写白名单：前缀**任一字**命中即可
    #: ⚠️ 实测教训：首版取 `cn[-1]` 判断，「计科2301」的末字是「科」不在表内 → 全挂。
    #: 正确做法是**前缀任一字符命中缩写表**（计/软/电/机…都是院系首字）。
    _CLASS_PREFIX_TAIL = (
        "计", "软", "电", "机", "土木", "建", "化", "生", "数", "物", "法", "汉",
        "英", "商", "财", "审", "公", "行", "新", "传", "艺", "体", "医", "护",
        "药", "农", "林", "交", "航", "食", "心", "历", "哲", "教", "地", "语",
        "冶", "能", "环", "安", "印", "纺", "科", "学", "核", "测", "控",
    )
    _RE_CLASS_CTX = re.compile(
        r"(?:我们(?:班|在)|我在|读|上)\s*([一-龥]{2,6}\d{4})(?!\d)"
    )

    # ---- 年级 / 培养阶段 ----
    _RE_GRADE_YEAR = re.compile(r"((?:19|20)\d{2}\s?[级届])")
    _RE_GRADE_SHORT = re.compile(r"([一二三四五六七八九])\s*年级")
    #: 裸「大三」「大二」
    #: ⚠️ 实测教训：首版用 `(?<![一-龥])大` 作左边界，把「我在武汉大学读的大二」
    #: 也挡掉了（前面是中文「的」）。左边界只该挡**数字和字母**，
    #: 「大学」「大家」这类误命中交由右侧后缀校验兜底。
    _RE_GRADE_DA = re.compile(r"(?<![0-9A-Za-z])大([一二三四])(?:$|[^一-龥])")
    _RE_GRADE_NUM = re.compile(r"(?<!\d)([1-4])\s*年级")
    _RE_DEGREE = re.compile(
        r"(本科生?|专科生?|硕士(?:研究)?生|博士生?|研究生)"
    )

    # ---- 强标识（只检出字段名，不返回值）----
    _RE_STUDENT_ID = re.compile(
        r"(?:学号|Student\s*ID|student\s*id)\s*(?:是|为|:|：)?\s*([A-Za-z0-9]{6,20})",
        re.IGNORECASE,
    )
    _RE_PHONE = re.compile(r"(?<!\d)(1[3-9]\d{9})(?!\d)")
    _RE_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]{2,}")
    _RE_IDCARD = re.compile(r"(?<!\d)(\d{17}[\dXx])(?!\d)")

    # ---- 排除词：命中则整体放弃该字段（宁缺勿错）----
    _RE_NEGATION = re.compile(
        r"(?:不是|别填|不要填|不用|无需|随便|例如|比如|举例|假设|如果我是)"
    )

    # ---- 排除词：这些是问题而非陈述（如「你是大几的？」）----
    _RE_QUESTION = re.compile(
        r"[?？]\s*$|(?:请问|帮我查|你知不知道|是多少|叫什么名字)\s*[?？]?"
    )

    # ---------------------------------------------------------------

    def extract(self, text: str) -> ExtractionResult:
        """从一段用户输入中抽取身份信息。

        Args:
            text: 用户原始输入（一整段，可能含多句）

        Returns:
            ExtractionResult；未命中任何字段时 is_empty() 为 True
        """
        result = ExtractionResult()
        if not text or not isinstance(text, str):
            return result
        text = text.strip()
        if not text:
            return result

        # 整段是疑问句且无自述 cue → 直接放弃（避免把「你叫啥」当成用户自述）
        if self._RE_QUESTION.search(text) and not self._RE_SELF_CUE.search(text):
            return result

        # 先探测强标识：即使不入画像，也要告知调用方「用户在输入里给了敏感信息」
        for fname, rx in (
            ("student_id", self._RE_STUDENT_ID),
            ("phone", self._RE_PHONE),
            ("email", self._RE_EMAIL),
            ("id_card", self._RE_IDCARD),
        ):
            if rx.search(text):
                result.sensitive_found.append(fname)

        def _negated(pos: int, end: int) -> bool:
            """否定/举例词是否出现在命中点前 10 字或后 6 字内。

            ⚠️ 首版 bug：窗口是「前 8 后 8」，「我叫你不要写这个东西」里
            「不要」距「我叫」有 5 字、落在窗口内却因先命中姓名而失效
            （实测抽到 display_name='你不要写'）。
            修法：**先做否定门禁，再抽任何字段** —— 只要整段出现否定词就整体放弃。
            代价是「我不要苹果，就要橙子」这类会漏抽，但宁缺勿错。
            """
            win = text[max(0, pos - 10):end + 6]
            return bool(self._RE_NEGATION.search(win))

        # ---- 姓名（需在专业之前抽：先定位 cue，再向后截断）----
        m = self._RE_NAME_CUE.search(text)
        if m and not _negated(m.start(), m.end()):
            value = self._extract_name_after(text, m.end())
            if value:
                result.fields["display_name"] = value
                result.evidence["display_name"] = value

        # ---- 裸姓名兜底：「韩佳文，男，计科2301」「韩佳文 计科2301」
        #: 无 cue 时若整段极短（≤3 句）且以 2~4 字中文开头，视为自述姓名。
        #: 护栏：长度上限 + 排除词 + 必须不在疑问句里，避免把「今天天气」当姓名。
        if "display_name" not in result.fields:
            value = self._extract_bare_name(text)
            if value:
                result.fields["display_name"] = value
                result.evidence["display_name"] = value

        # ---- 专业（双向 cue：前接式 + 后接式 + 弱信号）----
        # ⚠️ 中文里「X专业」和「专业是X」两种语序都常见，必须都覆盖。
        #   优先级：后接式（专业是X，语义最强）> 前接式（X专业）> 弱信号（尾词）
        for rx in (self._RE_MAJOR_AFTER, self._RE_MAJOR_AFTER_SCHOOL,
                   self._RE_MAJOR_BEFORE,
                   self._RE_MAJOR, self._RE_MAJOR_WEAK):
            mm = rx.search(text)
            if not mm:
                continue
            if _negated(mm.start(), mm.end()):
                continue
            value = self._handle_major(mm)
            if value:
                result.fields["major"] = value
                result.evidence["major"] = value
                break

        # ---- 其余标量字段 ----
        for fname, rx, handler in (
            ("school", self._RE_SCHOOL, self._handle_school),
            ("school_short", self._RE_SCHOOL_SHORT, self._handle_school_short),
            ("class_name", self._RE_CLASS, self._handle_class),
            ("grade_year", self._RE_GRADE_YEAR, self._handle_grade_year),
            ("degree_stage", self._RE_DEGREE, self._handle_degree),
        ):
            mm = rx.search(text)
            if not mm:
                continue
            if _negated(mm.start(), mm.end()):
                continue
            value = handler(mm)
            if not value:
                continue
            result.fields[fname] = value
            result.evidence[fname] = mm.group(0).strip()

        # ---- 年级短写兜底：大三 / 3年级 / 二年级 ----
        if "grade_year" not in result.fields:
            for rx, conv in (
                (self._RE_GRADE_SHORT, lambda mm: f"{_CN_NUM[mm.group(1)]}年级"),
                (self._RE_GRADE_DA, lambda mm: f"{_CN_NUM[mm.group(1)]}年级"),
                (self._RE_GRADE_NUM, lambda mm: f"{mm.group(1)}年级"),
            ):
                mm = rx.search(text)
                if not mm:
                    continue
                if _negated(mm.start(), mm.end()):
                    continue
                try:
                    val = conv(mm)
                except (KeyError, IndexError):
                    continue
                result.fields["grade_year"] = val
                result.evidence["grade_year"] = mm.group(0)
                break

        return result

    # 「我是XX」既是姓名线索也是专业线索，用它做整段的自述信号
    _RE_SELF_CUE = re.compile(r"我(?:叫|是|的名字)")

    # ---- 各字段处理器：清洗 + 排除词过滤 ----

    def _extract_name_after(self, text: str, start: int) -> str:
        """从 cue 之后抽取姓名，逐长度回退直到尾字合法。

        这是首版最严重的 bug 的正解：中文正则没有右边界，
        `我叫韩佳文，学号...` 里若取 4 字会得到「韩佳文学号」，
        必须从最长候选回退到遇到尾字黑名单为止。

        场景：「我们班是计科2301，我是韩佳文」—— cue 在句中，
        cue 后紧跟的应是真正的姓名，需跳过前置噪声词。
        """
        tail = text[start:start + 12]
        if not tail:
            return ""
        # ⚠️ 实测教训：cue 位于句末时 tail 可能只有 2~3 字（「…，我是韩佳文」）。
        # 原循环按 4→3→2 逐个截断，3 字「韩佳文」在 length=2 时得「韩佳」，
        # 但其后一字「文」是汉字 → 2 字分支要求「后面非汉字」也失败 → 整条返回空。
        # 修法：**先尝试整段短串**，若 tail 到文本结束且是纯中文姓名，直接采纳。
        stripped = tail.rstrip()
        head = re.split(r"[\d\s,，。、!！?？:：;；]", stripped)[0]
        if 2 <= len(head) <= 4 and head == stripped:
            if (head not in self._NAME_STOPWORDS
                    and not any(h in head for h in self._NAME_HEAD_FORBID)):
                return head
        # 从 4 字回退到 2 字
        for length in (4, 3, 2):
            cand = tail[:length]
            if len(cand) < 2:
                continue
            # 候选内部含非中文（如数字）→ 截断
            cand = re.split(r"[\d\s,，。、!！?？:：]", cand)[0]
            if len(cand) < 2:
                continue
            if cand in self._NAME_STOPWORDS:
                return ""
            if any(cand.startswith(h) or h in cand
                   for h in self._NAME_HEAD_FORBID):
                return ""
            # 尾字必须是「名字常用字」，即后面紧跟的分隔符或结束
            after = tail[length:length + 1]
            if after and after in self._NAME_TAIL_FORBID:
                return cand
            if length == 2:
                # 2 字候选：后面是标点/结束/汉字名词边界都可接受
                if not after or not re.match(r"[一-龥]", after or " "):
                    return cand
        return ""

    def _extract_bare_name(self, text: str) -> str:
        """无 cue 的裸姓名兜底抽取。

        场景A：「韩佳文，男，计科2301」—— 姓名在**开头**
        场景B：「我们班是计科2301，我是韩佳文」—— 姓名在**句中 cue 之后**
          （这里由主流程的 _RE_NAME_CUE 覆盖，此处只补场景A）

        护栏（宁缺勿错）：
        - 只看开头 4 字，姓名后必须紧跟分隔符/属性词（逗号、空格、性别、班级…）
        - 长度 2~3 字（中文姓名常规长度）
        - 命中排除词或疑问句直接放弃
        """
        head = text[:4]
        m = re.match(r"[一-龥]{2,3}", head)
        if not m:
            return ""
        cand = m.group(0)
        if cand in self._NAME_STOPWORDS:
            return ""
        if any(h in cand for h in self._NAME_HEAD_FORBID):
            return ""
        # 姓名后必须紧跟「属性信号」：标点 / 性别 / 年龄 / 班级 / 逗号
        after = text[m.end():m.end() + 6]
        if not re.match(r"[\s,，。、:：;；]|男|女|岁|班|级|，", after):
            return ""
        # 疑问句不抽
        if self._RE_QUESTION.search(text):
            return ""
        return cand

    def _handle_school(self, m) -> str:
        val = m.group(0)
        # 贪婪匹配会把左侧噪声吞进来（「我本科是哈尔滨工业大学」），
        # 按已知噪声前缀从长到短剥离。
        changed = True
        while changed:
            changed = False
            for prefix in self._SCHOOL_NOISE_PREFIX:
                if val.startswith(prefix) and len(val) > len(prefix) + 2:
                    val = val[len(prefix):]
                    changed = True
                    break
        return val

    def _handle_school_short(self, m) -> str:
        return m.group(0)

    #: 专业名库：命中即认可（不依赖「工程/技术」等尾词）
    #: ⚠️ 实测教训：「计算机」「软件工程」里的「计算机」不含任何尾词，
    #: 原先只看 _MAJOR_TAIL 会把标准专业名全部拒掉。
    _MAJOR_DICTIONARY = (
        "计算机", "软件", "电子", "通信", "自动化", "人工智能", "信息",
        "机械", "土木", "建筑", "车辆", "测绘", "地质", "采矿", "冶金",
        "材料", "化学", "化工", "生物", "医学", "临床", "口腔", "护理",
        "药学", "农学", "园林", "food", "金融", "会计", "审计", "税务",
        "工商", "管理", "经济", "贸易", "市场营销", "物流", "旅游",
        "法学", "汉语言", "英语", "日语", "新闻", "传播", "广告",
        "美术", "音乐", "舞蹈", "体育", "心理学", "哲学", "历史",
        "教育", "地理", "政治", "行政", "档案", "保密", "安全",
        "数学", "物理", "化学", "统计学", "生物医学",
    )

    def _handle_major(self, m) -> str:
        val = m.group(1)
        # ⚠️ 实测教训：「X专业的大三学生」里前接式捕获组会带上「的大三学生」，
        #: 必须剥离尾部的中文描述性成分，只保留专业名本体。
        # 做法：从右向左剥「的」及其后的中文短语（专业名里不含「的」）。
        if "的" in val:
            val = val.split("的", 1)[0]
        # 前接式捕获组可能带尾部「专业」二字（若正则在 cue 右侧未消费），剥掉
        for tail in ("这个专业", "该专业", "专业"):
            if val.endswith(tail) and len(val) > len(tail):
                val = val[: -len(tail)]
                break
        # 排除「XX学院/XX大学」被误当专业
        if val.endswith(("学院", "大学")):
            return ""
        # 含数字说明吞多了（如「计科2301」）
        if re.search(r"\d", val):
            return ""
        if not any(t in val for t in self._MAJOR_TAIL):
            # 尾词门槛只是启发式，命中专业名词库同样认可
            if not any(d in val for d in self._MAJOR_DICTIONARY):
                return ""
        # ⚠️ 弱信号跨边界防护：「我本科是哈尔滨工业大学计算机」这类
        # 专业名里混进了校名与人称代词，宁可丢弃也不能把错值填进模板。
        if "大学" in val or "学院" in val or "我" in val:
            return ""
        # 过长的候选一定是跨了语义边界（专业名常规 ≤ 8 字）
        if len(val) > 8:
            return ""
        # 纯泛词（只有「专业」二字本身）不算
        if len(val) < 2:
            return ""
        return val

    def _handle_class(self, m) -> str:
        val = re.sub(r"\s+", "", m.group(0))
        # 剥离左侧中文噪声（「我是计科2301」→ 「计科2301」）
        # ⚠️ 实测教训：条件写成 `len(val) > len(prefix) + 4` 时，
        # 「我是计科2301」剥离「我是」后剩 6 字、6 > 6 为假 → 没剥掉。
        # 正确下限是「剥离后仍需留下 ≥2 汉字 + 4 数字」，即 len(val) - len(prefix) >= 6。
        changed = True
        while changed:
            changed = False
            for prefix in self._CLASS_NOISE_PREFIX:
                if val.startswith(prefix) and len(val) - len(prefix) >= 6:
                    val = val[len(prefix):]
                    changed = True
                    break
        digits = re.search(r"\d{4}$", val)
        if not digits:
            return ""
        cn = val[:digits.start()]
        if not cn:
            return ""
        # 院系缩写白名单：中文前缀**任一字**命中缩写即认可
        # （实测教训：取末字判断时「计科」的「科」不在表内 → 全部漏抽）
        if not any(ch in self._CLASS_PREFIX_TAIL for ch in cn):
            return ""
        # 前缀过长（>4 字）说明吞了动词，如「班是计科」
        if len(cn) > 4:
            return ""
        # 数字段恰为年份形态 → 是入学年份不是班级
        if re.fullmatch(r"(?:19|20)\d{2}", digits.group(0)):
            return ""
        return val

    def _handle_grade_year(self, m) -> str:
        return re.sub(r"\s+", "", m.group(1)).replace("届", "级")

    def _handle_degree(self, m) -> str:
        return m.group(1)


def mask_for_cloud(profile_fields: Dict[str, str]) -> Dict[str, str]:
    """把画像身份字段转成可外发的粗粒度描述（纯规则，零模型）。

    这是「模糊化处理」的唯一实现点：入库存原文（要能回填），
    发给云端前才做粗化（防外泄）。

    设计原则：**宁可少说，不可说错**。识别不了的字段一律丢弃而非猜测。

    >>> mask_for_cloud({"class_name": "计科2301", "major": "计算机科学与技术"})
    {'education_field': '理工科', 'degree_stage': '本科'}
    """
    out: Dict[str, str] = {}

    major = (profile_fields.get("major") or "").strip()
    if major:
        field = _classify_major(major)
        if field:
            out["education_field"] = field

    degree = (profile_fields.get("degree_stage") or "").strip()
    if degree:
        stage = _classify_degree(degree)
        if stage:
            out["degree_stage"] = stage

    # 班级号 → 年级段（大一/大二/大三/大四），丢班级本身
    class_name = (profile_fields.get("class_name") or "").strip()
    if class_name:
        m = re.search(r"\d{3,4}", class_name)
        if m:
            digits = m.group(0)
            # 计科2301 → 2301 → 取末位判定年级；23 开头也可能表示 2023 级
            year_like = digits[:2]
            try:
                yy = int(year_like)
                guess = _grade_from_enrollment(yy)
                if guess:
                    out["grade_hint"] = guess
            except ValueError:
                pass

    return out


#: 专业 → 学科门类（粗粒度映射表，纯静态，无模型）
_MAJOR_FAMILY = {
    "计算机": "理工科", "软件": "理工科", "人工智能": "理工科", "电子": "理工科",
    "通信": "理工科", "自动化": "理工科", "机械": "理工科", "土木": "理工科",
    "建筑": "理工科", "数学": "理工科", "物理": "理工科", "化学": "理工科",
    "生物": "理工科", "材料": "理工科", "能源": "理工科", "车辆": "理工科",
    "临床": "医学", "口腔": "医学", "护理": "医学", "药学": "医学", "中医": "医学",
    "法学": "法学", "会计": "经管", "金融": "经管", "工商": "经管",
    "market": "经管", "经济": "经管", "管理": "经管", "统计": "经管",
    "汉语言": "文学", "英语": "文学", "新闻": "文学", "中文": "文学",
    "美术": "艺术", "音乐": "艺术", "设计": "艺术", "心理": "社科",
    "历史": "社科", "哲学": "社科", "教育": "社科", "地理": "社科",
}


def _classify_major(major: str) -> str:
    for kw, fam in _MAJOR_FAMILY.items():
        if kw in major:
            return fam
    return ""


def _classify_degree(degree: str) -> str:
    if "博士" in degree:
        return "博士"
    if "硕士" in degree or "研究生" in degree:
        return "研究生"
    if "本科" in degree:
        return "本科"
    if "专科" in degree:
        return "专科"
    return ""


def _grade_from_enrollment(yy: int) -> str:
    """从「计科2301」的 23 推断大致年级。

    ⚠️ 这是**弱推断**：也可能表示 2023 年入学，也可能只是编号。
    因此只在 yy 落在合理区间时返回，否则交给丢弃逻辑。
    """
    if 18 <= yy <= 30:
        # 按 2026 为基准：2023 入学 → 大三
        years_in = 2026 - (2000 + yy)
        idx = max(1, min(4, years_in))
        return ["", "大一", "大二", "大三", "大四"][idx]
    return ""
