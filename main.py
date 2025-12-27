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

    /* Input Container */
    .input-container {
        background: rgba(15, 23, 42, 0.6);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid rgba(148, 163, 184, 0.1);
        border-radius: 24px;
        padding: 30px;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    }

    /* Inputs */
    .stTextInput > div > div > input {
        background-color: #0f172a !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
        border-radius: 12px;
        padding: 15px;
        font-size: 1rem;
    }
    .stTextInput > div > div > input:focus {
        border-color: #818cf8 !important;
        box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.2);
    }

    /* Buttons */
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

    /* UI Cards */
    .glass-card {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 20px;
        padding: 24px;
        margin-bottom: 15px;
    }

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

# --- UPDATED: DUAL-AGENT ANALYSIS LOGIC ---
def analyze_with_flash_lite(file_obj):
    # Using Gemini 2.5 Flash Lite (Keeping the model as requested)
    model = genai.GenerativeModel("gemini-2.5-flash-lite")
    
    print("🚀 ViralPod AI: Starting Double-Agent Analysis...")

    # ==========================================
    # AGENT 1: THE CREATIVE DIRECTOR
    # ==========================================
    creative_prompt = """
    You are ViralPod AI, an Elite Senior Video Editor and Content Strategist. Your job is to EDIT a raw podcast into high-value assets by analyzing the audio/video **from 00:00 to the very last second**.
    
    ### CORE ANALYSIS PROTOCOL (STRICT):
    1. **FULL SPECTRUM SCAN:** You must analyze the file from 0 seconds to the very end. Do not skip any section.
    2. **EDITORIAL WISDOM:** For every clip you select, you must provide a "Wisdom" explanation. Why is this specific 30s clip better than the other 59 minutes? Explain the retention psychology, the emotional hook, or the value proposition.
    3. **NO LAZY HOOKS:** Do NOT just pick the first 60 seconds for the Intro. Scan the MIDDLE (40-60%) and END (80-90%) for the most shocking statements.
    4. **IGNORE SMALL TALK:** Ignore "Hi, how are you", "Thanks for coming", or "Welcome to the show."
    5. **STRICT TIMESTAMPS:** All start/end times must be exact format MM:SS.
    
    ### DELIVERABLES:
    
    **1. The "Cold Open" Teaser (Total 30s)**
       - Find 3 specific, punchy sentences or groups of sentences, minimum total duration must 30 secs long that represent the CLIMAX or SHOCKING MOMENT of the episode.
       - These clips must come from deep inside the conversation.
       - **Wisdom:** Explain why these specific lines will force a viewer to stop scrolling and watch the full episode.
    
    **2. The Pod Trailer (Total 60-90s)**
       - Select 4-5 clips that build a Story Arc:
         * Clip 1: The Problem/Conflict.
         * Clip 2: The Debate/Argument.
         * Clip 3: The "Wait, what?" Moment.
         * Clip 4: The Tease (Don't reveal the final answer).
       - **Wisdom:** Explain how this specific sequence creates suspense.
    
    **3. Viral Shorts/Reels (3-4 Distinct Clips)**
       - Find standalone moments (tiny stories) suitable for TikTok/Reels.
       - Duration: 30s to 60s per clip.
       - **Viral Score:** You must assign a score from **1-10** (10 being absolutely viral).
       - **Wisdom:** Detailed reasoning is required. Why did you select this? Is it a "Knowledge Bomb"? Is it a "Controversial Take"? Explain the viral psychology.
    
    ### OUTPUT SCHEMA (JSON ONLY - NO MARKDOWN):
    {
      "cold_open_clips": [
        {"start": "MM:SS", "end": "MM:SS", "text": "...", "reason": "Detailed editorial wisdom on why this hook beats the rest."}
      ],
      "trailer_structure": [
        {"start": "MM:SS", "end": "MM:SS", "text": "...", "narrative_role": "Conflict/Climax", "reason": "Wisdom on why this fits the story arc."}
      ],
      "viral_shorts": [
        {"start": "MM:SS", "end": "MM:SS", "title": "Catchy Title", "text": "text transcript", "virality_score": "9/10", "reason": "Detailed viral psychology analysis. Why this clip will stop the scroll."}
      ]
    }
    """
    
    response_creative = model.generate_content(
        [file_obj, creative_prompt],
        generation_config={"response_mime_type": "application/json"}
    )
    
    try:
        creative_data = json.loads(response_creative.text)
    except Exception as e:
        creative_data = {}

    # ==========================================
    # AGENT 2: THE TECHNICAL INSPECTOR
    # ==========================================
    technical_prompt = """
    You are ViralPod AI's Technical Quality Inspector. Your ONLY job is to find errors and technical issues in the entire file.
    
    ### CORE ANALYSIS PROTOCOL (STRICT):
    1. **FULL SPECTRUM SCAN:** Analyze from 00:00 to End.
    2. **STRICT TIMESTAMPS:** Exact MM:SS format.
    
    ### DELIVERABLE: The 'Mistake Hunter' (Quality Control)
       - Identify errors to be removed.
       - **Long Silence:** Dead air > 8 seconds mean no music, no background sounds etc.
       - **Audio Disturbances:** Coughing ("Khansi"), sneezing, loud throat clearing.
       - **Editor Commands:** Phrases like "Cut this," "Delete that," "Start over," or "Ghalti hogayi" (Mistake), Repeated sentences for correction etc
    
    ### OUTPUT SCHEMA (JSON ONLY - NO MARKDOWN):
    {
      "mistakes_log": [
        {"start": "MM:SS", "end": "MM:SS", "error_type": "Silence/Cough/Command", "description": "Speaker coughed/Asked to cut"}
      ]
    }
    """
    
    response_technical = model.generate_content(
        [file_obj, technical_prompt],
        generation_config={"response_mime_type": "application/json"}
    )

    try:
        technical_data = json.loads(response_technical.text)
    except Exception as e:
        technical_data = {"mistakes_log": []}

    # ==========================================
    # FINAL STEP: MERGE
    # ==========================================
    full_report = {**creative_data, **technical_data}
    return full_report

