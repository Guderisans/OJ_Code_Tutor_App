from flask import Flask, render_template, request, jsonify
import subprocess
import os
import sys

app = Flask(__name__)

# 配置：原脚本的路径（确保和app.py同目录）
SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "oj_download_submissions.py")
# 基础URL模板（核心修正：更新带problemID的提交页URL规则）
BASE_URL = "https://onlinejudge.hkust-gz.edu.cn/contest/{contest_id}"
SUBMISSIONS_ALL = "{base_url}/submissions"  # 无题目ID，获取整个竞赛提交
SUBMISSIONS_PROBLEM = "{base_url}/submissions?problemID={problem_id}"  # 有题目ID，带参数过滤


@app.route('/')
def index():
    # 渲染前端表单页面
    return render_template('index.html')


@app.route('/run-script', methods=['POST'])
def run_script():
    try:
        # 1. 获取前端提交的表单数据
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
            # 校验contest_id是否为数字
            if not contest_id.isdigit():
                required_errors.append("竞赛ID必须是数字（如65）")

        if required_errors:
            return jsonify({
                'status': 'error',
                'message': '参数校验失败：' + ' | '.join(required_errors)
            })

        # 3. 自动拼接URL（核心修正：按新规则拼接）
        base_url = BASE_URL.format(contest_id=contest_id)
        if problem_id.strip():
            # 校验problem_id是否为数字（如果填写了）
            if not problem_id.isdigit():
                return jsonify({
                    'status': 'error',
                    'message': '题目ID必须是数字（如1003）'
                })
            submissions_url = SUBMISSIONS_PROBLEM.format(base_url=base_url, problem_id=problem_id)
        else:
            submissions_url = SUBMISSIONS_ALL.format(base_url=base_url)
        contest_url = base_url  # 竞赛主URL保持不变

        # 4. 构造执行脚本的命令行参数
        cmd = [
            sys.executable,  # 当前Python解释器路径（避免环境问题）
            SCRIPT_PATH,
            '--username', username,
            '--password', password,
            '--contest-password', contest_password,
            '--contest-url', contest_url,
            '--submissions-url', submissions_url,
            '--output', output
        ]
        # 可选参数：年份、是否无头模式
        if year:
            cmd.extend(['--year', year])
        if headless:
            cmd.append('--headless')

        # 5. 执行脚本，捕获输出和错误
        result = subprocess.run(
            cmd,
            capture_output=True,  # 捕获stdout/stderr
            text=True,  # 输出为字符串（而非字节）
            encoding='utf-8',  # 编码
            timeout=300  # 超时时间（5分钟，避免脚本卡死）
        )

        # 6. 处理执行结果
        if result.returncode == 0:
            # 执行成功：展示拼接后的正确URL
            return jsonify({
                'status': 'success',
                'message': f'脚本运行成功！已保存 {output} 文件\n拼接的URL：\n竞赛主URL：{contest_url}\n提交页URL：{submissions_url}',
                'output': result.stdout
            })
        else:
            # 执行失败：展示拼接后的URL方便核对
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
    # 启动Web服务（本地访问：http://127.0.0.1:5000）
    app.run(debug=True, host='0.0.0.0', port=5000)