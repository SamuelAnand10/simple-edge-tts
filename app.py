# streamlit_gtts_stt_safe.py
"""
streamlit_gtts_stt_htmlrecorder.py

- Uses a pure-HTML/JS in-page recorder (MediaRecorder). The JS provides a Download link for the recorded file.
- The user then uploads that file with the file uploader (or use any recorded file).
- The app converts the uploaded file to WAV via pydub and transcribes with SpeechRecognition (Google).
- Transcription can be placed into the TTS text area and played with gTTS.

Notes:
- This avoids installing fragile recorder libraries.
- pydub requires ffmpeg (add packages.txt with 'ffmpeg' on Streamlit Cloud).
"""

import streamlit as st
from gtts import gTTS
import base64, tempfile, os, io
from pydub import AudioSegment
import speech_recognition as sr

st.set_page_config(page_title="gTTS + STT (HTML Recorder + Upload)", layout="centered")
st.title("gTTS — Autoplay Mode + STT (HTML Recorder + Upload)")

# -------------------------
# TTS section (session_state-backed)
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
            st.success("Done! Your audio is playing automatically.")
        finally:
            try:
                tmp.close(); os.unlink(tmp.name)
            except Exception:
                pass

st.markdown("---")

# -------------------------
# HTML recorder UI
# -------------------------
st.header("Record in your browser (HTML recorder)")

st.write(
    "Click **Record** below, speak, then **Stop**. "
    "Click **Download** to save the file, then upload the saved file with the uploader below for transcription."
)

# Simple HTML + JS recorder using MediaRecorder
RECORDER_HTML = r"""
<style>
.rec-btn { padding:8px 12px; margin:6px; font-size:14px; }
#controls { margin-top: 8px; }
#audioPlayer { margin-top: 10px; width: 100%; }
</style>

<div>
  <button id="recordBtn" class="rec-btn">Start Recording</button>
  <button id="stopBtn" class="rec-btn" disabled>Stop</button>
  <button id="playBtn" class="rec-btn" disabled>Play</button>
  <a id="downloadLink" style="display:none; margin-left: 10px;">Download</a>
  <p id="status" style="font-size:13px; color:#333;"></p>
  <audio id="audioPlayer" controls></audio>
</div>

<script>
let mediaRecorder;
let audioChunks = [];
const recordBtn = document.getElementById('recordBtn');
const stopBtn = document.getElementById('stopBtn');
const playBtn = document.getElementById('playBtn');
const downloadLink = document.getElementById('downloadLink');
const status = document.getElementById('status');
const audioPlayer = document.getElementById('audioPlayer');

recordBtn.onclick = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
    mediaRecorder.onstart = () => {
      status.textContent = 'Recording...';
      recordBtn.disabled = true;
      stopBtn.disabled = false;
      playBtn.disabled = true;
      downloadLink.style.display = 'none';
    };
    mediaRecorder.onstop = () => {
      const blob = new Blob(audioChunks, { type: 'audio/webm' });
      const url = URL.createObjectURL(blob);
      audioPlayer.src = url;
      playBtn.disabled = false;
      downloadLink.href = url;
      // default filename
      downloadLink.download = 'recording.webm';
      downloadLink.style.display = 'inline';
      downloadLink.textContent = 'Download (save & upload)';
      status.textContent = 'Recording stopped. Click Download to save the file, then upload it below.';
    };
    mediaRecorder.start();
  } catch (err) {
    status.textContent = 'Microphone access denied or not available. Use the upload fallback below.';
  }
};

stopBtn.onclick = () => {
  if (mediaRecorder && mediaRecorder.state !== 'inactive') {
    mediaRecorder.stop();
  }
  recordBtn.disabled = false;
  stopBtn.disabled = true;
};

playBtn.onclick = () => {
  if (audioPlayer.src) {
    audioPlayer.play();
  }
};
</script>
"""

# Render HTML recorder
st.components.v1.html(RECORDER_HTML, height=220)

st.markdown("---")

# -------------------------
# Upload fallback & transcription
# -------------------------
st.header("Upload recorded file for transcription")
st.write(
    "Upload the file you downloaded from the recorder (or any audio file). "
    "Supported types: wav, mp3, m4a, webm, ogg."
)

uploaded = st.file_uploader("Upload recorded audio (from the Download link above)", type=["wav", "mp3", "m4a", "webm", "ogg"])
if uploaded is not None:
    st.info("File uploaded — processing...")
    try:
        # Read bytes and normalize/convert with pydub (requires ffmpeg)
        in_bytes = uploaded.read()
        audio_seg = AudioSegment.from_file(io.BytesIO(in_bytes))
        # export to wav bytes
        bio = io.BytesIO()
        audio_seg.export(bio, format="wav")
        wav_bytes = bio.getvalue()

        # Play preview in the app
        st.audio(wav_bytes, format="audio/wav")

        # Transcribe using SpeechRecognition
        r = sr.Recognizer()
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        try:
            tmp.write(wav_bytes)
            tmp.flush()
            tmp.close()
            with sr.AudioFile(tmp.name) as source:
                audio_data = r.record(source)
            try:
                transcript = r.recognize_google(audio_data)
            except sr.UnknownValueError:
                transcript = "(Could not understand audio)"
            except sr.RequestError as e:
                transcript = f"(Could not request results; {e})"
        finally:
            try:
                os.unlink(tmp.name)
            except Exception:
                pass

        st.subheader("Transcription result")
        st.write(transcript)

        if st.button("Put transcription into TTS text area"):
            st.session_state["tts_text"] = transcript
            st.success("Transcription placed into the TTS text area.")
            st.experimental_rerun()

    except Exception as e:
        st.error(f"Failed to process uploaded audio: {e}")

st.markdown("---")
st.caption("Dependencies: streamlit, gTTS, pydub, SpeechRecognition. System dependency: ffmpeg (for pydub).")
