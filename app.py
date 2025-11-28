import streamlit as st
from gtts import gTTS
import tempfile
import base64
import os

st.set_page_config(page_title="gTTS Autoplay", layout="centered")
st.title("gTTS — Autoplay Mode")

# UI
lang = st.selectbox("Language", ["en", "en-uk", "en-us"])
text = st.text_area("Text", "Hi there, I'm your personal assistant.")

def autoplay_audio(mp3_path):
    with open(mp3_path, "rb") as f:
        audio_bytes = f.read()
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f"""
        <audio autoplay controls>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True
    )

if st.button("Speak", key="speak_btn"):
    if not text.strip():
        st.warning("Please enter some text.")
    else:
        tts = gTTS(text=text, lang="en")
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        tts.save(tmp.name)

        autoplay_audio(tmp.name)
        st.success("Done! Your audio is playing automatically.")
