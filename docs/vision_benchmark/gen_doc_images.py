"""生成「文档类」测试图像（PPT / Word / Excel 截图风格）

用于评测本地多模态模型（qwen2.5vl:7b）对文档图像的识别能力。
样本程序化渲染，内容与项目自身领域一致，避免"背题"偏差。

用法：python docs/vision_benchmark/gen_doc_images.py
输出：同目录 images/ 下的 4 张样本图
"""
import os

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "images")
os.makedirs(OUT, exist_ok=True)

F_CN = r"C:\Windows\Fonts\msyh.ttc"
F_CN_BD = r"C:\Windows\Fonts\msyhbd.ttc"


def font(size, bold=False):
    return ImageFont.truetype(F_CN_BD if bold else F_CN, size)


# ────────────────────── 1. PPT 幻灯片 ──────────────────────
def make_ppt():
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)

    d.rectangle([0, 0, W, 86], fill="#1E3A5F")
    d.text((44, 22), "第三章  多智能体协同架构设计", font=font(38, True), fill="#FFFFFF")

    d.text((44, 122), "3.1  责任链编排与路由决策", font=font(26, True), fill="#1E3A5F")
    d.line([44, 160, 1180, 160], fill="#C8D4E3", width=2)

    bullets = [
        "编排顺序：Knowledge → Writer → Review → Judge → Result",
        "双阈值路由：complexity_score < 0.65 走本地 Ollama，≥ 0.65 上云 DeepSeek",
        "显存约束：单卡 8GB，单模型实例，视觉与文本统一为 qwen2.5vl:7b",
        "失败降级：Review 不可用时标记 degraded，而非伪造评分",
    ]
    y = 186
    for b in bullets:
        d.ellipse([50, y + 9, 60, y + 19], fill="#3B82F6")
        d.text((74, y), b, font=font(21), fill="#222222")
        y += 44

    col_x = [44, 384, 764, 1180]
    row_y = [404, 452, 500, 548, 596]
    header = ["模块", "模型调用次数", "是否可并行"]
    rows = [
        ["Knowledge", "0", "是（IO 密集）"],
        ["Writer", "7", "否（GPU 串行）"],
        ["Judge", "0", "否（纯规则）"],
    ]
    d.rectangle([col_x[0], row_y[0], col_x[3], row_y[-1]], outline="#8FA8C8", width=2)
    for i in range(1, 3):
        d.line([col_x[i], row_y[0], col_x[i], row_y[-1]], fill="#8FA8C8", width=2)
    for j in range(1, 4):
        d.line([col_x[0], row_y[j], col_x[3], row_y[j]], fill="#8FA8C8", width=2)
    d.rectangle([col_x[0], row_y[0], col_x[3], row_y[1]], fill="#E8EFF7")
    for i, h in enumerate(header):
        d.text((col_x[i] + 14, row_y[0] + 10), h, font=font(19, True), fill="#1E3A5F")
    for r, row in enumerate(rows):
        for i, cell in enumerate(row):
            d.text((col_x[i] + 14, row_y[r + 1] + 10), cell, font=font(19), fill="#222222")

    img.save(os.path.join(OUT, "01_ppt.png"))


