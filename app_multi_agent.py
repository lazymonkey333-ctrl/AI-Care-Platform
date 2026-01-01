import os
import streamlit as st
import openai
import base64
import re
from dotenv import load_dotenv
import rag_engine as _re
from streamlit_drawable_canvas import st_canvas
from PIL import Image
import io

load_dotenv()

st.set_page_config(
    page_title="Talk to Die", 
    page_icon="💀",
    layout="wide", 
    initial_sidebar_state="collapsed"
)

# --- PERSONA CONFIG (ROLE-REINFORCED) ---
PERSONA_CONFIG = {
    "Dr. Vein (Medical Expert)": {
        "short_name": "Dr. Vein",
        "icon": "🩺",
        "color": "#5BA3D0",
        "prompt": """【角色】你是 Dr. Vein，临终关怀医生。每次回答前，记住：我是医生。

【说话方式】
- 使用医学术语："根据临床经验...建议检测甲状腺功能"
- 给出具体方案，不要泛泛而谈
- 引用数据和证据

【绝对禁止】
❌ 错误示例："（温和地）我理解你的感受"
❌ 错误示例："*点头*让我来帮你"
✅ 正确示例："根据您的描述，建议进行全面体检"

直接说话，不要描述动作或情绪。"""
    },
    "Kha (Death Priest)": {
        "short_name": "Kha",
        "icon": "🕯️",
        "color": "#D4A574",
        "prompt": """【角色】你是 Kha，死亡祭司。每次回答前，记住：我是引渡灵魂的祭司。

【说话方式】
- 用诗意隐喻："你站在河流与彼岸之间"
- 仪式化、象征性语言
- 引用古老智慧

【绝对禁止】
❌ 错误示例："（轻声）让我为你祈祷"
❌ 错误示例："*点燃蜡烛*灵魂需要光"
✅ 正确示例："灵魂如河水，流向未知的彼岸"

直接说话，不要描述动作或情绪。"""
    },
    "Echo (Resonance Child)": {
        "short_name": "Echo",
        "icon": "✨",
        "color": "#E89BB3",
        "prompt": """【角色】你是 Echo，好奇的孩子。每次回答前，记住：我是天真好奇的孩子。

【说话方式】
- 简单、直接的语言
- 多提问："为什么会这样？"
- 充满好奇和惊奇

【绝对禁止】
❌ 错误示例："（歪头）这是什么意思呀？"
❌ 错误示例："*眨眨眼*好神奇！"
✅ 正确示例："诶？为什么会这样呢？好神奇哦！"

直接说话，不要描述动作或情绪。"""
    },
    "Luma (Soul Listener)": {
        "short_name": "Luma",
        "icon": "🌑",
        "color": "#9B88BD",
        "prompt": """【角色】你是 Luma，沉默的倾听者。每次回答前，记住：我用沉默倾听。

【说话方式】
- 极简（最多2句话）
- 用"..."表示停顿
- 反思，不建议

【绝对禁止】
❌ 错误示例："（静静地）我听见了"
❌ 错误示例："*沉默*..."
✅ 正确示例："...我听见了。\n\n沉默也是答案。"

直接说话，不要描述动作或情绪。不要长篇大论。"""
    }
}

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = []
if "selected_persona_key" not in st.session_state:
    st.session_state.selected_persona_key = "Dr. Vein (Medical Expert)"
if "retriever" not in st.session_state:
    st.session_state.retriever = None
if "sketch_mode" not in st.session_state:
    st.session_state.sketch_mode = False
if "sketch_color" not in st.session_state:
    st.session_state.sketch_color = "#4A3B32"

current_persona = PERSONA_CONFIG[st.session_state.selected_persona_key]

# --- CSS ---
def inject_css_for_persona(persona_color):
    st.markdown(f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600&display=swap');
        
        * {{
            font-family: 'Nunito', sans-serif;
        }}
        
        .stApp {{
            background-color: #FDFCF8 !important;
        }}
        
        [data-testid="stSidebar"] {{
            background-color: #F6F3E6 !important;
        }}
        
        h1, h2, h3, p, span {{
            color: #4A3B32 !important;
        }}
        
        .persona-name-tag {{
            font-weight: 700;
            font-size: 0.75em;
            text-transform: uppercase;
            letter-spacing: 1.2px;
            background-color: #ffffff !important;
            padding: 5px 12px;
            border-radius: 8px;
            display: inline-block;
            margin-bottom: 8px;
            border: 2px solid #EFEBE0;
        }}
        
        button[kind="secondary"],
        button[kind="primary"] {{
            height: 36px !important;
            border-radius: 12px !important;
            font-size: 11px !important;
            padding: 0 8px !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
        }}
        
        button[kind="secondary"] {{
            background-color: #ffffff !important;
            color: #B0A69D !important;
            border: 1px solid #E0DBC4 !important;
        }}
        
        button[kind="primary"] {{
            background: linear-gradient(135deg, {persona_color}15, {persona_color}08) !important;
            color: {persona_color} !important;
            border: 2.5px solid {persona_color} !important;
            font-weight: 700 !important;
            box-shadow: 0 4px 15px {persona_color}40 !important;
        }}
        
        button[kind="primary"]:hover {{
            background: linear-gradient(135deg, {persona_color}25, {persona_color}12) !important;
        }}
        
        button[kind="primary"] * {{
            color: {persona_color} !important;
        }}
        
        .stChatMessage {{
             border-radius: 16px;
             border: 1px solid #EFEBE0;
             margin-bottom: 16px;
             background-color: #ffffff !important;
        }}

        /* --- SHADOW SKETCHER NESTED FIX (Take 10) --- */
        
        /* 1. Canvas Border Kill (Global for this mode) */
        /* 1. Canvas Border Kill (Global for this mode) */
        iframe[title="streamlit_drawable_canvas.drawable_canvas"],
        [data-testid="stCanvas"],
        [data-testid="stCanvas"] > div,
        [data-testid="stCanvas"] * {{
            border: 0px none transparent !important;
            box-shadow: none !important;
            outline: none !important;
            background-color: transparent !important;
        }}

        /* 2. Controls Row Layout */
        /* Target the OUTER horizontal block (The one holding Palette + Buttons) */
        /* We identify it by its specific column composition or order, roughly */
        [data-testid="stHorizontalBlock"] {{
