"""
测试学业进度解析
"""
import sys
from pathlib import Path
from bs4 import BeautifulSoup
import re

# 添加backend目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_academic_progress_parsing():
    """测试学业进度解析"""
    
    # 读取真实HTML文件
    html_file = Path(__file__).parent.parent / ".qoder" / "教务系统源代码" / "学业进度查询.txt"
    
    if not html_file.exists():
        print(f"❌ HTML文件不存在: {html_file}")
        return
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    # 提取返回样式部分（第255行开始）
    if '返回样式：' in html_content:
        html_content = html_content.split('返回样式：')[1]
    
    print("=" * 80)
    print("开始测试学业进度解析")
    print("=" * 80)
    
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 1. 提取总学分要求
    print("\n【步骤1】提取总学分要求")
    title_th = soup.find('th', colspan="7")
    if title_th:
        print(f"✅ 找到th[colspan=7]: {title_th.get_text(strip=True)}")
        credit_match = re.search(r'需修读总学分[：:]\s*(\d+)', title_th.get_text())
        if credit_match:
            total_credits = int(credit_match.group(1))
            print(f"✅ 提取总学分要求: {total_credits}")
        else:
            print("❌ 未匹配到总学分")
    else:
        print("❌ 未找到th[colspan=7]")
    
    # 2. 查找表格
    print("\n【步骤2】查找表格")
    progress_table = soup.find('table', class_=lambda x: x and 'Nsb_r_list' in x if x else False)
    
    if not progress_table:
        print("❌ 未找到Nsb_r_list表格，尝试查找所有表格")
        all_tables = soup.find_all('table')
        print(f"找到 {len(all_tables)} 个表格")
        for idx, table in enumerate(all_tables):
            rows = table.find_all('tr')
            print(f"  表格{idx}: {len(rows)}行")
            if len(rows) > 10:
                progress_table = table
                print(f"  ✅ 选择表格{idx}")
                break
    
    if not progress_table:
        print("❌ 未找到合适的表格")
        return
    
    # 3. 解析表格行
    print("\n【步骤3】解析表格行")
    rows = progress_table.find_all('tr')
    print(f"表格共有 {len(rows)} 行")
    
    # 分析每一行
    for row_idx, row in enumerate(rows):
        cells = row.find_all('td')
        th_cells = row.find_all('th')
        
        print(f"\n行{row_idx}:")
        print(f"  td数量: {len(cells)}, th数量: {len(th_cells)}")
        
        if th_cells:
            th_text = th_cells[0].get_text(strip=True)
            print(f"  th内容: {th_text[:50]}")
            if '需修读总学分' in th_text:
                print(f"  ✅ 这是总学分行")
        
        if cells:
            cell_texts = [cell.get_text(strip=True)[:20] for cell in cells]
            print(f"  td内容: {cell_texts}")
            
            # 检查是否是合计行
            row_text = row.get_text(strip=True)
            if '合计' in row_text:
                print(f"  ✅ 这是合计行！")
                print(f"  实际td数量: {len(cells)}")
                # 提取合计行的已获学分
                if len(cells) >= 2:
                    # 最后一个td是已获学分
                    earned_text = cells[-1].get_text(strip=True)
                    print(f"  已获学分: {earned_text}")
    
    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)

if __name__ == "__main__":
    test_academic_progress_parsing()
