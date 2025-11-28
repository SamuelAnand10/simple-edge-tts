# app.py
import base64
import streamlit as st
import asyncio
import tempfile
import threading
import os
import traceback
from edge_tts import Communicate
from edge_tts.communicate import NoAudioReceived

st.set_page_config(page_title="Edge TTS — Autoplay Mode", layout="centered")

# -------------------------
# Background asyncio loop
# -------------------------
_bg_loop = None
_bg_thread = None

def _ensure_bg_loop():
    global _bg_loop, _bg_thread
    if _bg_loop is None:
        _bg_loop = asyncio.new_event_loop()
        def _loop_runner(loop):
            asyncio.set_event_loop(loop)
            loop.run_forever()
        _bg_thread = threading.Thread(target=_loop_runner, args=(_bg_loop,), daemon=True)
        _bg_thread.start()

def _run_in_bg(coro, timeout=60):
    """
    Schedule coroutine on background event loop and return result (or raise).
    """
    _ensure_bg_loop()
    future = asyncio.run_coroutine_threadsafe(coro, _bg_loop)
    return future.result(timeout=timeout)

# -------------------------
# Edge-TTS helpers
# -------------------------
async def _synthesize_to_file_async(text_or_ssml: str, voice: str, out_path: str):
    communicator = Communicate(text_or_ssml, voice)
    await communicator.save(out_path)

def synthesize_to_file(text_or_ssml: str, voice="en-US-AriaNeural", timeout=60):
    """
    Synchronous wrapper that schedules async synth on the background loop.
    Returns path to saved mp3 or raises exceptions from edge-tts.
    """
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    tmp_path = tmp.name
    tmp.close()
    try:
        _run_in_bg(_synthesize_to_file_async(text_or_ssml, voice, tmp_path), timeout=timeout)
        # verify file exists and non-empty
        if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) == 0:
            raise RuntimeError("Synthesis completed but output file is missing or empty.")
        return tmp_path
    except Exception:
        # cleanup on failure
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        raise

def autoplay_html(mp3_path: str, autoplay=True):
    """
    Embed mp3 as base64 and render an HTML audio tag.
    """
    with open(mp3_path, "rb") as f:
        mp3_bytes = f.read()
    b64 = base64.b64encode(mp3_bytes).decode("ascii")
    html = f"""
    <audio {'autoplay' if autoplay else ''} controls>
      <source src="data:audio/mpeg;base64,{b64}" type="audio/mpeg">
      Your browser does not support the audio element.
    </audio>
    """
    st.markdown(html, unsafe_allow_html=True)

# -------------------------
# Streamlit UI
# -------------------------
st.title("Edge TTS — Autoplay Mode")

voice = st.selectbox("Voice", ["en-US-AriaNeural", "en-GB-LibbyNeural", "en-US-GuyNeural"])
text = st.text_area("Text", "Hi there, I'm your personal assistant.")

if st.button("Speak", key="speak_btn_v1"):
    if not text.strip():
        st.warning("Please enter text to synthesize.")
    else:
        st.info("Synthesizing... please wait.")
        try:
            mp3_path = synthesize_to_file(text, voice, timeout=60)
            autoplay_html(mp3_path, autoplay=True)
            st.success("Done! Audio should autoplay (if browser allows autoplay).")
            # optional: remove mp3 file if you don't want to keep it
            # os.remove(mp3_path)
        except NoAudioReceived:
            st.error(
                "No audio received from Edge-TTS. Possible causes:\n"
                "- invalid voice name\n- malformed SSML\n- service blocked or network issue\n\nTry a different voice (e.g. short plain text) or check your deployer's outbound networking."
            )
        except Exception as e:
            st.error(f"Synthesis failed: {e}")
            st.code(traceback.format_exc(), language="text")


if st.button("Speak"):
    mp3_path = synthesize_to_file(text, voice)
    autoplay_html(mp3_path)
    st.success("Done! Audio should autoplay 🎧🔥")
