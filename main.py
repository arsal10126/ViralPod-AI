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

# --- CONFIGURATION & SETUP ---
st.set_page_config(
    page_title="ViralPod AI",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Load environment variables
load_dotenv()

# Style tweaks
st.markdown("""
<style>
    .stButton>button { width: 100%; border-radius: 5px; }
    .success-box { padding: 1rem; background-color: #d4edda; color: #155724; border-radius: 5px; margin-bottom: 1rem; }
    .metric-card { background-color: #f0f2f6; padding: 15px; border-radius: 10px; border-left: 5px solid #ff4b4b; }
</style>
""", unsafe_allow_html=True)

# --- HELPER FUNCTIONS ---

def get_api_key():
    """Retrieves API Key from st.secrets, env, or sidebar."""
    api_key = None
    
    # Priority 1: Streamlit Secrets
    try:
        if "GOOGLE_API_KEY" in st.secrets:
            api_key = st.secrets["GOOGLE_API_KEY"]
    except FileNotFoundError:
        pass

    # Priority 2: Environment Variables
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY")
    
    # Priority 3: Sidebar Input
    if not api_key:
        with st.sidebar:
            st.warning("⚠️ No API Key found in secrets.toml or .env")
            api_key = st.text_input("Enter Gemini API Key", type="password")
    return api_key

def sanitize_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', "", filename)

def process_dropbox_link(url):
    """Converts a Dropbox DL=0 link to a DL=1 direct link."""
    if "dropbox.com" in url and "dl=0" in url:
        return url.replace("dl=0", "dl=1")
    return url

def download_youtube_video(url, output_dir):
    """Downloads video/audio from YouTube using yt-dlp."""
    sanitized_output = os.path.join(output_dir, '%(title)s.%(ext)s')
    
    # We prefer lower resolution video + best audio for faster AI processing
    # Gemini Flash handles audio/video tokens very well.
    ydl_opts = {
        'format': 'best[height<=480]/best', 
        'outtmpl': sanitized_output,
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        return filename

def download_file_from_url(url, output_path):
    """Downloads a file from a direct URL (Dropbox/Direct)."""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    return output_path

def upload_to_gemini(file_path, mime_type=None):
    """Uploads file to Gemini and waits for processing."""
    file = genai.upload_file(file_path, mime_type=mime_type)
    
    with st.status(f"Processing media on Gemini server...", expanded=True) as status:
        while file.state.name == "PROCESSING":
            st.write("Media is processing... (Encoding)")
            time.sleep(2)
            file = genai.get_file(file.name)
        
        if file.state.name == "FAILED":
            status.update(label="Processing Failed", state="error")
            raise ValueError("Gemini failed to process the file.")
            
        status.update(label="Media Ready for Analysis!", state="complete")
    return file

def analyze_content(file_obj):
    """Sends the prompt to Gemini Flash."""
    model = genai.GenerativeModel(model_name="gemini-1.5-flash")
    
    # Enforcing strict JSON structure
    prompt = """
    You are a professional Video Editor and Viral Content Strategist. 
    Analyze the provided video/audio file.
    
    Your goal is to extract the most viral-worthy clips.
    Return a STRICT JSON object with the following structure:
    {
        "viral_shorts": [
            {"title": "Catchy Title 1", "start": "MM:SS", "end": "MM:SS", "reasoning": "Why this is viral", "viral_score": 95},
            {"title": "Catchy Title 2", "start": "MM:SS", "end": "MM:SS", "reasoning": "Why this is viral", "viral_score": 88},
            {"title": "Catchy Title 3", "start": "MM:SS", "end": "MM:SS", "reasoning": "Why this is viral", "viral_score": 85}
        ],
        "hook_intro": {
            "title": "Perfect Hook", "start": "MM:SS", "end": "MM:SS", "reasoning": "Why this grabs attention", "viral_score": 90
        },
        "trailer_segment": {
            "title": "High Energy Trailer", "start": "MM:SS", "end": "MM:SS", "reasoning": "Best summary segment", "viral_score": 92
        }
    }
    
    Constraints:
    - Shorts must be 30-60 seconds.
    - Hook/Intro must be 0-15 seconds.
    - Trailer should be high energy.
    - Viral Score is an integer 0-100.
    """
    
    response = model.generate_content(
        [file_obj, prompt],
        generation_config={"response_mime_type": "application/json"}
    )
    return json.loads(response.text)

# --- MAIN APP LOGIC ---

def main():
    st.title("🚀 ViralPod AI")
    st.markdown("Extract viral Shorts, Intros, and Trailers from any video using **Gemini 1.5 Flash**.")
    
    api_key = get_api_key()
    if api_key:
        genai.configure(api_key=api_key)
    
    # Create temp directory
    temp_dir = Path("temp_media")
    temp_dir.mkdir(exist_ok=True)

    # Input Method Selection
    tab_url, tab_upload = st.tabs(["🔗 Paste URL", "📂 Upload File"])
    
    source_path = None
    media_source = None

    with tab_url:
        url_input = st.text_input("Paste YouTube, Google Drive, Dropbox, or Direct Link")
        if url_input:
            media_source = "url"

    with tab_upload:
        uploaded_file = st.file_uploader("Upload MP3, MP4, WAV, MOV", type=["mp3", "mp4", "wav", "mov", "m4a"])
        if uploaded_file:
            media_source = "upload"

    # Process Button
    if st.button("✨ Find Viral Clips", type="primary", disabled=not (url_input or uploaded_file)):
        if not api_key:
            st.error("Please provide a Gemini API Key.")
            return

        try:
            downloaded_file_path = None
            
            # --- STEP 1: ACQUIRE MEDIA ---
            with st.spinner("Acquiring Media..."):
                if media_source == "upload":
                    downloaded_file_path = temp_dir / sanitize_filename(uploaded_file.name)
                    with open(downloaded_file_path, "wb") as f:
                        f.write(uploaded_file.getbuffer())
                
                elif media_source == "url":
                    # Determine Source Type
                    if "youtube.com" in url_input or "youtu.be" in url_input:
                        st.info("Detected YouTube URL...")
                        downloaded_file_path = download_youtube_video(url_input, str(temp_dir))
                    
                    elif "drive.google.com" in url_input:
                        st.info("Detected Google Drive URL...")
                        # Handle view links vs id
                        file_id = None
                        if "id=" in url_input:
                            file_id = url_input.split("id=")[1].split("&")[0]
                        elif "/d/" in url_input:
                            file_id = url_input.split("/d/")[1].split("/")[0]
                        
                        if file_id:
                            output_path = temp_dir / f"gdrive_file_{file_id}.mp4"
                            # Using gdown's robust download
                            url = f'https://drive.google.com/uc?id={file_id}'
                            gdown.download(url, str(output_path), quiet=False)
                            downloaded_file_path = str(output_path)
                        else:
                            st.error("Could not parse Google Drive ID.")
                            return

                    elif "dropbox.com" in url_input:
                        st.info("Detected Dropbox URL...")
                        direct_link = process_dropbox_link(url_input)
                        output_path = temp_dir / "dropbox_file.mp4"
                        downloaded_file_path = download_file_from_url(direct_link, output_path)
                    
                    else:
                        st.info("Detected Direct URL...")
                        output_path = temp_dir / "direct_download_file.mp4"
                        downloaded_file_path = download_file_from_url(url_input, output_path)

            if not downloaded_file_path or not os.path.exists(downloaded_file_path):
                st.error("Failed to download or process the file.")
                return

            st.success(f"Media acquired: {os.path.basename(downloaded_file_path)}")

            # --- STEP 2: UPLOAD TO GEMINI ---
            gemini_file = upload_to_gemini(downloaded_file_path)

            # --- STEP 3: ANALYZE ---
            with st.spinner("AI is watching and analyzing for viral moments..."):
                result_json = analyze_content(gemini_file)
            
            # --- STEP 4: DISPLAY RESULTS ---
            st.divider()
            st.subheader("🔥 Viral Analysis Results")
            
            # Display Hook
            hook = result_json.get("hook_intro", {})
            st.markdown(f"### 🪝 The Hook ({hook.get('start')} - {hook.get('end')})")
            st.markdown(f"""
            <div class='metric-card'>
                <h4>{hook.get('title')}</h4>
                <p><b>Viral Score:</b> {hook.get('viral_score')}/100</p>
                <p><i>{hook.get('reasoning')}</i></p>
            </div>
            """, unsafe_allow_html=True)
            
            st.divider()

            # Display Shorts
            st.subheader("📱 Top 3 Viral Shorts")
            shorts = result_json.get("viral_shorts", [])
            cols = st.columns(3)
            
            for i, clip in enumerate(shorts):
                with cols[i]:
                    st.markdown(f"""
                    <div style='background-color: #ffffff; padding: 10px; border-radius: 8px; border: 1px solid #ddd; height: 100%;'>
                        <h4 style='color: #d90429;'>#{i+1}: {clip.get('title')}</h4>
                        <p><b>⏱ {clip.get('start')} - {clip.get('end')}</b></p>
                        <p><b>Score:</b> {clip.get('viral_score')}</p>
                        <p style='font-size: 0.9em;'>{clip.get('reasoning')}</p>
                    </div>
                    """, unsafe_allow_html=True)
            
            st.divider()

            # Display Trailer
            trailer = result_json.get("trailer_segment", {})
            st.markdown(f"### 🎬 High Energy Trailer ({trailer.get('start')} - {trailer.get('end')})")
            st.info(f"**{trailer.get('title')}**: {trailer.get('reasoning')}")

            # Cleanup
            try:
                os.remove(downloaded_file_path)
                # Optional: Delete from Gemini to save storage (Gemini files auto-expire after 48h usually)
                genai.delete_file(gemini_file.name)
            except Exception as e:
                pass # Non-critical cleanup

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    main()