# --- 4. MAIN APPLICATION ---

def main():
    api_key = get_api_key()
    if api_key: genai.configure(api_key=api_key)
    else: st.warning("⚠️ System Key Missing")

    # Initialize Session State Variables to prevent crash
    if 'analysis_data' not in st.session_state:
        st.session_state['analysis_data'] = None
    if 'view_mode' not in st.session_state:
        st.session_state['view_mode'] = "Creative"

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

    # --- EXECUTION LOGIC ---
    if start_btn and input_val:
        if not api_key: st.error("Authorization Failed"); return

        temp_dir = Path("temp_workspace")
        temp_dir.mkdir(exist_ok=True)
        final_audio_path = None
        raw_download_path = None

        try:
            # PHASE 1: ACQUISITION (Only runs if button clicked)
            with st.status("🚀 ViralPod AI Sequence Initiated...", expanded=True) as status:
                if source == "url":
                    st.write("Target acquired. Establishing secure stream...")
                    raw_download_path = smart_downloader(input_val, str(temp_dir))
                    st.write("Stream captured successfully.")
                elif source == "upload":
                    st.write("Verifying file integrity...")
                    raw_download_path = temp_dir / sanitize_filename(input_val.name)
                    save_uploaded_chunked(input_val, raw_download_path)
                    st.write("Upload buffered.")

                st.write("Optimizing video data for Neural Engine...")
                final_audio_path = convert_to_audio_optimized(raw_download_path)
                status.update(label="Ingestion Complete", state="complete")

            # PHASE 2: PROCESSING
            st.toast("ViralPod AI is uploading your content to the Neural Engine...", icon="☁️")
            gemini_file = upload_to_gemini_turbo(final_audio_path)
            
            # PHASE 3: ANALYSIS (Save to Session State)
            with st.spinner("ViralPod AI is running Double-Agent Analysis (Creative + Technical)..."):
                st.session_state['analysis_data'] = analyze_with_flash_lite(gemini_file)
                st.session_state['view_mode'] = "Creative" # Reset to Creative on new analysis
            
            st.success("Analysis Complete! Workspace Ready.")
            
            # Cleanup
            try: 
                if final_audio_path: os.remove(final_audio_path)
            except: pass

        except Exception as e:
            st.error(f"Execution Halted: {str(e)}")

    # --- DASHBOARD RENDER (Runs from Session State) ---
    if st.session_state['analysis_data']:
        data = st.session_state['analysis_data']
        
        st.divider()
        
        # 1. THE "TWO BUTTONS" INTERFACE
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✨ Get Viral Assets (Intro, Shorts)", use_container_width=True):
                st.session_state['view_mode'] = "Creative"
        with col2:
            if st.button("🛠️ Fix Mistakes (Silence, Errors)", use_container_width=True):
                st.session_state['view_mode'] = "Technical"

        st.divider()

        # 2. CONDITIONAL DISPLAY
        
        # --- OPTION 1: CREATIVE MODE ---
        if st.session_state['view_mode'] == "Creative":
            st.header("✨ Creative Studio")
            
            # A. Cold Open
            st.subheader("🔥 Cold Open Teaser (0-30s)")
            for clip in data.get('cold_open_clips', []):
                with st.expander(f"⏰ {clip['start']} - {clip['end']}"):
                    st.write(f"**Script:** \"{clip['text']}\"")
                    # Fallback to 'reason' if 'wisdom' key is missing to prevent errors
                    st.info(f"💡 **Wisdom:** {clip.get('reason', clip.get('wisdom', 'No reasoning provided'))}")
            
            st.markdown("---")

            # B. Trailer
            st.subheader("🎬 Movie Trailer Arc")
            for clip in data.get('trailer_structure', []):
                with st.container(border=True):
                    st.write(f"**{clip.get('narrative_role', 'Clip')}** ({clip['start']} - {clip['end']})")
                    st.caption(f"\"{clip['text']}\"")
                    st.write(f"*Why:* {clip.get('reason', 'N/A')}")

            st.markdown("---")

            # C. Viral Shorts
            st.subheader("📱 Viral Short Clips ")
            for short in data.get('viral_shorts', []):
                st.markdown(f"#### 🎬 {short.get('title', 'Untitled Clip')}")
                # Handling viral_score vs score key difference
                score = short.get('virality_score', short.get('score', 0))
                st.caption(f"**Viral Score:** {score}/10")
                st.write(f"**Wisdom:** {short.get('reason', short.get('wisdom', 'N/A'))}")
                st.code(f"Cut: {short['start']} --> {short['end']}")
                st.markdown("---")

        # --- OPTION 2: TECHNICAL MODE ---
            elif st.session_state['view_mode'] == "Technical":
        st.header("🛠️ Quality Control Room")
        
        mistakes = data.get('mistakes_log', [])
        if not mistakes:
            st.success("✅ No critical errors found! Great recording.")
        else:
            count = len(mistakes)
            st.warning(f"⚠️ Inspector found {count} issues to fix.")
            
            for error in mistakes:
                # Determine Icon based on error type
                icon = "🛑" if "Command" in error.get('error_type', '') else "🤧" if "Cough" in error.get('error_type', '') else "🔇"
                
                # Get timestamps safely
                start_time = error.get('start', '00:00')
                end_time = error.get('end', '00:00')
                
                with st.container(border=True):
                    c1, c2 = st.columns([1, 5]) # Adjusted width for better look
                    
                    with c1:
                        st.markdown(f"## {icon}")
                        # Display the Time Range clearly
                        st.markdown(f"**{start_time}**")
                        st.caption("⬇ to")
                        st.markdown(f"**{end_time}**")
                        
                    with c2:
                        st.subheader(error.get('error_type', 'Unknown Error'))
                        st.write(error.get('description', 'No description'))
                        
                        # Fake "Fix" button using the start time as unique ID
                        if st.button("Mark Fixed", key=f"fix_{start_time}_{end_time}"):
                            st.toast(f"Fixed error at {start_time}!")

if __name__ == "__main__":
    main()
