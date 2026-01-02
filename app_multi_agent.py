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
if "vision_mode" not in st.session_state:
    st.session_state.vision_mode = False

current_persona = PERSONA_CONFIG[st.session_state.selected_persona_key]

# --- CSS ---
def inject_css_for_persona(persona_color):
    css = f"""
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

        /* --- SHADOW SKETCHER NESTED FIX (Take 11) --- */
        
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
        [data-testid="stHorizontalBlock"] {{
            align-items: flex-end !important;
            width: 1000px !important; /* Match Canvas Width (Resized) */
            max-width: 100% !important;
            margin: 0 auto !important;
        }}

        /* 3. PALETTE BUTTONS (The Nested Block) */
        /* Target buttons inside a Horizontal Block which is INSIDE another Horizontal Block */
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] button {{
            width: 26px !important;
            height: 26px !important;
            min-height: 26px !important;
            padding: 0 !important;
            border-radius: 6px !important;
            border: 1px solid rgba(0,0,0,0.1) !important;
            transition: transform 0.1s !important;
            color: transparent !important; /* Hide any text */
        }}
        
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] button:hover {{
            transform: scale(1.1) !important;
            border: 1px solid rgba(0,0,0,0.2) !important;
            z-index: 10 !important;
        }}

        /* Hide the <p> inside palette buttons */
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] button p {{
            display: none !important;
        }}

        /* PALETTE COLORS (Targeting the Columns of the Inner Block) */
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(1) button {{ background-color: #1E1E1E !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(2) button {{ background-color: #4A3B32 !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(3) button {{ background-color: #7FB5D1 !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(4) button {{ background-color: #D4AC6E !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(5) button {{ background-color: #E5A0B0 !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(6) button {{ background-color: #A294C2 !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(7) button {{ background-color: #8E9775 !important; }}
        [data-testid="stHorizontalBlock"] [data-testid="stHorizontalBlock"] > div:nth-child(8) button {{ background-color: #FF4B4B !important; }}

        /* 4. ACTION BUTTONS (Clear / Send) */
        button[kind="secondary"], button[kind="primary"] {{
             /* Base styles handled by earlier block */
        }}
        </style>
    """
    st.markdown(css, unsafe_allow_html=True)



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
    
    # Mode Toggles
    st.subheader("🎨 Modes")
    st.session_state.sketch_mode = st.toggle("🎨 Shadow Sketcher", value=st.session_state.sketch_mode, help="Communicate via drawings")
    st.session_state.vision_mode = st.toggle("👁️ Sight Mode", value=st.session_state.vision_mode, help="Upload photos for analysis")
    
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

# --- Sight Mode UI (Main Page) ---
if st.session_state.vision_mode:
    with st.container():
        st.info("👁️ Sight Mode Active: Upload a photo to discuss with your Guardian.")
        uploaded_photo = st.file_uploader("Choose a photo or take one", type=["png", "jpg", "jpeg"], key="main_photo_uploader")
        
        if uploaded_photo:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.image(uploaded_photo, caption="Selected Preview", width=300)
            with col2:
                st.markdown('<div style="height: 30px"></div>', unsafe_allow_html=True)
                if st.button("📤 Analyze Photo", use_container_width=True, type="primary"):
                    photo_data = base64.b64encode(uploaded_photo.read()).decode()
                    photo_uri = f"data:image/jpeg;base64,{photo_data}"
                    
                    user_avatar = generate_avatar_data_uri(None, "#FF4B4B", is_user=True)
                    st.session_state.messages.append({
                        "role": "user",
                        "content": "Please analyze this photo and tell me your thoughts.",
                        "avatar_uri": user_avatar,
                        "image": photo_uri
                    })
                    st.session_state.vision_mode = False # Auto-off after sending or keep on? Keep on but clear maybe. 
                    st.rerun()
    st.markdown("---")

