"""测试课表解析逻辑"""
from bs4 import BeautifulSoup
import re

# 读取HTML源码
with open('../.qoder/教务系统源代码/学期课表.txt', 'r', encoding='utf-8') as f:
    html_content = f.read()

soup = BeautifulSoup(html_content, 'html.parser')

# 查找课表表格
schedule_table = soup.find('table', id='kbtable')
if not schedule_table:
    print("❌ 未找到id='kbtable'的表格")
    exit(1)

print("✅ 找到课表表格")

# 解析课表
courses = []
rows = schedule_table.find_all('tr')
print(f"总行数: {len(rows)}")

# 节次映射
period_map = {
    "第一二节": "1-2",
    "第三四节": "3-4",
    "第五六节": "5-6",
    "第七八节": "7-8",
    "第九十节": "9-10",
    "第十一十二节": "11-12"
}

# 跳过表头行（第一行是星期标题）
for row_idx, row in enumerate(rows):
    # 只跳过第一行（表头：星期一、星期二...）
    if row_idx == 0:
        print(f"行{row_idx}: 跳过（表头）")
        continue
    
    cells = row.find_all(['th', 'td'])
    print(f"\n行{row_idx}: 找到{len(cells)}个单元格")
    
    if len(cells) >= 8:
        # 节次信息
        period_text = cells[0].get_text(strip=True)
        period = period_map.get(period_text, period_text)
        print(f"  节次: {period_text} -> {period}")

        # 遍历每天的课程 (周一到周日)
        days = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
        for i, cell in enumerate(cells[1:8], 1):
            # 使用 kbcontent 解析（含教师信息）
            course_divs = cell.find_all('div', class_='kbcontent')
            
            for div_idx, div in enumerate(course_divs):
                div_text = div.get_text(strip=True)
                if not div_text or div_text == '\xa0':
                    continue
                
                print(f"  {days[i-1]}: 找到课程div {div_idx+1}")
                
                # kbcontent 多课程分隔符：21 个短横线
                inner_html = div.decode_contents()
                course_blocks_html = re.split(r'-{21,22}', inner_html)
                
                for block_idx, block_html in enumerate(course_blocks_html):
                    block_html = block_html.strip()
                    if not block_html:
                        continue
                    
                    # 用 BeautifulSoup 解析单个课程块
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
                    
                    # 用 font[title] 精确提取各字段
                    teacher_font = block_soup.find('font', title='老师')
                    teacher = teacher_font.get_text(strip=True) if teacher_font else ""
                    
                    weeks_font = block_soup.find('font', title='周次(节次)')
                    weeks = weeks_font.get_text(strip=True) if weeks_font else ""
                    
                    location_font = block_soup.find('font', title='教室')
                    location = location_font.get_text(strip=True) if location_font else ""
                    
                    # 节次信息（[XX-XX]节）
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
                    print(f"    ✅ 课程{block_idx+1}: {course_name} | {days[i-1]} | {period}节 | {teacher} | {location}")
    else:
        print(f"  ⚠️ 单元格数{len(cells)} < 8，跳过")

print(f"\n{'='*60}")
print(f"总计解析到 {len(courses)} 门课程")
print(f"{'='*60}")

# 显示所有课程
for idx, course in enumerate(courses, 1):
    print(f"{idx}. {course['课程名称']} - {course['星期']}第{course['节次']}节 - {course['教师']} - {course['地点']}")
