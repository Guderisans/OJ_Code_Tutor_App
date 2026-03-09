from flask import Flask, render_template, request, jsonify
import subprocess
import os
import sys
import webbrowser
import threading
import time

app = Flask(__name__)

# 配置：原脚本的路径
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "oj_download_submissions.py")
# URL模板
BASE_URL = "https://onlinejudge.hkust-gz.edu.cn/contest/{contest_id}"
SUBMISSIONS_ALL = "{base_url}/submissions"
SUBMISSIONS_PROBLEM = "{base_url}/submissions?problemID={problem_id}"

# 新增：全局标志位，确保只打开一次浏览器
browser_opened = False


# 自动打开浏览器函数（加锁，仅执行一次）
def open_browser():
    global browser_opened
    # 避免多进程/多线程重复执行
    if browser_opened:
        return
    # 延迟1秒，等Flask服务完全启动
    time.sleep(1)
    # 打开页面（new=1：只打开一个窗口/标签页，不重复创建）
    webbrowser.open("http://127.0.0.1:5000", new=1)
    # 标记为已打开
    browser_opened = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/run-script', methods=['POST'])
def run_script():
    try:
        # 1. 获取表单数据
        data = request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        contest_password = data.get('contest_password', '').strip()
        contest_id = data.get('contest_id', '').strip()
        problem_id = data.get('problem_id', '').strip()
        year = data.get('year', '').strip()
        output = data.get('output', 'submissions.csv').strip()
        headless = data.get('headless', 'false') == 'true'

        # 2. 校验必填参数
        required_errors = []
        if not username:
            required_errors.append("OJ用户名不能为空")
        if not password:
            required_errors.append("OJ密码不能为空")
        if not contest_password:
            required_errors.append("竞赛密码不能为空")
        if not contest_id:
            required_errors.append("竞赛ID不能为空")
        else:
            if not contest_id.isdigit():
                required_errors.append("竞赛ID必须是数字（如65）")

        if required_errors:
            return jsonify({
                'status': 'error',
                'message': '参数校验失败：' + ' | '.join(required_errors)
            })

        # 3. 拼接URL
        base_url = BASE_URL.format(contest_id=contest_id)
        if problem_id.strip():
            if not problem_id.isdigit():
                return jsonify({
                    'status': 'error',
                    'message': '题目ID必须是数字（如1003）'
                })
            submissions_url = SUBMISSIONS_PROBLEM.format(base_url=base_url, problem_id=problem_id)
        else:
            submissions_url = SUBMISSIONS_ALL.format(base_url=base_url)
        contest_url = base_url

        # 4. 构造执行命令
        cmd = [
            sys.executable,
            SCRIPT_PATH,
            '--username', username,
            '--password', password,
            '--contest-password', contest_password,
            '--contest-url', contest_url,
            '--submissions-url', submissions_url,
            '--output', output
        ]
        if year:
            cmd.extend(['--year', year])
        if headless:
            cmd.append('--headless')

        # 5. 执行脚本
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=300
        )

        # 6. 返回结果
        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': f'脚本运行成功！已保存 {output} 文件\n拼接的URL：\n竞赛主URL：{contest_url}\n提交页URL：{submissions_url}',
                'output': result.stdout
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f'脚本运行失败！\n拼接的URL（请核对）：\n竞赛主URL：{contest_url}\n提交页URL：{submissions_url}',
                'error': result.stderr,
                'stdout': result.stdout
            })

    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': '脚本运行超时（超过5分钟）！'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'服务器内部错误：{str(e)}'
        })


if __name__ == '__main__':
    # 1. 启动线程打开浏览器（仅一次）
    threading.Thread(target=open_browser, daemon=True).start()
    # 2. 关闭debug模式（核心：避免多进程导致重复打开）
    # host=0.0.0.0：允许局域网访问，若仅本地用可改为127.0.0.1
    app.run(debug=False, host='127.0.0.1', port=5000)