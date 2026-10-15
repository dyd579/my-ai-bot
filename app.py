import streamlit as st
import requests
import json
import os

# ==========================================
# ⚠️ 第一步：引出真实配置
# ==========================================
API_TOKEN = os.environ.get("API_TOKEN", "本地开发默认值")
BOT_ID = os.environ.get("BOT_ID", "本地开发默认值")

# ==========================================
# ⚠️ 第二步：网页界面初始化
# ==========================================
st.set_page_config(page_title="我的专属助手", page_icon="🤖")
st.title("🤖 我的专属助手")
st.caption("基于 Coze API 的企业级知识库问答 (流式输出优化版)")

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# ⚠️ 第三步：接收输入并请求 API
# ==========================================
if prompt := st.chat_input("请输入你想问的问题："):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    url = "https://api.coze.cn/open_api/v2/chat"
    headers = {
        "Authorization": f"Bearer {API_TOKEN}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "Host": "api.coze.cn",
        "Connection": "keep-alive"
    }
    payload = {
        "bot_id": BOT_ID,
        "user": "streamlit_user",
        "query": prompt,
        "stream": True
    }

    with st.chat_message("assistant"):
        with st.spinner("思考中..."):
            try:
                response = requests.post(url, headers=headers, json=payload, stream=True)

                if response.status_code == 200:
                    full_response = ""
                    message_placeholder = st.empty()
                    # 🌟 核心：字节缓冲区，专门解决中文乱码0xe4和分包截断问题
                    buffer = b""

                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            buffer += chunk
                            while b"\n" in buffer:
                                line, buffer = buffer.split(b"\n", 1)
                                line = line.strip()

                                if line.startswith(b"data:"):
                                    data_bytes = line[5:].strip()
                                    if data_bytes and data_bytes != b"[DONE]":
                                        try:
                                            # 1. 解码并转换 JSON
                                            data_str = data_bytes.decode('utf-8')
                                            data_json = json.loads(data_str)

                                            # 2. 适配 Coze 最新流式返回格式 (event + 单数 message)
                                            event_type = data_json.get("event")

                                            if event_type == "message":
                                                message_data = data_json.get("message", {})
                                                msg_type = message_data.get("type")
                                                msg_content = message_data.get("content", "")

                                                # 3. 核心：仅提取 answer 类型的内容
                                                if msg_type == "answer" and msg_content:
                                                    full_response += msg_content
                                                    message_placeholder.markdown(full_response + "▌")

                                            elif event_type == "done":
                                                # 收到 done 事件，流正式结束
                                                break

                                        except json.JSONDecodeError as e:
                                            print(f"【解析警告】JSON解析失败: {e}")
                                            continue
                                        except Exception as e:
                                            print(f"【处理警告】逻辑异常: {e}")
                                            continue

                    # 最终渲染（去掉打字机光标）
                    if full_response:
                        message_placeholder.markdown(full_response)
                        st.session_state.messages.append({"role": "assistant", "content": full_response})
                    else:
                        message_placeholder.warning("⚠️ 未提取到任何回答内容，请查看PyCharm终端日志。")
                        print("\n【最终警告】流已结束，但没有提取到 answer 类型的回复。")

                else:
                    st.error(f"请求失败，状态码：{response.status_code}")
                    st.write(response.text)
            except Exception as e:
                st.error(f"发生严重错误：{e}")
                print(f"【严重错误】: {e}")