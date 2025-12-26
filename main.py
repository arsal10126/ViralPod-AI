import os

# --- 1. SERVER CONFIGURATION ---
os.environ["STREAMLIT_SERVER_MAX_UPLOAD_SIZE"] = "10000"
os.environ["STREAMLIT_SERVER_ENABLE_CORS"] = "false"
os.environ["STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION"] = "false"
os.environ["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"

import streamlit as st
import time
import json
import re
import requests
import google.generativeai as genai
from pathlib import Path
from dotenv import load_dotenv
import yt_dlp
import gc
from moviepy.editor import VideoFileClip, AudioFileClip

# --- 2. PREMIUM UI SETUP ---
st.set_page_config(
    page_title="ViralPod AI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

load_dotenv()

# High-Tech "Silicon Valley" CSS Injection
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;800&display=swap');
    
    html, body, [class*="css"] { 
        font-family: 'Inter', sans-serif; 
        background-color: #020617; 
        color: #f8fafc;
    }

    /* Gradient Brand Header */
    .main-header {
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 3.5rem;
        letter-spacing: -1px;
        margin-bottom: 0.5rem;
        text-shadow: 0 0 30px rgba(99, 102, 241, 0.3);
    }

    /* Input Container Styling */
    .input-container {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 24px;
        padding: 30px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }

    /* Clean Input Fields */
    .stTextInput > div > div > input {
        background-color: #0f172a !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 15px;
        font-size: 1rem;
        transition: all 0.2s;
    }
    .stTextInput > div > div > input:focus {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.2);
    }

    /* Button Styling */
    .stButton > button {
        background: linear-gradient(90deg, #4f46e5 0%, #7c3aed 100%);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 1rem 2rem;
        font-weight: 700;
        letter-spacing: 1px;
        text-transform: uppercase;
        width: 100%;
        box-shadow: 0 10px 25px -5px rgba(79, 70, 229, 0.4);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        transform: translateY(-2px) scale(1.01);
        box-shadow: 0 20px 25px -5px rgba(79, 70, 229, 0.5);
    }

    /* Result Cards */
    .glass-card {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 24px;
        height: 100%;
        transition: transform 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .glass-card:hover {
        transform: translateY(-5px);
        border-color: rgba(139, 92, 246, 0.5);
        box-shadow: 0 10px 40px -10px rgba(139, 92, 246, 0.2);
    }

    /* Badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-purple { background: rgba(139, 92, 246, 0.2); color: #c4b5fd; border: 1px solid rgba(139, 92, 246, 0.3); }
    .badge-green { background: rgba(16, 185, 129, 0.2); color: #6ee7b7; border: 1px solid rgba(16, 185, 129, 0.3); }
    .badge-red { background: rgba(239, 68, 68, 0.2); color: #fca5a5; border: 1px solid rgba(239, 68, 68, 0.3); }

    /* Hiding Streamlit Branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
</style>
""", unsafe_allow_html=True)

# --- 3. INTERNAL LOGIC ---

def get_api_key():
    api_key = None
    try:
        if "GOOGLE_API_KEY" in st.secrets: api_key = st.secrets["GOOGLE_API_KEY"]
    except FileNotFoundError: pass
    if not api_key: api_key = os.getenv("GOOGLE_API_KEY")
    return api_key

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def convert_to_audio_optimized(input_path):
    try:
        output_path = str(input_path).rsplit(".", 1)[0] + ".mp3"
        if str(input_path).endswith((".mp3", ".m4a", ".wav")):
            return input_path
        audio_clip = AudioFileClip(str(input_path))
        audio_clip.write_audiofile(output_path, bitrate="64k", logger=None)
        audio_clip.close()
        if os.path.exists(input_path): os.remove(input_path) 
        return output_path
    except Exception as e:
        return input_path

def smart_downloader(url, output_dir):
    sanitized_output = os.path.join(output_dir, '%(title)s.%(ext)s')
    ydl_opts = {
        'format': 'bestaudio/worst', 
        'outtmpl': sanitized_output,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'compat_opts': ['no-live-chat'], 
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return ydl.prepare_filename(info)
    except Exception as e:
        if "http" in url:
            filename = os.path.join(output_dir, "direct_download.mp4")
            response = requests.get(url, stream=True)
            with open(filename, 'wb') as f:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    f.write(chunk)
            return filename
        raise e

def save_uploaded_chunked(uploaded_file, path):
    with open(path, "wb") as f:
        while True:
            chunk = uploaded_file.read(10 * 1024 * 1024)
            if not chunk: break
            f.write(chunk)
    uploaded_file = None
    gc.collect()
    return path

def upload_to_gemini_turbo(file_path):
    file = genai.upload_file(file_path, mime_type="audio/mp3")
    bar = st.progress(0)
    while file.state.name == "PROCESSING":
        time.sleep(0.5)
        bar.progress(50)
        file = genai.get_file(file.name)
    bar.progress(100)
    time.sleep(0.2)
    bar.empty()
    if file.state.name == "FAILED":
        raise ValueError("Neural Engine could not process this video format.")
    return file

def analyze_with_flash_lite(file_obj):
    # Maintaining Gemini 2.5 Flash Lite as requested
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    
    # THE BILLION DOLLAR PROMPT
    prompt = """
    You are ViralPod AI, an elite Senior Video Editor and Content Strategist. 
    Analyze the provided audio/video file and extract a structured Edit Decision List (EDL).
    
    You must output strictly in JSON format.
    
    ### OBJECTIVES:
    
    1. **The 'Hook' Intro (Total 25-30s):**
       - Find 2-3 rapid-fire, high-energy sentences that define the episode.
       - These will be stitched together to create a 30-second cold open.
    
    2. **The Movie Trailer (Total 60-90s):**
       - Select 4-5 clips that build a narrative arc (Setup -> Conflict -> Tease).
       - Ensure these clips do not reveal the final secrets, just the excitement.
    
    3. **Viral Shorts (3-4 distinct clips):**
       - Find standalone moments suitable for TikTok/Reels (Vertical Video).
       - Criteria: High emotion, controversy, strong humor, or specific "knowledge bombs."
       - Duration per clip: 30s to 60s.
    
    4. **The 'Mistake Hunter' (Quality Control):**
       - Identify technical and performance errors to be removed.
       - **Long Silence:** Dead air > 7 seconds.
       - **Audio Disturbances:** Coughing ("Khansi"), sneezing, loud throat clearing.
       - **Editor Commands:** If a speaker says "Cut this," "Delete that," "Start over," or "Ghalti hogayi" (Mistake).
    
    ### OUTPUT SCHEMA (JSON ONLY):
    {
      "intro_sequence": [
        {"start": "MM:SS", "end": "MM:SS", "text": "...", "reason": "High energy hook"}
      ],
      "trailer_structure": [
        {"start": "MM:SS", "end": "MM:SS", "text": "...", "narrative_role": "Setup/Climax"}
      ],
      "viral_shorts": [
        {"start": "MM:SS", "end": "MM:SS", "title": "Catchy Title", "virality_score": "9/10", "reason": "..."}
      ],
      "mistakes_log": [
        {"timestamp": "MM:SS", "error_type": "Silence/Cough/Command", "description": "Speaker coughed/Asked to cut"}
      ]
    }
    """
    response = model.generate_content(
        [file_obj, prompt],
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# --- 4. MAIN APPLICATION ---

def main():
    api_key = get_api_key()
    if api_key: genai.configure(api_key=api_key)
    else: st.warning("⚠️ System Key Missing")

    st.markdown('<div style="text-align: center; padding: 40px 0;"><h1 class="main-header">ViralPod AI</h1><p style="color: #94a3b8; font-size: 1.2rem;">Enterprise-Grade Video Intelligence</p></div>', unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 6, 1])
    with col2:
        st.markdown('<div class="input-container">', unsafe_allow_html=True)
        tab_link, tab_file = st.tabs(["🔗 INTELLIGENT LINK", "📂 SECURE UPLOAD"])
        
        source = None
        input_val = None
        
        with tab_link:
            url = st.text_input("URL Input", placeholder="Paste YouTube / Google Drive / Dropbox Link", key="url_input", label_visibility="collapsed")
            if url: 
                source = "url"
                input_val = url

        with tab_file:
            uploaded = st.file_uploader("File Upload", type=['mp4','mov','mp3','wav','m4a'], label_visibility="collapsed")
            if uploaded:
                source = "upload"
                input_val = uploaded

        st.markdown("<br>", unsafe_allow_html=True)
        start_btn = st.button("INITIALIZE ANALYSIS SEQUENCE")
        st.markdown('</div>', unsafe_allow_html=True)

    if start_btn and input_val:
        if not api_key: st.error("Authorization Failed"); return

        temp_dir = Path("temp_workspace")
        temp_dir.mkdir(exist_ok=True)
        final_audio_path = None
        raw_download_path = None

        try:
            # --- PHASE 1: ACQUISITION ---
            with st.status("🚀 ViralPod AI Sequence Initiated...", expanded=True) as status:
                
                if source == "url":
                    st.write("Target acquired. Establishing secure stream...")
                    raw_download_path = smart_downloader(input_val, str(temp_dir))
                    st.write("Stream captured successfully.")
                
                elif source == "upload":
                    st.write("Verifying file integrity...")
                    raw_download_path = temp_dir / sanitize_filename(input_val.name)
                    save_uploaded_chunked(input_val, raw_download_path)
                    st.write("Upload buffered to secure storage.")

                st.write("Optimizing video data for Neural Engine...")
                final_audio_path = convert_to_audio_optimized(raw_download_path)
                
                status.update(label="Ingestion Complete", state="complete")

            # --- PHASE 2: PROCESSING ---
            st.toast("ViralPod AI is uploading your content to the Neural Engine...", icon="☁️")
            gemini_file = upload_to_gemini_turbo(final_audio_path)
            
            # --- PHASE 3: ANALYSIS ---
            with st.spinner("ViralPod AI is analyzing your video... (This may take up to 5 minutes depending on duration)"):
                data = analyze_with_flash_lite(gemini_file)

            # --- PHASE 4: RESULTS RENDER ---
            st.markdown("<br><br>", unsafe_allow_html=True)
            
            # --- INTRO SEQUENCE ---
            st.markdown("<h3 style='color: white;'>🔥 The Perfect Cold Open (Intro)</h3>", unsafe_allow_html=True)
            intro_seq = data.get('intro_sequence', [])
            if intro_seq:
                for clip in intro_seq:
                    st.markdown(f"""
                    <div class="glass-card" style="margin-bottom: 10px; padding: 15px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span class="badge badge-purple">HOOK CLIP</span>
                            <span style="font-family:monospace; color:#94a3b8; font-weight:bold;">{clip.get('start')} - {clip.get('end')}</span>
                        </div>
                        <p style="color:#e2e8f0; margin-top:10px; font-style:italic;">"{clip.get('text')}"</p>
                        <p style="color:#64748b; font-size:0.8rem; margin-top:5px;">Reason: {clip.get('reason')}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No clear intro hooks found.")

            st.markdown("<br>", unsafe_allow_html=True)

            # --- TRAILER STRUCTURE ---
            st.markdown("<h3 style='color: white;'>🎬 Cinematic Trailer Arc</h3>", unsafe_allow_html=True)
            trailer_seq = data.get('trailer_structure', [])
            if trailer_seq:
                for clip in trailer_seq:
                    st.markdown(f"""
                    <div class="glass-card" style="margin-bottom: 10px; padding: 15px; border-left: 3px solid #f472b6;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <span style="color: #f472b6; font-weight:bold; font-size:0.8rem;">{clip.get('narrative_role', 'Clip').upper()}</span>
                            <span style="font-family:monospace; color:#94a3b8;">{clip.get('start')} - {clip.get('end')}</span>
                        </div>
                        <p style="color:#cbd5e1; margin-top:5px;">{clip.get('text')}</p>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("Insufficient data for trailer generation.")

            # --- VIRAL SHORTS ---
            st.markdown("<h3 style='margin-top:40px; text-align:center; color:white;'>📱 Viral Shorts Candidates</h3>", unsafe_allow_html=True)
            shorts = data.get('viral_shorts', [])
            if shorts:
                cols = st.columns(3)
                for i, clip in enumerate(shorts):
                    col_idx = i % 3
                    with cols[col_idx]:
                        st.markdown(f"""
                        <div class="glass-card">
                            <div style="display:flex; justify-content:space-between;">
                                <span class="badge badge-green">SHORT #{i+1}</span>
                                <span style="font-family:monospace; color:#94a3b8;">{clip.get('start')}</span>
                            </div>
                            <h4 style="margin-top:10px; font-weight:600; color:white;">{clip.get('title')}</h4>
                            <p style="color:#94a3b8; font-size:0.85rem; margin-top:5px;">{clip.get('reason')}</p>
                            <div style="margin-top:10px; font-weight:700; color:#fff;">Score: {clip.get('virality_score')}</div>
                        </div>
                        """, unsafe_allow_html=True)

            # --- MISTAKES LOG ---
            st.markdown("<br><hr style='border-color: #334155'><br>", unsafe_allow_html=True)
            st.markdown("<h3 style='color: #ef4444;'>🛠️ The Mistake Hunter Log</h3>", unsafe_allow_html=True)
            
            mistakes = data.get('mistakes_log', [])
            if mistakes:
                for error in mistakes:
                    st.markdown(f"""
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); padding: 10px 15px; border-radius: 8px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
                        <div>
                            <span class="badge badge-red">{error.get('error_type')}</span>
                            <span style="color: #fca5a5; margin-left: 10px;">{error.get('description')}</span>
                        </div>
                        <span style="font-family:monospace; color:#fca5a5; font-weight:bold;">{error.get('timestamp')}</span>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.success("No major technical errors detected.")

            try: 
                if final_audio_path: os.remove(final_audio_path)
            except: pass

        except Exception as e:
            st.error(f"Execution Halted: {str(e)}")

if __name__ == "__main__":
    main()
