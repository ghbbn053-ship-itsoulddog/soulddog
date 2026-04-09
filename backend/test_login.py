from scraper import JwxtScraper

print('=== 教务系统登录测试 ===')
scraper = JwxtScraper()

print('1. 获取验证码...')
captcha = scraper.get_captcha()
print(f'   验证码大小: {len(captcha)} bytes')

with open('captcha.jpg', 'wb') as f:
    f.write(captcha)
print('   验证码已保存到 captcha.jpg')

print('\n2. 请输入登录信息:')
username = input('   学号: ')
password = input('   密码: ')
code = input('   验证码: ')

print('\n3. 正在登录...')
result = scraper.login(username, password, captcha=code)
print(f'   结果: {result}')

if result['success']:
    print('\n4. 获取个人信息...')
    info = scraper.get_personal_info()
    print(f'   {info}')

    print('\n5. 选择查询方式:')
    print('   1. 查询所有主修成绩')
    print('   2. 查询辅修成绩')
    print('   3. 按学期查询')
    print('   4. 查询最好成绩')
    choice = input('   请选择(1-4，默认1): ').strip() or '1'

    if choice == '1':
        grades = scraper.get_all_grades()
    elif choice == '2':
        grades = scraper.get_grades(fxkc='1')
    elif choice == '3':
        semester = input('   输入学期(如2024-2025-2): ')
        grades = scraper.get_grades(kksj=semester)
    elif choice == '4':
        grades = scraper.get_grades(xsfs='max')
    else:
        grades = scraper.get_all_grades()

    print(f'\n   成绩数量: {grades.get("count", 0)}')

    if grades.get('success') and grades.get('data'):
        print('\n   成绩统计:')
        stats = grades.get('stats', {})
        print(f"      需修读: {stats.get('total_credits_required', 0)} 学分")
        print(f"      已修读: {stats.get('credits_completed', 0)} 学分")
        print(f"      还需修读: {stats.get('credits_remaining', 0)} 学分")
        print(f"      平均绩点: {stats.get('gpa_major', 0)}")
        print(f"      专业排名: {stats.get('rank', 'N/A')}")

        print('\n   最近5门课程:')
        for i, grade in enumerate(grades['data'][:5], 1):
            print(f"      {i}. {grade.get('课程名称', 'N/A')} - {grade.get('成绩', 'N/A')} ({grade.get('开课学期', 'N/A')})")

    # 测试其他功能
    print('\n6. 测试其他功能:')
    print('   a. 获取课表')
    print('   b. 获取我的培养方案（详细）')
    print('   c. 获取学业进度（主修/辅修）')
    print('   d. 获取考试安排')
    print('   e. 获取执行计划')
    print('   f. 跳过')

    test_choice = input('   请选择(a-f，默认f): ').strip() or 'f'

    if test_choice == 'a':
        semester = input('   输入学期(如2024-2025-2，直接回车获取当前): ')
        week = input('   输入周次(1-30，直接回车获取全部): ')
        print(f'\n   正在获取课表...')
        schedule = scraper.get_schedule(semester=semester, week=week)
        print(f"\n   课表课程数: {schedule.get('count', 0)}")
        if schedule.get('data'):
            print('   示例课程:')
            for i, course in enumerate(schedule['data'][:5], 1):
                print(f"      {i}. {course.get('课程名称', 'N/A')}")
                print(f"         时间: {course.get('星期', 'N/A')} 第{course.get('节次', 'N/A')}节")
                print(f"         地点: {course.get('地点', 'N/A')}")
                print(f"         周次: {course.get('周次', 'N/A')}")
                if course.get('教师'):
                    print(f"         教师: {course.get('教师', 'N/A')}")
        if schedule.get('未安排时间课程'):
            print(f"\n   未安排时间课程: {', '.join(schedule['未安排时间课程'])}")

    elif test_choice == 'b':
        print('\n   正在获取我的培养方案...')
        plan = scraper.get_my_training_plan()
        print(f"\n   培养方案课程数: {plan.get('count', 0)}")
        if plan.get('data'):
            basic_info = plan['data'].get('基本信息', {})
            credit_stats = plan['data'].get('学分统计', {})
            print(f"   专业版本: {basic_info.get('专业版本', 'N/A')}")
            print(f"   学院: {basic_info.get('学院', 'N/A')}")
            print(f"   总学分要求: {credit_stats.get('总学分要求', 0)}")
            print(f"   计划学分: {credit_stats.get('计划学分', 0)}")
            if plan['data'].get('课程列表'):
                print('   示例课程:')
                for i, course in enumerate(plan['data']['课程列表'][:3], 1):
                    print(f"      {i}. {course.get('课程名称', 'N/A')} ({course.get('课程代码', 'N/A')}) - {course.get('学分', 'N/A')}学分")

    elif test_choice == 'c':
        print('\n   选择修读类型:')
        print('   0. 主修')
        print('   1. 辅修')
        study_type = input('   请选择(0-1，默认0): ').strip() or '0'

        print(f'\n   正在获取{"辅修" if study_type == "1" else "主修"}学业进度...')
        progress = scraper.get_academic_progress(study_type=study_type)
        if progress.get('success'):
            data = progress.get('data', {})
            print(f"\n   修读类型: {data.get('修读类型', 'N/A')}")
            print(f"   总学分要求: {data.get('总学分要求', 0)}")
            print(f"   已获学分: {data.get('已获学分', 0)}")
            print(f"   还需学分: {data.get('还需学分', 0)}")
            print(f"   课程数量: {progress.get('count', 0)}")
            if data.get('课程列表'):
                print('   示例课程:')
                for i, course in enumerate(data['课程列表'][:3], 1):
                    status = "✓" if course.get('已获学分') else "✗"
                    print(f"      {status} {i}. {course.get('课程名称', 'N/A')} - 已获{course.get('已获学分', '0')}学分")

    elif test_choice == 'd':
        semester = input('   输入学期(如2024-2025-1): ')
        exams = scraper.get_exam_schedule(semester=semester)
        print(f"\n   考试安排数: {exams.get('count', 0)}")
        if exams.get('data'):
            print('   考试列表:')
            for i, exam in enumerate(exams['data'][:3], 1):
                print(f"      {i}. {exam.get('课程名称', 'N/A')} - {exam.get('考试时间', 'N/A')}")

    elif test_choice == 'e':
        print('\n   正在获取执行计划...')
        plan = scraper.get_execution_plan()
        print(f"\n   执行计划课程数: {plan.get('count', 0)}")
        if plan.get('data'):
            plan_info = plan['data'].get('计划信息', {})
            print(f"   计划信息: {plan_info}")