# --- Sketch Mode UI ---
if st.session_state.sketch_mode:
    # 1. Canvas (Width 1000px - Fixed for Desktop Wide)
    canvas_result = st_canvas(
        fill_color="rgba(255, 165, 0, 0.3)",
        stroke_width=3,
        stroke_color=st.session_state.sketch_color,
        background_color="#ffffff",
        update_streamlit=True,
        height=350,  # Slightly taller
        width=1000,  # Resized to fill more space
        drawing_mode="freedraw",
        display_toolbar=False,
        key=f"shadow_sketcher_{st.session_state.get('shadow_sketcher_version', 0)}",
    )
    
    # 2. Controls Row
    # Column ratios: 6 for palette (needs space), 1 for spacer/clear, 1 for send
    control_cols = st.columns([6, 1, 1]) 
    
    with control_cols[0]: # Left: Palette
        st.caption("🎨 Color Palette")
        palette = ["#1E1E1E", "#4A3B32", "#7FB5D1", "#D4AC6E", "#E5A0B0", "#A294C2", "#8E9775", "#FF4B4B"]
        # Nested columns for the specific button grid
        p_cols = st.columns(8)
        for idx, color in enumerate(palette):
            with p_cols[idx]:
                if st.button(" ", key=f"c_{idx}"):
                    st.session_state.sketch_color = color
                    st.rerun()

    # Right: Buttons (Clear / Send)
    with control_cols[1]:
        st.markdown('<div style="height: 24px"></div>', unsafe_allow_html=True) # Spacer to align bottom
        if st.button("🗑️ Clear", use_container_width=True, key="clear_btn"):
            st.session_state["shadow_sketcher_version"] = st.session_state.get("shadow_sketcher_version", 0) + 1
            st.rerun()
        
    with control_cols[2]:
        st.markdown('<div style="height: 24px"></div>', unsafe_allow_html=True) # Spacer to align bottom
        if st.button("✨ Send", use_container_width=True, key="send_btn", type="primary"):
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
                st.toast("Sketch sent upwards...", icon="✨")
                st.session_state.sketch_mode = False
                st.rerun()

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
            
            # --- VISION & TEXT HYBRID LOGIC ---
            # Check if there are any images in the history being sent
            has_images = False
            final_messages = []
            
            # System Prompt
            final_messages.append({"role": "system", "content": system_prompt})
            
            # Message Processing
            for m in list(st.session_state.messages)[-10:]:
                if m["role"] == "user":
                    role_reminder = f"[提醒：你是 {current_persona['short_name']}，用你的独特风格回答]\n\n"
                    # Vision Payload Construction
                    if "image" in m:
                        has_images = True
                        # Clean up data URI
                        img_url = m["image"]
                        final_messages.append({
                            "role": "user",
                            "content": [
                                {"type": "text", "text": role_reminder + m["content"]},
                                {"type": "image_url", "image_url": {"url": img_url}}
                            ]
                        })
                    else:
                        final_messages.append({
                            "role": "user", 
                            "content": role_reminder + m["content"]
                        })
                else:
                    final_messages.append(m)

            try:
                # Dynamic Client Switch
                if has_images:
                    # Use Vision Provider (OpenRouter, SiliconFlow, etc.)
                    vision_key = os.getenv("VISION_API_KEY") or os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
                    vision_base = os.getenv("VISION_BASE_URL", "https://openrouter.ai/api/v1")
                    vision_model = os.getenv("VISION_MODEL", "google/gemini-2.0-flash-exp:free")
                    
                    client = openai.OpenAI(
                        api_key=vision_key, 
                        base_url=vision_base
                    )
                    model_id = vision_model
                    # Extra headers for OpenRouter
                    extra_headers = {
                        "HTTP-Referer": "https://streamlit.io",
                        "X-Title": "Shadow Sketcher"
                    }
                else:
                    # Use DeepSeek (Text Only)
                    client = openai.OpenAI(
                        api_key=os.gete
