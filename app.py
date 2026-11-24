import streamlit as st
import requests
import time
import os
import re

API_HOST = "http://localhost:8000"
API_BASE_URL = f"{API_HOST}/api/v1"

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
    metadata = data.get("metadata", {})
    
    # 다운로드 파일명 정규화: 한글(가-힣) 허용 및 빈 문자열 Fallback 방어
    raw_filename = os.path.splitext(st.session_state.original_filename)[0]
    safe_filename = re.sub(r'[^a-zA-Z0-9가-힣]', '_', raw_filename)
    safe_filename = re.sub(r'_+', '_', safe_filename).strip('_')
    
    if not safe_filename:
        safe_filename = "bass_track"
    
    st.divider()
    st.subheader("✅ 분석 완료")
    
    col1, col2 = st.columns(2)
    
    # 백엔드 응답 DTO의 metadata URL을 SSOT로 직접 참조 (샌드박스 경로 정합성 보장)
    bass_rel_url = metadata.get("bass_audio_url", f"/api/v1/downloads/{task_id}/bass.wav")
    bassless_rel_url = metadata.get("bassless_audio_url", f"/api/v1/downloads/{task_id}/bassless_backing.wav")
    midi_rel_url = metadata.get("midi_url")
    
    bass_audio_url = f"{API_HOST}{bass_rel_url}"
    bassless_audio_url = f"{API_HOST}{bassless_rel_url}"
    
    with col1:
        st.markdown("#### 🎧 추출된 베이스 트랙")
        st.audio(bass_audio_url, format="audio/wav")
        
    with col2:
        st.markdown("#### 🔇 베이스 제외 MR (Backing Track)")
        st.audio(bassless_audio_url, format="audio/wav")

    st.markdown(f"**BPM:** {data.get('bpm', 'N/A')}")
    
    st.markdown("#### 📄 타브 악보 (ASCII Tab)")
    st.code(data.get("ascii_tab", "악보 데이터가 없습니다."), language="text")
    
    st.markdown("#### 💾 다운로드")
    if midi_rel_url:
        midi_url = f"{API_HOST}{midi_rel_url}"
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
    else:
        st.info("감지된 베이스 노트가 없어 생성된 MIDI 파일이 없습니다.")
