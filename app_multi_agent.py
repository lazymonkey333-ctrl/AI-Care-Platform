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

        .sketch-area div[data-testid="stHorizontalBlock"] {{
            align-items: flex-end !important;
        }}

        .sketch-controls {{
            display: flex !important;
            flex-direction: column !important;
            gap: 10px !important;
            margin-bottom: 2px !important;
        }}

        /* Palette Button Styling */
        .color-block {{
            width: 100%;
            height: 34px;
            border-radius: 8px;
            border: 1px solid rgba(0,0,0,0.1); /* Subtle border */
            box-shadow: inset 0 1px 4px rgba(0,0,0,0.1);
            margin-top: -38px;
            pointer-events: none;
        }}

        .sketch-controls [data-testid="baseButton-secondary"],
        .sketch-controls [data-testid="baseButton-primary"] {{
            height: 32px !important;
            min-height: 32px !important;
            font-size: 11px !important;
            border-radius: 8px !important;
            margin: 0 !important;
        }}

        div.sketch-controls .stCaption p {{
            margin: 0 !important;
            padding: 0 !important;
            font-size: 11px !important;
            color: #A0968E !important;
        }}
        </style>
    """, unsafe_allow_html=True)

inject_css_for_persona(current_persona["color"])

# --- Avatar Generator ---
def generate_avatar_data_uri(content, bg_color, is_user=False):
    if is_user:
        inner_svg = f'<circle cx="32" cy="22" r="10" fill="#FFFDF5" /><path d="M12 56 C12 40 52 40 52 56 L52 64 L12 64 Z" fill="#FFFDF5" />'
    else:
        inner_svg = f'<text x="32" y="44" font-size="34" text-anchor="middle" font-family="Arial" fill="white">{content}</text>'
        
    svg_code = f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64"><circle cx="32" cy="32" r="30" fill="{bg_color}" />{inner_svg}</svg>'
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_code.encode()).decode()}"

for key in PERSONA_CONFIG:
    PERSONA_CONFIG[key]["avatar_uri"] = generate_avatar_data_uri(PERSONA_CONFIG[key]["icon"], PERSONA_CONFIG[key]["color"])

# --- Sidebar ---
with st.sidebar:
    st.header("🧠 Guardians")
    st.caption("Choose your guide:")
    
    for p_key in PERSONA_CONFIG.keys():
        is_active = (st.session_state.selected_persona_key == p_key)
        
        if st.button(
            f"{PERSONA_CONFIG[p_key]['icon']}   {p_key}", 
            key=f"btn_{p_key.replace(' ', '_')}", 
            type="primary" if is_active else "secondary",
            use_container_width=True
        ):
            st.session_state.selected_persona_key = p_key
            st.rerun()

    st.markdown("---")
    
    # Mode Toggle
    st.subheader("🎨 Modes")
    st.session_state.sketch_mode = st.toggle("Shadow Sketcher", value=st.session_state.sketch_mode, help="Communicate via drawings")
    
    dev_mode = st.checkbox("Dev Mode (Mock Embeddings)", value=True, key="dev_mode")
    os.environ["RAG_USE_RANDOM_EMBEDDINGS"] = "1" if dev_mode else "0"
    
    if st.button("🗑️ Reset", key="reset_btn"):
        st.session_state.clear()
        st.rerun()

st.title("💀 Talk to Die")
st.caption("The ByeBye Machine. • Conversations across the boundary.")

if st.session_state.retriever is None and not st.session_state.get("dev_mode", True):
    try:
        pdfs = _re.get_backend_pdfs()
        if pdfs:
            st.session_state.retriever = _re.get_retriever(pdfs)
    except Exception as e:
        st.error(f"RAG Init Error: {e}")

# --- Sketch Mode UI ---
if st.session_state.sketch_mode:
    # Wrap columns in a custom div to force flex-end alignment
    st.markdown('<div class="sketch-area">', unsafe_allow_html=True)
    col1, col2 = st.columns([5, 1], gap="small")
    
    with col1:
        canvas_result = st_canvas(
            fill_color="rgba(255, 165, 0, 0.3)",
            stroke_width=3,
            stroke_color=st.session_state.sketch_color,
            background_color="#ffffff",
            update_streamlit=True,
            height=300,
            width=700,
            drawing_mode="freedraw",
            display_toolbar=False,
            key=f"shadow_sketcher_{st.session_state.get('shadow_sketcher_version', 0)}",
        )
    
    with col2:
        st.markdown('<div class="sketch-controls">', unsafe_allow_html=True)
        
        st.caption("🎨 Palette")
        palette = ["#1E1E1E", "#4A3B32", "#7FB5D1", "#D4AC6E", "#E5A0B0", "#A294C2", "#8E9775", "#FF4B4B"]
        
        # Fully filled color buttons
        p_cols = st.columns(4)
        for idx, color in enumerate(palette):
            with p_cols[idx % 4]:
                if st.button(" ", key=f"c_{idx}"):
                    st.session_state.sketch_color = color
                    st.rerun()
                # Solid color block that perfectly fits the button ellipse
                st.markdown(f'<div class="color-block" style="background-color:{color};"></div>', unsafe_allow_html=True)

        if st.button("🗑️ Clear", use_container_width=True, key="clear_btn"):
            st.session_state["shadow_sketcher_version"] = st.session_state.get("shadow_sketcher_version", 0) + 1
            st.rerun()

        if st.button("✨ Send", use_container_width=True, key="send_btn"):
            if canvas_result.image_data is not None:
                img_data = canvas_result.image_data
                img = Image.fromarray(img_data.astype('uint8'), 'RGBA')
                buffered = io.BytesIO()
                img.save(buffered, format="PNG")
                img_base64 = base64.b64encode(buffered.getvalue()).decode()
                
                user_avatar = generate_avatar_data_uri(None, "#FF4B4B", is_user=True)
                st.session_state.messages.append({
                    "role": "user", 
                    "content": "I shared a sketch with you.", 
                    "avatar_uri": user_avatar,
                    "image": f"data:image/png;base64,{img_base64}"
                })
                st.toast("Sketch sent to the guardians...", icon="✨")
        
        st.markdown('</div>', unsafe_allow_html=True) # Close sketch-controls div
    st.markdown('</div>', unsafe_allow_html=True) # Close sketch-area wrapper

# Render History
for msg in st.session_state.messages:
    m_role = msg["role"]
    p_name = msg.get("persona_name")
    p_config = None
    for cfg in PERSONA_CONFIG.values():
        if cfg["short_name"] == p_name:
            p_config = cfg
            break

    with st.chat_message(m_role, avatar=msg.get("avatar_uri")):
        if m_role == "assistant" and p_config:
            st.markdown(f"<div class='persona-name-tag' style='color:{p_config['color']}'>{p_name}</div>", unsafe_allow_html=True)
        
        if "image" in msg:
            st.image(msg["image"], width=300, caption="User's Sketch")
            
        st.markdown(msg["content"])

# User Input
if prompt := st.chat_input("Speak to the shadow..."):
    user_avatar = generate_avatar_data_uri(None, "#FF4B4B", is_user=True)
    st.session_state.messages.append({"role": "user", "content": prompt, "avatar_uri": user_avatar})
    # No rerun needed, will flow to response logic below

# Handle Assistant Response if last message is from user
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_msg = st.session_state.messages[-1]
    
    with st.chat_message("assistant", avatar=current_persona["avatar_uri"]):
        st.markdown(f"<div class='persona-name-tag' style='color:{current_persona['color']}'>{current_persona['short_name']}</div>", unsafe_allow_html=True)
        
        with st.spinner(f"{current_persona['short_name']} is here..."):
            context = ""
            if st.session_state.retriever:
                try:
                    docs = st.session_state.retriever.get_relevant_documents(last_msg["content"])
                    context = "\n".join([d.page_content for d in docs[:3]])
                except Exception:
                    pass
            
            system_prompt = current_persona['prompt']
            if context:
                system_prompt += f"\n\n### 参考文档：\n{context}"
            
            # Build message history with role reinforcement
            conversation_messages = []
            for m in st.session_state.messages[-10:]:
                if m["role"] == "user":
                    role_reminder = f"[提醒：你是 {current_persona['short_name']}，用你的独特风格回答]\n\n"
                    # If there's an image, we should theoretically use a vision model
                    # For now, we'll keep it text and mention the image if present
                    msg_content = m["content"]
                    if "image" in m:
                        msg_content = "[用户绘制了一幅画] " + msg_content
                    
                    conversation_messages.append({
                        "role": "user",
                        "content": role_reminder + msg_content
                    })
                else:
                    conversation_messages.append(m)
            
            try:
                client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"), base_url="https://api.deepseek.com/v1")
                res = client.chat.completions.create(
                    model="deepseek-chat",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        *conversation_messages
                    ],
                    temperature=0.9,
                    max_tokens=500
                )
                ans = res.choices[0].message.content
                
                # POST-PROCESSING: Remove all parentheses, brackets, and asterisks
                ans = re.sub(r'[（(].*?[)）]', '', ans)
                ans = re.sub(r'\[.*?\]', '', ans)
                ans = re.sub(r'\*.*?\*', '', ans)
                ans = ans.strip()
                
                st.markdown(ans)
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": ans,
                    "avatar_uri": current_persona["avatar_uri"],
                    "persona_name": current_persona["short_name"]
                })
                st.rerun()
            except Exception as e:
                st.error(f"Error: {e}")
