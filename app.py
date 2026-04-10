import streamlit as st
import requests
import time
import os
import re

API_BASE_URL = "http://localhost:8000/api/v1"

st.set_page_config(page_title="AI Bass Transcription", page_icon="🎸", layout="wide")
st.title("🎸 AI Bass Separator & Transcription")
st.markdown("오디오 파일을 업로드하면 베이스 트랙을 분리하고 타브 악보 및 MIDI를 추출합니다.")

if "task_id" not in st.session_state:
    st.session_state.task_id = None
if "result_data" not in st.session_state:
    st.session_state.result_data = None
if "original_filename" not in st.session_state:
    st.session_state.original_filename = None

uploaded_file = st.file_uploader("오디오 파일 선택 (.wav, .mp3)", type=["wav", "mp3"])

if uploaded_file is not None:
    if st.button("🚀 분석 시작"):
        st.session_state.result_data = None
        st.session_state.original_filename = uploaded_file.name
        
        with st.spinner("서버로 파일을 전송 중입니다..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "audio/wav")}
                response = requests.post(f"{API_BASE_URL}/transcribe", files=files)
                
                if response.status_code in [200, 202]:
                    data = response.json()
                    st.session_state.task_id = data.get("task_id")
                    st.success(f"업로드 성공! 작업 ID: {st.session_state.task_id}")
                else:
                    st.error(f"업로드 실패: {response.status_code} - {response.text}")
                    st.stop()
            except Exception as e:
                st.error(f"서버 연결 에러: {repr(e)}")
                st.stop()

# 비동기 폴링 
if st.session_state.task_id and not st.session_state.result_data:
    with st.spinner("AI 모델 추론 및 타브 악보 추출 중..."):
        task_id = st.session_state.task_id
        
        for _ in range(300): # 최대 10분 대기로 연장
            try:
                poll_res = requests.get(f"{API_BASE_URL}/tasks/{task_id}")
                if poll_res.status_code == 200:
                    poll_data = poll_res.json()
                    status = poll_data.get("status")
                    
                    if status == "SUCCESS":
                        st.session_state.result_data = poll_data
                        st.rerun() 
                    elif status == "FAILED":
                        st.error(f"파이프라인 연산 실패: {poll_data.get('error')}")
                        st.session_state.task_id = None
                        st.stop()
            except requests.exceptions.RequestException:
                pass 
            
            time.sleep(2)
            
        st.error("요청 시간 초과(Timeout). 서버가 응답하지 않습니다.")

# 결과 시각화
if st.session_state.result_data:
    data = st.session_state.result_data
    task_id = st.session_state.task_id
    
    # [Fix 1] 다운로드 파일명 정규화: 한글(가-힣) 허용 및 빈 문자열 Fallback 방어
    raw_filename = os.path.splitext(st.session_state.original_filename)[0]
    safe_filename = re.sub(r'[^a-zA-Z0-9가-힣]', '_', raw_filename)
    safe_filename = re.sub(r'_+', '_', safe_filename).strip('_')
    
    # 특수문자로만 이루어진 파일명이라 모두 치환되어 빈 문자열이 된 경우
    if not safe_filename:
        safe_filename = "bass_track"
    
    st.divider()
    st.subheader("✅ 분석 완료")
    
    col1, col2 = st.columns(2)
    
    # [Fix 2] 오디오 서빙 URL 인코딩 (한글 및 공백 파일명 파싱 에러 방어)
    import urllib.parse
    encoded_folder_name = urllib.parse.quote(f"{task_id}_{raw_filename}")
    demucs_base_url = f"{API_BASE_URL}/downloads/demucs/htdemucs/{encoded_folder_name}"
    midi_url = f"{API_BASE_URL}/downloads/{task_id}.mid"
    
    with col1:
        st.markdown("#### 🎧 추출된 베이스 트랙")
        bass_audio_url = f"{demucs_base_url}/bass.wav"
        st.audio(bass_audio_url, format="audio/wav")
        # URL 인코딩을 적용했으므로 파일명 변경 요구 경고문은 제거하거나 완화해도 좋습니다.
        
    with col2:
        st.markdown("#### 🔇 베이스 제외 MR (Backing Track)")
        bassless_audio_url = f"{demucs_base_url}/bassless_backing.wav"
        st.audio(bassless_audio_url, format="audio/wav")

    st.markdown(f"**BPM:** {data.get('bpm', 'N/A')}")
    
    st.markdown("#### 📄 타브 악보 (ASCII Tab)")
    st.code(data.get("ascii_tab", "악보 데이터가 없습니다."), language="text")
    
    st.markdown("#### 💾 다운로드")
    try:
        midi_response = requests.get(midi_url)
        if midi_response.status_code == 200:
            st.download_button(
                label="🎵 MIDI 파일 다운로드 (.mid)",
                data=midi_response.content,
                file_name=f"{safe_filename}_bass.mid",
                mime="audio/midi"
            )
        else:
            st.warning("MIDI 파일을 서버에서 찾을 수 없습니다.")
    except Exception:
         st.warning("MIDI 다운로드 링크 생성 중 오류가 발생했습니다.")
