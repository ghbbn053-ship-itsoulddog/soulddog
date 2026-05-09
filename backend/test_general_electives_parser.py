"""
通识选修课程一览表解析回归测试
"""

from pathlib import Path

from scraper import JwxtScraper


def test_general_electives_parser():
    html_path = Path(__file__).parent / "tmp" / "txxxjh_query_cktxk_tsk.html"
    assert html_path.exists(), "缺少通识选修课程 HTML 样本"

    scraper = JwxtScraper(base_url="http://jwxt.gdufe.edu.cn/jsxsd/")
    parsed = scraper._parse_general_electives_html(html_path.read_text(encoding="utf-8"), elective_type="tsk")

    assert parsed["标题"] == "广东财经大学通识选修课程设置一览表"
    assert parsed["数量"] > 500
    assert len(parsed["课程列表"]) == parsed["数量"]
    assert len(parsed["课程模块列表"]) >= 10
    assert parsed["课程列表"][0]["课程名称"]
    assert parsed["课程列表"][0]["课程代码"]
    assert any(course["课程名称"] == "粤语入门" for course in parsed["课程列表"])
    assert any("网站开发与管理" in course["课程名称"] for course in parsed["课程列表"])
    assert any(course["序号"] == "946" for course in parsed["课程列表"])


if __name__ == "__main__":
    test_general_electives_parser()
    print("general electives parser tests passed")
