# from openai import OpenAI
# key='sk-an10Ha4ZnY80qWBohKJZaRJciFlxosuH0Q7ap7ovnaW60PLm'
#
#
#
# client = OpenAI(
#     base_url="https://api2.aigcbest.top/v1",
#     api_key=key
# )
#
# response = client.chat.completions.create(
#   model="gpt-4o",
#   messages=[
#     {"role": "user", "content": "你好?"},
#
#   ]
# )
# print(response)

from openai import OpenAI

# 设置 API 密钥
key = 'sk-an10Ha4ZnY80qWBohKJZaRJciFlxosuH0Q7ap7ovnaW60PLm'

client = OpenAI(
    base_url="https://api2.aigcbest.top/v1",
    api_key=key
)


def chat_with_ai():
    print("与 AI 对话，输入 'exit' 结束对话。")
    messages = [{"role": "user", "content": "你好?"}]  # 初始化对话

    while True:
        user_input = input("你：")
        if user_input.lower() == 'exit':
            print("结束对话。")
            break

        # 将用户输入添加到消息列表
        messages.append({"role": "user", "content": user_input})

        # 调用 API 获取 AI 响应
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages
        )

        # 获取 AI 的响应并打印
        ai_response = response.choices[0].message.content  # 修改这一行
        print(f"AI：{ai_response}")

        # 将 AI 的响应添加到消息列表，以便进行后续对话
        messages.append({"role": "assistant", "content": ai_response})


if __name__ == "__main__":
    chat_with_ai()