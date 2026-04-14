#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能爬虫自动测试 - 完全自动化爬取和解析
功能：
1. 自动登录教务系统
2. 自动爬取所有页面
3. 自动解析HTML结构
4. 自动推断下一个URL和表单数据
5. 保存所有原始HTML供分析
"""

import sys
import os
from bs4 import BeautifulSoup
import re
import json

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from scraper import JwxtScraper
import requests

class SmartCrawlerTester:
    """智能爬虫测试器"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        self.base_url = "http://172.19.13.62:80/jsxsd"
        self.scraper = JwxtScraper(self.session, self.base_url)
        self.html_dir = os.path.join(os.path.dirname(__file__), 'crawled_html')
        os.makedirs(self.html_dir, exist_ok=True)
        
    def save_html(self, filename, content):
        """保存HTML到本地"""
        filepath = os.path.join(self.html_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"   💾 已保存: {filepath}")
        return filepath
    
    def analyze_html(self, html_content, page_name):
        """分析HTML结构，提取关键信息"""
        soup = BeautifulSoup(html_content, 'html.parser')
        
        print(f"\n{'='*80}")
        print(f"📊 分析页面: {page_name}")
        print(f"{'='*80}")
        
        # 1. 提取所有链接
        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True)
            if href and not href.startswith('javascript:') and not href.startswith('#'):
                links.append({'text': text, 'href': href})
        
        if links:
            print(f"\n🔗 发现 {len(links)} 个链接:")
            for i, link in enumerate(links[:20], 1):  # 只显示前20个
                print(f"   {i}. {link['text'] or '(无文本)'} -> {link['href']}")
        
        # 2. 提取所有表单
        forms = []
        for form in soup.find_all('form'):
            form_info = {
                'action': form.get('action', ''),
                'method': form.get('method', 'get'),
                'inputs': []
            }
            for inp in form.find_all(['input', 'select', 'textarea']):
                input_info = {
                    'type': inp.get('type', 'text'),
                    'name': inp.get('name', ''),
                    'value': inp.get('value', ''),
                    'id': inp.get('id', '')
                }
                form_info['inputs'].append(input_info)
            forms.append(form_info)
        
        if forms:
            print(f"\n📝 发现 {len(forms)} 个表单:")
            for i, form in enumerate(forms, 1):
                print(f"   表单 {i}: action={form['action']}, method={form['method']}")
                print(f"      输入字段:")
                for inp in form['inputs']:
                    print(f"      - {inp['type']}: name={inp['name']}, value={inp['value'][:30] if inp['value'] else ''}")
        
        # 3. 提取iframe
        iframes = soup.find_all('iframe')
        if iframes:
            print(f"\n🖼️  发现 {len(iframes)} 个iframe:")
            for i, iframe in enumerate(iframes, 1):
                src = iframe.get('src', '')
                name = iframe.get('name', '')
                print(f"   {i}. name={name}, src={src}")
        
        # 4. 提取JavaScript中的URL
        scripts = soup.find_all('script')
        js_urls = set()
        for script in scripts:
            if script.string:
                # 查找 window.location, href, src 等
                url_pattern = r'''(?:window\.location\.href|location\.href|href|src|action)\s*=\s*['"]([^'"]+)['"]'''
                matches = re.findall(url_pattern, script.string)
                js_urls.update(matches)
        
        if js_urls:
            print(f"\n💻 JavaScript中发现 {len(js_urls)} 个URL:")
            for url in list(js_urls)[:10]:
                print(f"   - {url}")
        
        return {
            'links': links,
            'forms': forms,
            'iframes': iframes,
            'js_urls': list(js_urls)
        }
    
    def download_captcha(self):
        """下载验证码"""
        print("\n" + "="*80)
        print("📥 步骤1: 下载验证码")
        print("="*80)
        
        try:
            captcha_bytes = self.scraper.get_captcha()
            captcha_path = os.path.join(os.path.dirname(__file__), 'captcha.jpg')
            with open(captcha_path, 'wb') as f:
                f.write(captcha_bytes)
            
            print(f"✅ 验证码下载成功: {len(captcha_bytes)} bytes")
            print(f"📁 保存位置: {captcha_path}")
            
            # 尝试打开图片
            if sys.platform == 'win32':
                try:
                    os.startfile(captcha_path)
                    print("🖼️  已尝试打开图片")
                except:
                    pass
            
            return captcha_path
        except Exception as e:
            print(f"❌ 验证码下载失败: {e}")
            return None
    
    def login(self, username, password, captcha):
        """登录教务系统"""
        print("\n" + "="*80)
        print("🔐 步骤2: 登录教务系统")
        print("="*80)
        
        result = self.scraper.login(username, password, captcha)
        
        if result.get('success'):
            print(f"✅ 登录成功!")
            print(f"   响应: {result}")
            return True
        else:
            print(f"❌ 登录失败: {result.get('message')}")
            return False
    
    def crawl_main_page(self):
        """爬取主页面并分析"""
        print("\n" + "="*80)
        print("📄 步骤3: 爬取主页面 (xsMain.jsp)")
        print("="*80)
        
        try:
            # 访问主页面
            main_url = f"{self.base_url}/framework/xsMain.jsp"
            print(f"🌐 请求URL: {main_url}")
            
            response = self.session.get(main_url, timeout=10)
            html_content = self.scraper._fix_encoding(response)
            
            # 保存HTML
            self.save_html('01_main_page.html', html_content)
            
            # 分析HTML
            analysis = self.analyze_html(html_content, '主页面')
            
            # 提取个人信息
            print(f"\n👤 提取个人信息:")
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找包含个人信息的区域
            for div in soup.find_all(['div', 'td', 'span']):
                text = div.get_text(strip=True)
                if '姓名' in text and '学号' in text:
                    print(f"   找到个人信息块: {text[:100]}")
                    break
            
            return analysis
        except Exception as e:
            print(f"❌ 爬取主页面失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def crawl_all_menu_items(self, analysis):
        """爬取所有菜单项"""
        print("\n" + "="*80)
        print("📑 步骤4: 爬取所有菜单页面")
        print("="*80)
        
        if not analysis or 'links' not in analysis:
            print("⚠️  没有发现链接，跳过")
            return
        
        # 过滤出有意义的链接
        important_links = []
        for link in analysis['links']:
            href = link['href']
            text = link['text']
            
            # 跳过javascript和空链接
            if not href or href.startswith('javascript:') or href == '#':
                continue
            
            # 只保留包含关键路径的链接
            if any(keyword in href for keyword in ['kscj', 'xk', 'kb', 'cj', 'px', 'xl', 'pyfa', 'grxx']):
                important_links.append(link)
        
        print(f"\n🎯 发现 {len(important_links)} 个重要链接:")
        
        crawled = 0
        for i, link in enumerate(important_links[:15], 1):  # 最多爬取15个
            print(f"\n--- 链接 {i}/{min(15, len(important_links))} ---")
            print(f"📌 {link['text']} -> {link['href']}")
            
            try:
                # 构建完整URL（避免双/jsxsd/）
                href = link['href']
                
                # 如果href已经包含 /jsxsd/，直接使用base_url的域名部分
                if '/jsxsd/' in href:
                    # 提取 /jsxsd/ 后面的部分
                    path = href.split('/jsxsd/', 1)[1]
                    full_url = f"{self.base_url}/{path}"
                elif href.startswith('/'):
                    full_url = f"{self.base_url}{href}"
                else:
                    full_url = f"{self.base_url}/{href}"
                
                print(f"🌐 请求: {full_url}")
                
                # 请求页面
                response = self.session.get(full_url, timeout=10)
                html_content = self.scraper._fix_encoding(response)
                
                # 检查是否是错误页面
                if '非法访问' in html_content or '错误提示' in html_content:
                    print(f"⚠️  非法访问，跳过")
                    continue
                
                # 保存HTML
                safe_name = re.sub(r'[^\w\-_\. ]', '_', link['text'] or 'page')
                filename = f'{i:02d}_{safe_name}.html'
                self.save_html(filename, html_content)
                
                # 简单分析
                soup = BeautifulSoup(html_content, 'html.parser')
                text_content = soup.get_text(strip=True)[:200]
                print(f"📄 页面内容预览: {text_content}...")
                
                crawled += 1
                
            except Exception as e:
                print(f"❌ 爬取失败: {e}")
        
        print(f"\n✅ 成功爬取 {crawled} 个页面")
    
    def test_scraper_methods(self):
        """测试scraper的所有方法"""
        print("\n" + "="*80)
        print("🧪 步骤5: 测试scraper所有解析方法")
        print("="*80)
        
        methods = [
            ('get_profile', '个人信息'),
            ('get_grades', '成绩查询'),
            ('get_schedule', '学期课表'),
            ('get_my_training_plan', '我的培养方案'),
            ('get_academic_progress', '学业进度'),
        ]
        
        for method_name, desc in methods:
            print(f"\n{'─'*80}")
            print(f"🔍 测试: {desc} ({method_name})")
            print(f"{'─'*80}")
            
            try:
                method = getattr(self.scraper, method_name, None)
                if not method:
                    print(f"   ⚠️  方法不存在")
                    continue
                
                result = method()
                
                if isinstance(result, dict):
                    if result.get('success'):
                        data = result.get('data', {})
                        if isinstance(data, list):
                            print(f"   ✅ 成功获取 {len(data)} 条记录")
                            if data:
                                print(f"   📋 第一条数据: {json.dumps(data[0], ensure_ascii=False, indent=6)[:300]}")
                        elif isinstance(data, dict):
                            print(f"   ✅ 成功获取数据")
                            # 如果是培养方案，显示课程数量
                            if '课程列表' in data:
                                print(f"   📚 课程数量: {len(data['课程列表'])}")
                                if data['课程列表']:
                                    print(f"   📋 第一门课程: {json.dumps(data['课程列表'][0], ensure_ascii=False, indent=6)[:300]}")
                            else:
                                print(f"   📋 数据: {json.dumps(data, ensure_ascii=False, indent=6)[:300]}")
                    else:
                        print(f"   ❌ 失败: {result.get('message')}")
                else:
                    print(f"   ✅ 返回结果: {result}")
                    
            except Exception as e:
                print(f"   ❌ 异常: {e}")
                import traceback
                traceback.print_exc()
    
    def run(self, username, password, captcha):
        """运行完整测试流程"""
        print("="*80)
        print("🚀 智能爬虫自动测试开始")
        print("="*80)
        print(f"👤 学号: {username}")
        print(f"📁 HTML保存目录: {self.html_dir}")
        
        # 1. 登录
        if not self.login(username, password, captcha):
            print("\n❌ 登录失败，终止测试")
            return
        
        # 2. 爬取主页面
        main_analysis = self.crawl_main_page()
        
        # 3. 爬取所有菜单项
        self.crawl_all_menu_items(main_analysis)
        
        # 4. 测试scraper方法
        self.test_scraper_methods()
        
        # 5. 总结
        print("\n" + "="*80)
        print("✅ 测试完成！")
        print("="*80)
        print(f"\n📁 所有HTML文件保存在: {self.html_dir}")
        print(f"📊 请查看HTML文件分析爬虫逻辑")
        print(f"\n💡 下一步:")
        print(f"   1. 查看 crawled_html/ 目录中的HTML文件")
        print(f"   2. 对比 scraper.py 中的解析逻辑")
        print(f"   3. 修复不匹配的解析代码")


def main():
    """主函数 - 全自动运行"""
    print("="*80)
    print("🤖 智能爬虫自动测试系统 - 全自动模式")
    print("="*80)
    print()
    print("🚀 开始全自动爬取和分析...")
    print()
    
    # 固定测试账号
    username = "24251102121"
    password = "zj2831623154"
    
    # 创建测试器
    tester = SmartCrawlerTester()
    
    # 自动下载验证码
    captcha_path = tester.download_captcha()
    
    if not captcha_path:
        print("\n❌ 验证码下载失败")
        return
    
    # 自动打开验证码图片
    if sys.platform == 'win32':
        try:
            os.startfile(captcha_path)
            print("🖼️  验证码图片已打开")
        except:
            pass
    
    # 等待用户输入验证码（这是唯一需要人工的步驟）
    print("\n👉 请查看打开的验证码图片，然后输入验证码:")
    captcha = input("验证码: ").strip()
    
    # 运行全自动测试
    tester.run(username, password, captcha)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
