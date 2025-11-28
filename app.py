import base64
import streamlit as st
import asyncio
import tempfile
from edge_tts import Communicate

async def _synthesize_to_file(text_or_ssml: str, voice: str, out_path: str):
    communicator = Communicate(text_or_ssml, voice)
    await communicator.save(out_path)

def synthesize_to_file(text_or_ssml: str, voice="en-US-AriaNeural"):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_path = tmp.name
    tmp.close()
    asyncio.run(_synthesize_to_file(text_or_ssml, voice, tmp_path))
    return tmp_path

def autoplay_html(mp3_path: str):
    # Read file and convert to base64
    with open(mp3_path, "rb") as f:
        mp3_bytes = f.read()
    b64 = base64.b64encode(mp3_bytes).decode()

    # Autoplay HTML audio element
    html = f"""
    <audio autoplay="true">
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
    </audio>
    """
    st.markdown(html, unsafe_allow_html=True)

# ----------------------
# STREAMLIT UI
# ----------------------
st.title("Edge TTS — Autoplay Mode")

voice = st.selectbox("Voice", ["en-US-AriaNeural", "en-GB-LibbyNeural", "en-US-GuyNeural"])

text = st.text_area("Text", "Hi there, I'm your personal assistant.")

if st.button("Speak"):
    mp3_path = synthesize_to_file(text, voice)
    autoplay_html(mp3_path)
    st.success("Done! Audio should autoplay 🎧🔥")


if st.button("Speak"):
    mp3_path = synthesize_to_file(text, voice)
    autoplay_html(mp3_path)
    st.success("Done! Audio should autoplay 🎧🔥")
