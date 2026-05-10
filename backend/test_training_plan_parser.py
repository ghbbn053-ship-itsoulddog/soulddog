"""
培养方案解析回归测试
优先使用本地抓取到的真实 HTML 进行验证。
"""

from pathlib import Path

from scraper import JwxtScraper


def test_training_plan_html_structure():
    html_path = Path(__file__).parent / "tmp" / "jwxt_training_plan_page_live.html"
    assert html_path.exists(), "缺少真实培养方案 HTML 样本"

    scraper = JwxtScraper(base_url="http://jwxt.gdufe.edu.cn/jsxsd/")
    plan = scraper._parse_training_plan_html(html_path.read_text(encoding="utf-8"))

    assert plan["基本信息"]["方案名称"] == "计算机科学与技术 2024版"
    assert "培养目标" in plan["方案说明"]["章节"]
    assert plan["学分统计"]["总学分要求"] == 160
    assert len(plan["学分分布"]) >= 4
    assert len(plan["课程列表"]) >= 20
    assert any(row["课程名称"] == "马克思主义基本原理" for row in plan["课程列表"])


if __name__ == "__main__":
    test_training_plan_html_structure()
    print("training plan parser tests passed")
