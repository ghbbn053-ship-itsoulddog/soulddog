#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
教务系统爬虫实时测试脚本
功能：实际登录教务系统，逐层爬取并验证解析逻辑
"""

import sys
import os
from bs4 import BeautifulSoup
import re

# 添加backend目录到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from scraper import JwxtScraper
import requests

def test_login_and_scrape():
    """测试登录和爬取全流程"""
    
    print("=" * 80)
    print("教务系统爬虫实时测试")
    print("=" * 80)
    
    # 1. 获取用户输入
    print("\n📝 请输入登录信息：")
    username = input("学号: ").strip()
    password = input("密码: ").strip()
    
    # 2. 创建session
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # 3. 下载验证码
    print("\n📥 正在下载验证码...")
    scraper = JwxtScraper(session, "http://172.19.13.62:80/jsxsd/")
    
    # 使用scraper的get_captcha方法获取验证码
    try:
        captcha_bytes = scraper.get_captcha()
        print(f"✅ 验证码获取成功，大小: {len(captcha_bytes)} bytes")
    except Exception as e:
        print(f"❌ 验证码获取失败: {e}")
        return
    
    # 保存验证码图片
    captcha_path = os.path.join(os.path.dirname(__file__), 'test_captcha.jpg')
    with open(captcha_path, 'wb') as f:
        f.write(captcha_bytes)
    
    print(f"\n✅ 验证码已保存到: {captcha_path}")
    print(f"📏 文件大小: {len(captcha_bytes)} bytes")
    
    # 尝试多种方式打开图片
    opened = False
    try:
        # 方法1: 使用默认图片查看器
        if sys.platform == 'win32':
            os.startfile(captcha_path)
            opened = True
            print("🖼️  已尝试打开图片查看器")
    except Exception as e:
        print(f"⚠️  自动打开失败: {e}")
    
    if not opened:
        print("\n👉 请手动打开图片查看验证码:")
        print(f"   方式1: 在文件管理器中双击 {captcha_path}")
        print(f"   方式2: 在浏览器中打开 file:///{captcha_path.replace(chr(92), '/')}")
        print(f"   方式3: 使用图片查看器打开")
    
    print()
    
    captcha = input("请输入验证码: ").strip()
    
    # 4. 登录
    print("\n🔐 正在登录...")
    login_result = scraper.login(username, password, captcha)
    
    if not login_result.get('success'):
        print(f"❌ 登录失败: {login_result.get('message')}")
        return
    
    print("✅ 登录成功！")
    print(f"📋 登录结果: {login_result}")
    
    # 5. 获取个人信息
    print("\n" + "=" * 80)
    print("测试1: 个人信息")
    print("=" * 80)
    
    try:
        profile = scraper.get_profile()
        print(f"✅ 个人信息获取成功")
        print(f"   姓名: {profile.get('name', 'N/A')}")
        print(f"   学号: {profile.get('student_id', 'N/A')}")
        print(f"   专业: {profile.get('major', 'N/A')}")
        print(f"   班级: {profile.get('class', 'N/A')}")
    except Exception as e:
        print(f"❌ 个人信息获取失败: {e}")
    
    # 6. 获取成绩
    print("\n" + "=" * 80)
    print("测试2: 成绩查询")
    print("=" * 80)
    
    try:
        grades = scraper.get_grades()
        grade_list = grades.get('data', [])
        print(f"✅ 成绩获取成功")
        print(f"   共 {len(grade_list)} 条成绩记录")
        
        if grade_list:
            print(f"\n   前3条成绩:")
            for i, grade in enumerate(grade_list[:3], 1):
                print(f"   {i}. {grade.get('课程名称', 'N/A')} - {grade.get('成绩', 'N/A')}分")
    except Exception as e:
        print(f"❌ 成绩获取失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 7. 获取课表
    print("\n" + "=" * 80)
    print("测试3: 学期课表")
    print("=" * 80)
    
    try:
        schedule = scraper.get_schedule()
        courses = schedule.get('data', [])
        print(f"✅ 课表获取成功")
        print(f"   共 {len(courses)} 门课程")
        
        if courses:
            print(f"\n   前3门课程:")
            for i, course in enumerate(courses[:3], 1):
                print(f"   {i}. {course.get('课程名称', 'N/A')}")
                print(f"      教师: {course.get('教师', 'N/A')}")
                print(f"      时间: {course.get('星期', 'N/A')} {course.get('节次', 'N/A')}")
                print(f"      地点: {course.get('地点', 'N/A')}")
    except Exception as e:
        print(f"❌ 课表获取失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 8. 获取培养方案（重点测试）
    print("\n" + "=" * 80)
    print("测试4: 我的培养方案（重点）")
    print("=" * 80)
    
    try:
        plan = scraper.get_my_training_plan()
        courses = plan.get('data', {}).get('课程列表', [])
        print(f"✅ 培养方案获取成功")
        print(f"   共 {len(courses)} 门课程")
        
        if courses:
            print(f"\n   前5门课程:")
            for i, course in enumerate(courses[:5], 1):
                print(f"   {i}. [{course.get('课程代码', 'N/A')}] {course.get('课程名称', 'N/A')}")
                print(f"      类别: {course.get('课程类别', 'N/A')}")
                print(f"      性质: {course.get('课程性质', 'N/A')}")
                print(f"      学分: {course.get('学分', 'N/A')}")
            
            # 统计课程类别
            categories = {}
            for course in courses:
                cat = course.get('课程类别', '未知')
                categories[cat] = categories.get(cat, 0) + 1
            
            print(f"\n   课程类别统计:")
            for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                print(f"   - {cat}: {count}门")
        
        # 保存HTML供分析
        html_path = os.path.join(os.path.dirname(__file__), 'training_plan_real.html')
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(plan.get('raw_html', ''))
        print(f"\n💾 培养方案HTML已保存到: {html_path}")
        
    except Exception as e:
        print(f"❌ 培养方案获取失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 9. 获取学业进度
    print("\n" + "=" * 80)
    print("测试5: 学业进度")
    print("=" * 80)
    
    try:
        progress = scraper.get_academic_progress()
        print(f"✅ 学业进度获取成功")
        print(f"   共 {len(progress)} 门课程")
        
        if progress:
            print(f"\n   前3门课程:")
            for i, item in enumerate(progress[:3], 1):
                print(f"   {i}. {item.get('课程名称', 'N/A')} - {item.get('获得学分', 'N/A')}学分")
    except Exception as e:
        print(f"❌ 学业进度获取失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 10. 保存所有原始HTML供分析
    print("\n" + "=" * 80)
    print("原始HTML保存")
    print("=" * 80)
    
    # 保存课表HTML
    try:
        schedule = scraper.get_schedule()
        schedule_html = schedule.get('raw_html', '')
        if schedule_html:
            schedule_html_path = os.path.join(os.path.dirname(__file__), 'schedule_real.html')
            with open(schedule_html_path, 'w', encoding='utf-8') as f:
                f.write(schedule_html)
            print(f"✅ 课表HTML已保存到: {schedule_html_path}")
    except Exception as e:
        print(f"⚠️ 课表HTML保存失败: {e}")
    
    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)
    print("\n📁 生成的文件:")
    print("   - test_captcha.jpg: 验证码图片")
    print("   - training_plan_real.html: 培养方案原始HTML")
    print("   - schedule_real.html: 课表原始HTML（如果有）")
    print("\n🔍 你可以用这些真实HTML来验证和优化爬虫解析逻辑")

if __name__ == '__main__':
    try:
        test_login_and_scrape()
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断测试")
    except Exception as e:
        print(f"\n❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
