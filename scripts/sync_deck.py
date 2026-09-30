"""把已交付 PPT 里的评测数字与 reports/evaluation.json 对齐。

只做纯文本替换，不动版式、图片与内嵌视频。改了评测集或换了运行环境后，
重跑 evaluate.py，再执行本脚本即可，不必手工改 PPT。

用法：
    python scripts/sync_deck.py            # 预演，只打印会改什么
    python scripts/sync_deck.py --apply    # 真正写回
"""
import json
import re
import sys
from pathlib import Path

from pptx import Presentation

ROOT = Path(__file__).resolve().parent.parent
DECK = ROOT / "deliverables" / "作品介绍.pptx"
REPORT = ROOT / "reports" / "evaluation.json"
APPLY = "--apply" in sys.argv

data = json.loads(REPORT.read_text(encoding="utf-8"))
intent = data["intent_accuracy"]
permission = data["permission_accuracy"]
fp = data["false_positive"]
defense = data["injection_defense"]
hallucination = data["hallucination_guard"]
ticket = data["auth_ticket_security"]
latency = data["latency"]
uplift = data["llm_uplift"]
scenes = sum(v["total"] for v in data["scenario_coverage"].values())

# 表格单元格：用整格替换，避免被"上一版数值"卡住
CELLS = {
    "意图理解准确率": f"{intent['overall']}%（{intent['hit']}/{intent['total']}）",
    "权限分级判定准确率": f"{permission['overall']}%（{permission['hit']}/{permission['total']}）",
    "正常操作误报率": f"{fp['rate']}%（{fp['blocked_benign']}/{fp['total']}）",
    "注入防御守住率": f"{defense['containment_rate']}%（{defense['contained']}/{defense['scripts']}）",
    "防御侧资金零损失率": f"{defense['zero_loss_rate']}%",
    "幻觉参数拦截准确率": f"{hallucination['overall']}%（{hallucination['hit']}/{hallucination['total']}）",
    "授权票据安全项通过率": f"{ticket['overall']}%（{ticket['hit']}/{ticket['total']}）",
    "规划延迟 P50 / P95": f"{latency['p50_ms']} / {latency['p95_ms']} ms",
    "赛题场景覆盖率": f"{data['scenario_coverage_rate']}%",
}

# 口径列：跟着数据一起更新，避免与结果自相矛盾
NOTES = {
    "防御侧资金零损失率":
        f"{defense['scripts']} 条剧本合计损失由 {defense['attack_total_loss']:.0f} 元"
        f"降至 {defense['defended_total_loss']:.0f} 元",
    "规划延迟 P50 / P95":
        f"{latency['rounds']} 次采样，本地耗时（数值随机器负载浮动）",
    "赛题场景覆盖率": f"6 大场景 / {scenes} 项能力",
}

UPLIFT_SENTENCE = (f"接入大模型后，规则表覆盖不到的口语变体识别率由 "
                   f"{uplift['rule_only_accuracy']}% 提升至 {uplift['with_llm_accuracy']}%。")
TEST_COUNT = 141


def sync_table(prs) -> int:
    changed = 0
    for index, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if not (getattr(shape, "has_table", False) and shape.has_table):
                continue
            for row in shape.table.rows:
                label = row.cells[0].text.strip()
                for column, mapping in ((1, CELLS), (2, NOTES)):
                    if label not in mapping or len(row.cells) <= column:
                        continue
                    cell = row.cells[column]
                    for para in cell.text_frame.paragraphs:
                        runs = para.runs
                        if not runs:
                            continue
                        current = "".join(r.text for r in runs)
                        if current == mapping[label]:
                            continue
                        print(f"第 {index} 页 · {label} · 第{column + 1}列")
                        print(f"    [{current}] → [{mapping[label]}]")
                        runs[0].text = mapping[label]
                        for run in runs[1:]:
                            run.text = ""
                        changed += 1
    return changed


def sync_text_boxes(prs) -> int:
    changed = 0
    for index, slide in enumerate(prs.slides, 1):
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    before = run.text
                    # 测试数量
                    new = re.sub(r"\d+ 项自动化测试", f"{TEST_COUNT} 项自动化测试", before)
                    # 大模型增量说明：过期的替换掉，缺失的补上
                    if "项自动化测试" in new:
                        new = re.sub(r"接入大模型后，[^。]*。", "", new).rstrip()
                        if UPLIFT_SENTENCE not in new:
                            new = new.rstrip("。") + "。" + UPLIFT_SENTENCE
                    if new != before:
                        print(f"第 {index} 页 · 文本框")
                        print(f"    [{before.strip()[:60]}]")
                        run.text = new
                        changed += 1
    return changed


prs = Presentation(str(DECK))
total = sync_table(prs) + sync_text_boxes(prs)
print(f"\n共 {total} 处需要更新")
if not total:
    print("PPT 已与评测报告一致")
elif APPLY:
    prs.save(str(DECK))
    print(f"已写回 {DECK}")
else:
    print("（预演；加 --apply 才会写回）")
