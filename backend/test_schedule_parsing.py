"""
测试课表解析功能
使用真实HTML源代码验证解析逻辑
"""
import sys
from pathlib import Path
from bs4 import BeautifulSoup

# 添加backend目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_schedule_parsing():
    """测试课表解析"""
    
    # 读取真实HTML文件
    # 从backend目录向上找到项目根目录
    project_root = Path(__file__).parent.parent
    html_file = project_root / ".qoder" / "教务系统源代码" / "学期课表.txt"
    
    if not html_file.exists():
        print(f"❌ HTML文件不存在: {html_file}")
        return
    
    with open(html_file, 'r', encoding='utf-8') as f:
        html_content = f.read()
    
    print("=" * 80)
    print("开始测试课表解析")
    print("=" * 80)
    
    # 解析HTML
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # 查找课表表格
    schedule_table = soup.find('table', id='kbtable')
    
    if not schedule_table:
        print("❌ 未找到课表表格 (id='kbtable')")
        return
    
    print("✅ 找到课表表格")
    
    # 节次映射
    period_map = {
        "第一二节": "1-2",
        "第三四节": "3-4",
        "第五六节": "5-6",
        "第七八节": "7-8",
        "第九十节": "9-10",
        "第十一十二节": "11-12"
    }
    
    courses = []
    rows = schedule_table.find_all('tr')
    
    print(f"\n表格总行数: {len(rows)}")
    
    # 调试：打印每行的内容
    for idx, row in enumerate(rows):
        if idx < 3:
            print(f"\n行{idx} HTML片段: {str(row)[:200]}...")
    
    # 解析课程
    for row_idx, row in enumerate(rows):
        # 只跳过第一行（表头：星期一、星期二...）
        if row_idx == 0:
            continue
        
        cells = row.find_all(['th', 'td'])
        
        # 调试信息
        if row_idx < 3:
            print(f"\n行{row_idx}: 找到 {len(cells)} 个单元格")
        
        if len(cells) >= 8:
            period_text = cells[0].get_text(strip=True)
            period = period_map.get(period_text, period_text)
            
            days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            
            for i, cell in enumerate(cells[1:8], 1):
                # 查找kbcontent div（包含教师信息）
                course_divs = cell.find_all('div', class_='kbcontent')
                
                # 调试信息
                if i == 1 and row_idx == 1:  # 只打印第一个单元格的调试信息
                    print(f"\n调试：第{row_idx}行第{i}列找到 {len(course_divs)} 个kbcontent div")
                    for div_idx, div in enumerate(course_divs):
                        print(f"  div{div_idx}: {div.get_text(strip=True)[:50]}...")
                
                for div in course_divs:
                    if not div.get_text(strip=True):
                        continue
                    
                    # 解析课程块
                    import re
                    inner_html = div.decode_contents()
                    course_blocks_html = re.split(r'-{21,22}', inner_html)
                    
                    for block_html in course_blocks_html:
                        block_html = block_html.strip()
                        if not block_html:
                            continue
                        
                        block_soup = BeautifulSoup(
                            '<div>' + block_html + '</div>', 'html.parser'
                        )
                        
                        if not block_soup.get_text(strip=True):
                            continue
                        
                        lines = [
                            l.strip()
                            for l in block_soup.get_text(separator='\n').splitlines()
                            if l.strip()
                        ]
                        
                        if not lines:
                            continue
                        
                        course_name = lines[0]
                        
                        # 提取字段
                        teacher_font = block_soup.find('font', title='老师')
                        teacher = teacher_font.get_text(strip=True) if teacher_font else ""
                        
                        weeks_font = block_soup.find('font', title='周次(节次)')
                        weeks = weeks_font.get_text(strip=True) if weeks_font else ""
                        
                        location_font = block_soup.find('font', title='教室')
                        location = location_font.get_text(strip=True) if location_font else ""
                        
                        sections = ""
                        for line in lines:
                            if '节' in line and '[' in line:
                                sections = line
                                break
                        
                        course_data = {
                            "课程名称": course_name,
                            "星期": days[i-1],
                            "节次": period,
                            "教师": teacher,
                            "地点": location,
                            "周次": weeks,
                            "节次信息": sections
                        }
                        
                        courses.append(course_data)
    
    print(f"\n✅ 成功解析 {len(courses)} 门课程\n")
    print("=" * 80)
    print("课程列表:")
    print("=" * 80)
    
    for idx, course in enumerate(courses, 1):
        print(f"\n{idx}. {course['课程名称']}")
        print(f"   时间: {course['星期']} 第{course['节次']}节")
        print(f"   周次: {course['周次']}")
        print(f"   地点: {course['地点']}")
        print(f"   教师: {course['教师']}")
    
    print("\n" + "=" * 80)
    print("测试完成!")
    print("=" * 80)

if __name__ == "__main__":
    test_schedule_parsing()