# ────────────────────── 2. Word 文档 ──────────────────────
def make_word():
    W, H = 1000, 1250
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)

    d.text((70, 60), "4.2  技能图谱与自学习闭环", font=font(34, True), fill="#111111")

    para = "技能图谱以有向图形式组织任务的分解路径，节点表示可复用的子技能，"
    para2 = "边表示前置依赖关系。当 Review 模块给出低置信度反馈时，系统会生成"
    para3 = "候选补丁，经置信度过滤后进入待审核队列。"
    d.text((70, 126), para, font=font(20), fill="#333333")
    d.text((70, 160), para2, font=font(20), fill="#333333")
    d.text((70, 194), para3, font=font(20), fill="#333333")

    d.text((70, 258), "4.2.1  置信度过滤阈值", font=font(27, True), fill="#111111")

    items = [
        "高置信补丁（≥ 0.85）直接进入候选池，等待人工确认。",
        "中置信补丁（0.60 - 0.85）标记为待审核，不参与本次推理。",
        "低置信补丁（< 0.60）直接丢弃，避免噪声污染技能图谱。",
    ]
    y = 312
    for i, it in enumerate(items, 1):
        d.text((70, y), f"{i}. {it}", font=font(20), fill="#333333")
        y += 42

    d.text((70, 466), "表 4-2  补丁处理策略对照", font=font(19, True), fill="#444444")
    col_x = [70, 520, 930]
    row_y = [508, 550, 592, 634, 676]
    data = [
        ["置信度区间", "处理动作"],
        ["≥ 0.85", "进入候选池"],
        ["0.60 - 0.85", "标记待审核"],
        ["< 0.60", "丢弃"],
    ]
    d.rectangle([col_x[0], row_y[0], col_x[2], row_y[-1]], outline="#999999", width=2)
    for j in range(1, 4):
        d.line([col_x[0], row_y[j], col_x[2], row_y[j]], fill="#999999", width=2)
    d.line([col_x[1], row_y[0], col_x[1], row_y[-1]], fill="#999999", width=2)
    d.rectangle([col_x[0], row_y[0], col_x[2], row_y[1]], fill="#F0F0F0")
    for r, row in enumerate(data):
        for i, cell in enumerate(row):
            d.text((col_x[i] + 14, row_y[r] + 10), cell, font=font(20), fill="#222222")

    d.text((70, 726), "注：阈值可在 configs/ 下的 YAML 中调整，无需改代码。",
           font=font(17), fill="#666666")

    img.save(os.path.join(OUT, "02_word.png"))


# ────────────────────── 3. Excel 表格 ──────────────────────
def make_excel():
    W, H = 1080, 470
    img = Image.new("RGB", (W, H), "#FFFFFF")
    d = ImageDraw.Draw(img)

    d.text((30, 20), "40Q 跨域评测结果（节选）", font=font(24, True), fill="#111111")

    headers = ["编号", "题目域", "复杂度", "路由", "耗时(s)", "Review"]
    rows = [
        ["Q01", "算法", "0.42", "本地", "18.3", "0.86"],
        ["Q02", "商业", "0.78", "云端", "9.7", "0.91"],
        ["Q03", "生活", "0.31", "本地", "12.4", "0.79"],
        ["Q04", "学术", "0.88", "云端", "11.2", "0.94"],
        ["Q05", "算法", "0.55", "本地", "26.8", "0.83"],
        ["Q06", "商业", "0.64", "本地", "31.5", "0.72"],
    ]
    col_w = [86, 150, 150, 130, 160, 150]
    x0, y0 = 30, 66
    rh = 46
    xs = [x0]
    for w in col_w:
        xs.append(xs[-1] + w)

    n = len(rows) + 1
    d.rectangle([x0, y0, xs[-1], y0 + rh * n], outline="#7F7F7F", width=2)
    for i in range(1, len(col_w)):
        d.line([xs[i], y0, xs[i], y0 + rh * n], fill="#7F7F7F", width=1)
    for j in range(1, n):
        d.line([x0, y0 + rh * j, xs[-1], y0 + rh * j], fill="#7F7F7F", width=1)

    d.rectangle([x0, y0, xs[-1], y0 + rh], fill="#E6E6E6")
    for i, h in enumerate(headers):
        d.text((xs[i] + 14, y0 + 12), h, font=font(19, True), fill="#111111")
    for r, row in enumerate(rows):
        for i, cell in enumerate(row):
            d.text((xs[i] + 14, y0 + rh * (r + 1) + 12), cell, font=font(19), fill="#222222")

    img.save(os.path.join(OUT, "03_excel.png"))


def make_excel_degraded():
    """模拟真实用户上传：分辨率减半 + JPEG 强压缩（手机拍屏/截图二次压缩）"""
    src = Image.open(os.path.join(OUT, "03_excel.png")).convert("RGB")
    small = src.resize((src.width // 2, src.height // 2), Image.LANCZOS)
    small.save(os.path.join(OUT, "04_excel_lowres.jpg"), "JPEG", quality=42)


if __name__ == "__main__":
    make_ppt()
    make_word()
    make_excel()
    make_excel_degraded()

    lines = []
    for name in ("01_ppt.png", "02_word.png", "03_excel.png", "04_excel_lowres.jpg"):
        p = os.path.join(OUT, name)
        with Image.open(p) as im:
            lines.append(f"{name}  {im.size[0]}x{im.size[1]}  {os.path.getsize(p) // 1024} KB")
    with open(os.path.join(HERE, "gen.log"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
