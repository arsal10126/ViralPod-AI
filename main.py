import streamlit as st
import os
import time
import json
import re
import requests
import gdown
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv
import yt_dlp
import gc  # Garbage Collection for server memory management

# --- CONFIGURATION & SETUP ---
st.set_page_config(
    page_title="ViralPod AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

load_dotenv()

# --- MODERN UI INJECTION ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    .main-header {
        background: linear-gradient(90deg, #4338ca 0%, #6366f1 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3rem;
        margin-bottom: 0.5rem;
    }
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 24px;
        margin-bottom: 20px;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .glass-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 30px -10px rgba(99, 102, 241, 0.3);
        border: 1px solid rgba(99, 102, 241, 0.5);
    }
    .stTextInput > div > div > input {
        background-color: #1e293b;
        color: white;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 10px 15px;
    }
    .stTextInput > div > div > input:focus {
        border-color: #6366f1;
        box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
    }
    .stButton > button {
        background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        width: 100%;
        transition: all 0.3s ease;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stButton > button:hover {
        opacity: 0.9;
        transform: scale(1.02);
        box-shadow: 0 4px 15px rgba(124, 58, 237, 0.4);
    }
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .result-title { font-size: 1.2rem; font-weight: 700; color: #fff; margin-bottom: 5px; }
    .result-time { color: #94a3b8; font-size: 0.9rem; font-family: monospace; font-weight: 600; }
    .result-score { display: inline-block; padding: 4px 12px; border-radius: 20px; font-weight: 800; font-size: 0.85rem; margin-top: 10px; }
    .score-high { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid #059669; }
    .score-med { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid #d97706; }
    .server-warning {
        background-color: rgba(234, 179, 8, 0.1);
        border: 1px solid rgba(234, 179, 8, 0.5);
        color: #fde047;
        padding: 10px;
        border-radius: 8px;
        font-size: 0.9rem;
        margin-bottom: 15px;
    }
</style>
""", unsafe_allow_html=True)

# --- LOGIC & HELPERS ---

def get_api_key():
    api_key = None
    try:
        if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
    except FileNotFoundError: pass
    if not api_key: api_key = os.getenv("GOOGLE_API_KEY")
    return api_key

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def process_dropbox_link(url):
    if "dropbox.com" in url and "dl=0" in url: return url.replace("dl=0", "dl=1")
    return url

def download_youtube_video(url, output_dir):
    sanitized_output = os.path.join(output_dir, '%(title)s.%(ext)s')
    ydl_opts = {
        'format': 'bestvideo[height<=360][ext=mp4]+bestaudio[ext=m4a]/best[height<=360][ext=mp4]', 
        'outtmpl': sanitized_output,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def download_file_from_url(url, output_path):
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path

def save_uploaded_file_chunked(uploaded_file, destination_path):
    """Writes large uploaded files to disk in chunks to save RAM."""
    try:
        with open(destination_path, "wb") as f:
            while True:
                chunk = uploaded_file.read(4 * 1024 * 1024) # 4MB chunks
                if not chunk: break
                f.write(chunk)
    finally:
        # CRITICAL FOR SERVER: Free up the RAM immediately
        uploaded_file = None
        gc.collect()
    return destination_path

def upload_to_gemini(file_path, mime_type=None):
    file = genai.upload_file(file_path, mime_type=mime_type)
    progress_bar = st.progress(0)
    status_text = st.empty()
    status_text.markdown("**Encrypting & Uploading Media to Neural Engine...**")
    
    while file.state.name == "PROCESSING":
        for i in range(100):
            time.sleep(0.05)
            progress_bar.progress(i + 1)
        file = genai.get_file(file.name)
        
    if file.state.name == "FAILED":
        raise ValueError("Neural Engine processing failed.")
        
    progress_bar.empty()
    status_text.empty()
    return file

def analyze_content(file_obj):
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    prompt = """
    Act as an elite Viral Content Strategist. Analyze this video for:
    1. High-Engagement Expressions (Shock, Laughter, Debate).
    2. Technical Integrity (No blur, clear audio).
    3. The "Hook" Factor.
    
    Return STRICT JSON:
    {
        "viral_shorts": [
            {"title": "Punchy Headline", "start": "MM:SS", "end": "MM:SS", "reasoning": "Brief strategy why", "viral_score": 95}
        ],
        "hook_intro": {
            "title": "The Hook", "start": "MM:SS", "end": "MM:SS", "reasoning": "Strategy", "viral_score": 90
        },
        "trailer_segment": {
            "title": "Trailer Cut", "start": "MM:SS", "end": "MM:SS", "reasoning": "Strategy", "viral_score": 92
        }
    }
    Provide exactly 3 shorts, 1 hook, 1 trailer.
    """
    response = model.generate_content(
        [file_obj, prompt],
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

def render_hero():
    st.markdown("""
        <div style="text-align: center; padding: 40px 0;">
            <h1 class="main-header">ViralPod AI</h1>
            <p style="font-size: 1.2rem; color: #94a3b8; max-width: 600px; margin: 0 auto;">
                Next-Gen Content Intelligence. Turn long-form video into viral assets.
            </p>
        </div>
    """, unsafe_allow_html=True)

def render_result_card(title, time_range, score, reasoning, type="Short"):
    score_color = "score-high" if score >= 90 else "score-med"
    return f"""
    <div class="glass-card">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <span style="background: #334155; color: #cbd5e1; padding: 2px 8px; border-radius: 4px; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 1px;">{type}</span>
            <span class="result-time">⏱ {time_range}</span>
        </div>
        <div style="margin-top: 15px;">
            <div class="result-title">{title}</div>
            <p style="color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin-top: 5px;">{reasoning}</p>
        </div>
        <div class="result-score {score_color}">
            ⚡ Viral Score: {score}/100
        </div>
    </div>
    """

# --- MAIN APP ---

def main():
    api_key = get_api_key()
    if api_key:
        genai.configure(api_key=api_key)
    else:
        st.warning("⚠️ API Key not detected.")
    
    render_hero()

    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown('<div style="background: #1e293b; padding: 20px; border-radius: 12px; border: 1px solid #334155;">', unsafe_allow_html=True)
        tab_url, tab_upload = st.tabs(["🔗 Link Input", "📂 File Upload"])
        
        media_source = None
        url_input = None
        uploaded_file = None

        with tab_url:
            st.markdown("<div style='font-size: 0.8rem; color: #94a3b8; margin-bottom: 10px;'>✅ <b>Recommended for Large Files (>1GB)</b> to avoid Server Timeouts.</div>", unsafe_allow_html=True)
            url_input = st.text_input("YouTube / Drive / Dropbox URL", placeholder="https://...")
            if url_input: media_source = "url"

        with tab_upload:
            st.markdown("<div style='font-size: 0.8rem; color: #94a3b8; margin-bottom: 10px;'>⚠️ Server Upload Limit: 5GB. For faster processing, use Link Input.</div>", unsafe_allow_html=True)
            # File uploader with no explicit argument limit (handled by config.toml)
            uploaded_file = st.file_uploader("Upload Video", type=["mp4", "mov", "mp3", "m4a"], label_visibility="collapsed")
            if uploaded_file: media_source = "upload"
        
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div style="height: 20px;"></div>', unsafe_allow_html=True)
        
        process_btn = st.button("🚀 IGNITE ENGINE", type="primary")

    if process_btn and (url_input or uploaded_file):
        if not api_key:
            st.error("Access Denied: API Key Missing")
            return

        try:
            temp_dir = Path("temp_media")
            temp_dir.mkdir(exist_ok=True)
            downloaded_file_path = None

            # --- PHASE 1: INGESTION ---
            with st.status("Initializing Neural Ingestion...", expanded=True) as status:
                st.write("Establishing secure connection...")
                
                if media_source == "upload":
                    downloaded_file_path = temp_dir / sanitize_filename(uploaded_file.name)
                    # Use memory-safe chunked saving
                    save_uploaded_file_chunked(uploaded_file, downloaded_file_path)
                    
                elif media_source == "url":
                    if "youtube" in url_input or "youtu.be" in url_input:
                        st.write("Extracting stream from YouTube...")
                        downloaded_file_path = download_youtube_video(url_input, str(temp_dir))
                    elif "drive.google.com" in url_input:
                        st.write("Authenticating Google Drive link...")
                        if "id=" in url_input: file_id = url_input.split("id=")[1].split("&")[0]
                        elif "/d/" in url_input: file_id = url_input.split("/d/")[1].split("/")[0]
                        else: file_id = None
                        
                        if file_id:
                            output_path = temp_dir / f"gdrive_{file_id}.mp4"
                            gdown.download(f'https://drive.google.com/uc?id={file_id}', str(output_path), quiet=False)
                            downloaded_file_path = str(output_path)
                    elif "dropbox" in url_input:
                        st.write("Bridging Dropbox stream...")
                        downloaded_file_path = download_file_from_url(process_dropbox_link(url_input), temp_dir / "dropbox.mp4")
                    else:
                        downloaded_file_path = download_file_from_url(url_input, temp_dir / "direct.mp4")
                
                status.update(label="Ingestion Complete", state="complete")

            if not downloaded_file_path:
                st.error("Ingestion Failed.")
                return

            # --- PHASE 2: PROCESSING ---
            gemini_file = upload_to_gemini(downloaded_file_path)

            # --- PHASE 3: ANALYSIS ---
            with st.spinner("🤖 Analyzing facial micro-expressions and audio sentiment..."):
                result_json = analyze_content(gemini_file)

            # --- PHASE 4: RENDER RESULTS ---
            st.markdown("<br><hr style='border-color: #334155'><br>", unsafe_allow_html=True)
            st.markdown("<h2 style='text-align: center; color: white;'>✨ Viral Candidates Identified</h2><br>", unsafe_allow_html=True)

            r_col1, r_col2 = st.columns(2)
            with r_col1:
                h = result_json.get('hook_intro', {})
                st.markdown(render_result_card(h.get('title'), f"{h.get('start')} - {h.get('end')}", h.get('viral_score'), h.get('reasoning'), "HOOK"), unsafe_allow_html=True)
            with r_col2:
                t = result_json.get('trailer_segment', {})
                st.markdown(render_result_card(t.get('title'), f"{t.get('start')} - {t.get('end')}", t.get('viral_score'), t.get('reasoning'), "TRAILER"), unsafe_allow_html=True)

            st.markdown("<h3 style='color: #94a3b8; margin-top: 30px;'>Top Viral Shorts</h3>", unsafe_allow_html=True)
            
            shorts = result_json.get("viral_shorts", [])
            s_col1, s_col2, s_col3 = st.columns(3)
            for i, clip in enumerate(shorts):
                html = render_result_card(clip.get('title'), f"{clip.get('start')} - {clip.get('end')}", clip.get('viral_score'), clip.get('reasoning'), f"SHORT #{i+1}")
                if i == 0: s_col1.markdown(html, unsafe_allow_html=True)
                elif i == 1: s_col2.markdown(html, unsafe_allow_html=True)
                elif i == 2: s_col3.markdown(html, unsafe_allow_html=True)

            try: os.remove(downloaded_file_path)
            except: pass

        except Exception as e:
            st.error(f"System Error: {e}")

if __name__ == "__main__":
    main()
