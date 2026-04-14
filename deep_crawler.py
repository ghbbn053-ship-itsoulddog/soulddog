#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
深度优先智能爬虫 - 树形结构逐层爬取
功能：
1. 从主页开始，逐层深入爬取
2. 分析每个页面的所有链接、表单、iframe
3. 自动提交表单获取数据
4. 递归爬取子页面
5. 保存所有HTML和分析结果
"""

import sys
import os
from bs4 import BeautifulSoup
import re
import json
from urllib.parse import urljoin, urlparse
from collections import deque

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from scraper import JwxtScraper
import requests

class DeepCrawler:
    """深度优先爬虫"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        })
        self.base_url = "http://172.19.13.62:80/jsxsd"
        self.scraper = JwxtScraper(self.session, self.base_url)
        
        # 保存目录
        self.output_dir = os.path.join(os.path.dirname(__file__), 'deep_crawl')
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 已访问的URL集合（避免重复）
        self.visited = set()
        
        # 爬取队列：(url, depth, parent_url)
        self.queue = deque()
        
        # 爬取树结构
        self.crawl_tree = {
            'url': self.base_url,
            'children': [],
            'data': {}
        }
        
        # 重要数据收集
        self.found_data = {
            'grades': [],
            'schedule': [],
            'training_plan': [],
            'academic_progress': [],
            'personal_info': {}
        }
    
    def save_html(self, filename, content, depth=0):
        """保存HTML到本地"""
        # 按深度创建子目录
        depth_dir = os.path.join(self.output_dir, f'depth_{depth}')
        os.makedirs(depth_dir, exist_ok=True)
        
        filepath = os.path.join(depth_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath
    
    def save_json(self, filename, data):
        """保存JSON数据"""
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"   💾 JSON已保存: {filepath}")
    
    def extract_links(self, soup, current_url):
        """提取页面中的所有链接"""
        links = []
        
        for a in soup.find_all('a', href=True):
            href = a['href'].strip()
            text = a.get_text(strip=True)
            
            # 跳过无效链接
            if not href or href.startswith('javascript:') or href.startswith('#'):
                continue
            
            # 转换为绝对URL
            if href.startswith('http'):
                absolute_url = href
            else:
                absolute_url = urljoin(current_url, href)
            
            # 只保留同域名的链接
            if self.base_url.split('/jsxsd')[0] in absolute_url:
                links.append({
                    'url': absolute_url,
                    'text': text or '(无文本)',
                    'href': href
                })
        
        return links
    
    def extract_forms(self, soup, current_url):
        """提取页面中的所有表单"""
        forms = []
        
        for form in soup.find_all('form'):
            action = form.get('action', '')
            method = form.get('method', 'get').lower()
            
            # 构建完整的表单URL
            if action:
                if action.startswith('http'):
                    form_url = action
                else:
                    form_url = urljoin(current_url, action)
            else:
                form_url = current_url
            
            # 提取所有输入字段
            inputs = {}
            for inp in form.find_all(['input', 'select', 'textarea']):
                name = inp.get('name', '')
                if not name:
                    continue
                
                input_type = inp.get('type', 'text')
                value = inp.get('value', '')
                
                # 对于select，获取option值
                if inp.name == 'select':
                    options = [opt.get('value', '') for opt in inp.find_all('option') if opt.get('value')]
                    inputs[name] = {
                        'type': 'select',
                        'value': value,
                        'options': options
                    }
                else:
                    inputs[name] = {
                        'type': input_type,
                        'value': value
                    }
            
            forms.append({
                'url': form_url,
                'method': method,
                'inputs': inputs,
                'action': action
            })
        
        return forms
    
    def extract_iframes(self, soup, current_url):
        """提取iframe"""
        iframes = []
        
        for iframe in soup.find_all('iframe'):
            src = iframe.get('src', '')
            if src:
                if src.startswith('http'):
                    absolute_url = src
                else:
                    absolute_url = urljoin(current_url, src)
                iframes.append(absolute_url)
        
        return iframes
    
    def submit_form(self, form_info):
        """提交表单并获取结果"""
        try:
            url = form_info['url']
            method = form_info['method']
            data = {}
            
            # 准备表单数据
            for name, info in form_info['inputs'].items():
                if isinstance(info, dict):
                    data[name] = info.get('value', '')
                else:
                    data[name] = info
            
            print(f"   📝 提交表单: {url}")
            print(f"      数据: {json.dumps(data, ensure_ascii=False)[:200]}")
            
            if method == 'post':
                response = self.session.post(url, data=data, timeout=10)
            else:
                response = self.session.get(url, params=data, timeout=10)
            
            html_content = self.scraper._fix_encoding(response)
            return html_content
            
        except Exception as e:
            print(f"   ❌ 表单提交失败: {e}")
            return None
    
    def analyze_and_crawl_page(self, url, depth=0, max_depth=5, parent_node=None):
        """递归分析和爬取页面"""
        # 避免重复访问
        if url in self.visited:
            return None
        self.visited.add(url)
        
        # 检查深度限制
        if depth > max_depth:
            return None
        
        indent = "  " * depth
        print(f"\n{indent}{'='*60}")
        print(f"{indent}📄 [深度 {depth}] 爬取: {url}")
        print(f"{'='*60}")
        
        try:
            # 请求页面
            response = self.session.get(url, timeout=10)
            html_content = self.scraper._fix_encoding(response)
            
            # 检查是否是错误页面
            if '非法访问' in html_content or '错误提示' in html_content:
                print(f"{indent}⚠️  非法访问，跳过")
                return None
            
            # 保存HTML
            safe_name = re.sub(r'[^\w\-_\.]', '_', urlparse(url).path or 'page')
            if len(safe_name) > 50:
                safe_name = safe_name[:50]
            filename = f'{depth}_{safe_name}.html'
            filepath = self.save_html(filename, html_content, depth)
            print(f"{indent}💾 已保存: {filepath}")
            
            # 解析HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            page_text = soup.get_text(strip=True)
            
            # 创建当前节点
            current_node = {
                'url': url,
                'depth': depth,
                'filepath': filepath,
                'children': [],
                'forms': [],
                'data_found': []
            }
            
            if parent_node:
                parent_node['children'].append(current_node)
            
            # 提取链接
            links = self.extract_links(soup, url)
            print(f"{indent}🔗 发现 {len(links)} 个链接")
            
            # 提取表单
            forms = self.extract_forms(soup, url)
            if forms:
                print(f"{indent}📝 发现 {len(forms)} 个表单")
                current_node['forms'] = forms
            
            # 提取iframe
            iframes = self.extract_iframes(soup, url)
            if iframes:
                print(f"{indent}🖼️  发现 {len(iframes)} 个iframe")
                links.extend([{'url': ifr, 'text': 'iframe'} for ifr in iframes])
            
            # 检测页面类型并提取数据
            data_type = self.detect_page_type(page_text, soup, url)
            if data_type:
                print(f"{indent}🎯 检测到页面类型: {data_type}")
                current_node['data_found'].append(data_type)
                
                # 根据页面类型提取数据
                if data_type == 'grades':
                    self.extract_grades(soup, depth)
                elif data_type == 'schedule':
                    self.extract_schedule(soup, depth)
                elif data_type == 'training_plan':
                    self.extract_training_plan(soup, depth)
                elif data_type == 'academic_progress':
                    self.extract_academic_progress(soup, depth)
                elif data_type == 'personal_info':
                    self.extract_personal_info(soup, depth)
            
            # 如果有表单，尝试提交
            if forms and depth < max_depth - 1:
                for i, form in enumerate(forms):
                    print(f"\n{indent}📤 尝试提交表单 {i+1}/{len(forms)}...")
                    result_html = self.submit_form(form)
                    
                    if result_html and len(result_html) > 500:
                        # 保存表单提交结果
                        form_filename = f'{depth}_form_result_{i}.html'
                        form_filepath = self.save_html(form_filename, result_html, depth)
                        print(f"{indent}✅ 表单提交成功，结果保存到: {form_filepath}")
                        
                        # 分析表单结果页面
                        self.analyze_and_crawl_page(
                            form['url'], 
                            depth + 1, 
                            max_depth, 
                            current_node
                        )
            
            # 递归爬取链接（深度优先）
            if links and depth < max_depth:
                print(f"\n{indent}🔍 开始爬取子页面...")
                
                # 过滤和排序链接（优先爬取重要页面）
                important_keywords = ['cjcx', 'kbcx', 'pyfa', 'xyjd', 'xk', 'kscj']
                important_links = []
                normal_links = []
                
                for link in links:
                    if any(keyword in link['url'] for keyword in important_keywords):
                        important_links.append(link)
                    else:
                        normal_links.append(link)
                
                # 先爬取重要链接
                for link in important_links[:10]:  # 最多10个重要链接
                    if link['url'] not in self.visited:
                        print(f"\n{indent}➡️  爬取重要链接: {link['text']}")
                        self.analyze_and_crawl_page(
                            link['url'], 
                            depth + 1, 
                            max_depth, 
                            current_node
                        )
                
                # 再爬取普通链接
                for link in normal_links[:5]:  # 最多5个普通链接
                    if link['url'] not in self.visited:
                        self.analyze_and_crawl_page(
                            link['url'], 
                            depth + 1, 
                            max_depth, 
                            current_node
                        )
            
            return current_node
            
        except Exception as e:
            print(f"{indent}❌ 爬取失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def detect_page_type(self, page_text, soup, url):
        """检测页面类型"""
        if any(keyword in page_text for keyword in ['课程成绩', '成绩', '分数', '绩点']):
            return 'grades'
        elif any(keyword in page_text for keyword in ['课表', '课程表', '学期课表']):
            return 'schedule'
        elif any(keyword in page_text for keyword in ['培养方案', '执行计划', '课程列表']):
            return 'training_plan'
        elif any(keyword in page_text for keyword in ['学业进度', '修读', '已修']):
            return 'academic_progress'
        elif any(keyword in page_text for keyword in ['学籍表', '个人信息', '姓名：', '学号：']):
            return 'personal_info'
        return None
    
    def extract_grades(self, soup, depth):
        """提取成绩数据"""
        print(f"  {'  '*depth}📊 正在提取成绩数据...")
        
        # 查找成绩表格
        tables = soup.find_all('table')
        for table in tables:
            headers = [th.get_text(strip=True) for th in table.find_all('th')]
            if any(h in headers for h in ['课程名称', '成绩', '学分', '绩点']):
                rows = table.find_all('tr')[1:]  # 跳过表头
                for row in rows:
                    cells = [td.get_text(strip=True) for td in row.find_all('td')]
                    if len(cells) >= 3:
                        grade_data = {
                            '课程名称': cells[0] if len(cells) > 0 else '',
                            '成绩': cells[1] if len(cells) > 1 else '',
                            '学分': cells[2] if len(cells) > 2 else '',
                        }
                        self.found_data['grades'].append(grade_data)
                
                print(f"  {'  '*depth}✅ 找到 {len(rows)} 条成绩记录")
                break
    
    def extract_schedule(self, soup, depth):
        """提取课表数据"""
        print(f"  {'  '*depth}📅 正在提取课表数据...")
        
        # 查找课表表格
        schedule_table = soup.find('table', id='timetable') or soup.find('table', class_='timetable')
        if not schedule_table:
            # 尝试查找包含"课表"的表格
            for table in soup.find_all('table'):
                if '课表' in table.get_text():
                    schedule_table = table
                    break
        
        if schedule_table:
            print(f"  {'  '*depth}✅ 找到课表表格")
            # 保存原始HTML供后续分析
            self.save_html(
                f'{depth}_schedule_found.html',
                str(schedule_table),
                depth
            )
    
    def extract_training_plan(self, soup, depth):
        """提取培养方案数据"""
        print(f"  {'  '*depth}📚 正在提取培养方案数据...")
        
        # 查找培养方案表格
        tables = soup.find_all('table')
        for table in tables:
            table_text = table.get_text()
            if '课程' in table_text and '学分' in table_text:
                rows = table.find_all('tr')
                print(f"  {'  '*depth}✅ 找到培养方案表格，共 {len(rows)} 行")
                # 保存原始HTML
                self.save_html(
                    f'{depth}_training_plan_found.html',
                    str(table),
                    depth
                )
                break
    
    def extract_academic_progress(self, soup, depth):
        """提取学业进度数据"""
        print(f"  {'  '*depth}📈 正在提取学业进度数据...")
        
        tables = soup.find_all('table')
        for table in tables:
            if '学业进度' in table.get_text() or '修读' in table.get_text():
                print(f"  {'  '*depth}✅ 找到学业进度表格")
                self.save_html(
                    f'{depth}_academic_progress_found.html',
                    str(table),
                    depth
                )
                break
    
    def extract_personal_info(self, soup, depth):
        """提取个人信息"""
        print(f"  {'  '*depth}👤 正在提取个人信息...")
        
        # 查找个人信息
        text = soup.get_text()
        
        # 提取姓名
        name_match = re.search(r'姓名[：:]\s*(\S+)', text)
        if name_match:
            self.found_data['personal_info']['name'] = name_match.group(1)
        
        # 提取学号
        sid_match = re.search(r'学号[：:]\s*(\d+)', text)
        if sid_match:
            self.found_data['personal_info']['student_id'] = sid_match.group(1)
        
        # 提取专业
        major_match = re.search(r'专业[：:]\s*(\S+)', text)
        if major_match:
            self.found_data['personal_info']['major'] = major_match.group(1)
        
        if self.found_data['personal_info']:
            print(f"  {'  '*depth}✅ 个人信息: {json.dumps(self.found_data['personal_info'], ensure_ascii=False)}")
    
    def run(self, username, password, captcha, start_urls=None, max_depth=5):
        """运行深度爬取"""
        print("="*80)
        print("🚀 深度优先智能爬虫启动")
        print("="*80)
        print(f"👤 学号: {username}")
        print(f"📁 输出目录: {self.output_dir}")
        print(f"🔍 最大深度: {max_depth}")
        print()
        
        # 登录
        print("="*80)
        print("🔐 步骤1: 登录")
        print("="*80)
        
        result = self.scraper.login(username, password, captcha)
        if not result.get('success'):
            print(f"❌ 登录失败: {result.get('message')}")
            return
        
        print("✅ 登录成功!")
        
        # 如果没有指定起始URL，从主页开始
        if not start_urls:
            start_urls = [
                f"{self.base_url}/framework/xsMain.jsp",  # 主页
            ]
        
        # 开始深度爬取
        print("\n" + "="*80)
        print("🌳 步骤2: 深度优先爬取")
        print("="*80)
        
        for start_url in start_urls:
            self.analyze_and_crawl_page(start_url, depth=0, max_depth=max_depth, parent_node=self.crawl_tree)
        
        # 保存结果
        print("\n" + "="*80)
        print("💾 步骤3: 保存结果")
        print("="*80)
        
        self.save_json('crawl_tree.json', self.crawl_tree)
        self.save_json('found_data.json', self.found_data)
        self.save_json('visited_urls.json', list(self.visited))
        
        # 打印统计
        print(f"\n📊 爬取统计:")
        print(f"   - 访问URL数: {len(self.visited)}")
        print(f"   - 找到成绩: {len(self.found_data['grades'])} 条")
        print(f"   - 找到个人信息: {bool(self.found_data['personal_info'])}")
        print(f"   - 爬取树深度: 最大 {max_depth} 层")
        print(f"\n📁 所有文件保存在: {self.output_dir}")
        print(f"\n✅ 深度爬取完成！")


def main():
    """主函数"""
    print("="*80)
    print("🕷️  深度优先智能爬虫")
    print("="*80)
    print()
    print("本爬虫将:")
    print("  1. 从主页开始，逐层深入")
    print("  2. 分析每个页面的链接、表单、iframe")
    print("  3. 自动提交表单获取数据")
    print("  4. 递归爬取所有子页面")
    print("  5. 保存完整的爬取树和所有数据")
    print()
    
    # 登录信息
    username = "24251102121"
    password = "zj2831623154"
    
    # 创建爬虫
    crawler = DeepCrawler()
    
    # 下载验证码
    print("📥 下载验证码...")
    try:
        captcha_bytes = crawler.scraper.get_captcha()
        captcha_path = os.path.join(os.path.dirname(__file__), 'captcha.jpg')
        with open(captcha_path, 'wb') as f:
            f.write(captcha_bytes)
        
        print(f"✅ 验证码已保存: {captcha_path}")
        
        # 打开图片
        if sys.platform == 'win32':
            try:
                os.startfile(captcha_path)
            except:
                pass
        
        captcha = input("\n请输入验证码: ").strip()
    except Exception as e:
        print(f"❌ 验证码下载失败: {e}")
        return
    
    # 运行深度爬取
    crawler.run(
        username=username,
        password=password,
        captcha=captcha,
        max_depth=5  # 最大深度5层
    )


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断")
    except Exception as e:
        print(f"\n❌ 错误: {e}")
        import traceback
        traceback.print_exc()
