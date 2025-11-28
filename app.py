# streamlit_gtts_stt_safe.py
"""
Safe STT+TTS app:
- Attempts to use streamlit-webrtc; if it errors, falls back to upload-only STT.
- Puts transcript into TTS text area (session_state).
- Uses SpeechRecognition (Google) and pydub for conversions.
"""

import streamlit as st
from gtts import gTTS
import tempfile, os, io, base64, time
import numpy as np

# Try to import webrtc; we'll handle absence or runtime exceptions gracefully
webrtc_available = True
try:
    from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
except Exception as e:
    webrtc_available = False
    webrtc_import_error = e

# STT deps
import speech_recognition as sr
from pydub import AudioSegment

# Optional: soundfile fallback removal to reduce system deps
import soundfile as sf

st.set_page_config(page_title="gTTS + STT (safe)", layout="centered")
st.title("gTTS — Autoplay + STT (robust)")

# -------------------------
# TTS UI (session_state-backed)
# -------------------------
if "tts_text" not in st.session_state:
    st.session_state["tts_text"] = "Hi there, I'm your personal assistant."

lang = st.selectbox("Language (gTTS codes)", ["en", "en-uk", "en-us", "de", "fr"], index=0)
text = st.text_area("Text to speak", value=st.session_state["tts_text"], key="tts_text")

def autoplay_audio_bytes(audio_bytes: bytes):
    b64 = base64.b64encode(audio_bytes).decode()
    st.markdown(
        f"""
        <audio autoplay controls>
            <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """,
        unsafe_allow_html=True,
    )

if st.button("Speak (TTS)"):
    if not text.strip():
        st.warning("Please enter some text.")
    else:
        gtts_lang = lang.split("-")[0]
        tts = gTTS(text=text, lang=gtts_lang)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        try:
            tts.save(tmp.name)
            with open(tmp.name, "rb") as f:
                autoplay_audio_bytes(f.read())
            st.success("Done! Audio playing.")
        finally:
            try:
                tmp.close(); os.unlink(tmp.name)
            except Exception:
                pass

st.markdown("---")

# -------------------------
# STT logic (webrtc attempt + fallback)
# -------------------------
st.header("Speech-to-Text (STT)")

recog = sr.Recognizer()

def transcribe_wav_bytes(wav_bytes: bytes) -> str:
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    try:
        tmp.write(wav_bytes)
        tmp.flush()
        tmp.close()
        with sr.AudioFile(tmp.name) as source:
            audio_data = recog.record(source)
        try:
            return recog.recognize_google(audio_data)
        except sr.UnknownValueError:
            return "(Could not understand audio)"
        except sr.RequestError as e:
            return f"(Could not request results; {e})"
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

transcript = None
last_audio_preview = None

# --- Try webrtc, but guard against runtime errors ---
if webrtc_available:
    try:
        RTC_CONFIGURATION = RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]})
        webrtc_ctx = webrtc_streamer(
            key="stt",
            mode=WebRtcMode.SENDONLY,
            rtc_configuration=RTC_CONFIGURATION,
            media_stream_constraints={"audio": True, "video": False},
            async_processing=False,
        )

        st.write("If the WebRTC widget is available above, click Start then use the Record button below.")
        record_seconds = st.number_input("Record duration (seconds)", min_value=1, max_value=30, value=5, step=1)

        if st.button("Record using WebRTC"):
            if webrtc_ctx and webrtc_ctx.state.playing:
                st.info(f"Recording {record_seconds}s — speak now")
                frames = []
                start = time.time()
                while time.time() - start < float(record_seconds):
                    try:
                        new_frames = webrtc_ctx.audio_receiver.get_frames(timeout=1.0)
                    except Exception:
                        new_frames = []
                    if new_frames:
                        frames.extend(new_frames)
                if not frames:
                    st.error("No frames captured. Try allowing microphone or use upload fallback below.")
                else:
                    # convert frames -> wav bytes (simple path using soundfile)
                    chunks = []
                    sr_rate = None
                    for frame in frames:
                        try:
                            arr = frame.to_ndarray()
                        except Exception:
                            arr = np.asarray(frame)
                        if arr.ndim == 2:
                            arr = np.mean(arr, axis=0)
                        chunks.append(arr)
                        if sr_rate is None:
                            try:
                                sr_rate = frame.sample_rate
                            except Exception:
                                sr_rate = 48000
                    audio_np = np.concatenate(chunks).astype(np.float32)
                    bio = io.BytesIO()
                    sf.write(bio, audio_np, sr_rate, format="WAV")
                    wav_bytes = bio.getvalue()
                    last_audio_preview = wav_bytes
                    st.audio(wav_bytes, format="audio/wav")
                    st.write("Transcribing...")
                    transcript = transcribe_wav_bytes(wav_bytes)
            else:
                st.error("WebRTC streamer is not running. Use the upload fallback below.")
    except Exception as e:
        # Catch internal streamlit-webrtc runtime issues (like the thread AttributeError)
        st.error("WebRTC recording failed to initialize — falling back to upload-only mode.")
        st.exception(e)
        webrtc_available = False

# --- Upload fallback (always available) ---
st.markdown("### Fallback: upload an audio file")
uploaded = st.file_uploader("Upload audio (wav, mp3, m4a, webm)", type=["wav", "mp3", "m4a", "webm"])
if uploaded is not None:
    st.write("Processing uploaded file...")
    raw = uploaded.read()
    last_audio_preview = raw
    try:
        seg = AudioSegment.from_file(io.BytesIO(raw))
        bio = io.BytesIO()
        seg.export(bio, format="wav")
        wavbytes = bio.getvalue()
        st.audio(wavbytes)
        transcript = transcribe_wav_bytes(wavbytes)
    except Exception as e:
        st.error(f"Upload conversion/transcription failed: {e}")

# Show preview and transcript
if last_audio_preview:
    st.subheader("Preview recorded/uploaded audio")
    st.audio(last_audio_preview)

if transcript:
    st.subheader("Transcription result")
    st.write(transcript)
    if st.button("Put transcription into TTS text area"):
        st.session_state["tts_text"] = transcript
        st.success("Transcription placed into TTS text area.")
        st.experimental_rerun()

st.caption("If WebRTC fails repeatedly on Streamlit Cloud, use the upload fallback. For persistent WebRTC problems, try adjusting streamlit-webrtc version or removing soundfile and using pydub-only conversion.")
