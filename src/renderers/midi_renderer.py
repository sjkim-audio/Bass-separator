import mido
from typing import List
from src.models.events import NoteEvent # Pydantic DTO

class MidiRenderer:
    """
    [Core Logic] 추출된 NoteEvent 배열을 기반으로 표준 MIDI(.mid) 파일을 생성합니다.
    """
    @staticmethod
    def render_midi(events: List[any], bpm: float, output_path: str = "outputs/tab.mid") -> str:
        if not events:
            raise ValueError("MIDI로 변환할 노트 이벤트가 없습니다.")

        # 1. MIDI 파일 및 트랙 초기화
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)

        # 2. 메타데이터 (BPM 설정)
        # mido는 마이크로초 단위의 tempo를 사용하므로 변환 (60,000,000 / BPM)
        tempo = mido.bpm2tempo(bpm)
        track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
        track.append(mido.MetaMessage('track_name', name='Bass Transcription', time=0))

        # 3. 노트 이벤트 시간순 정렬 및 Duration 보정
        # JSON 데이터 상단에 duration이 0.0인 결함을 방어하기 위한 Heuristic 처리
        sorted_events = sorted(events, key=lambda e: e.time)
        
        # 4. 절대 시간(sec) -> 델타 타임(ticks) 변환 로직
        # MIDI는 이전 이벤트로부터 '얼마나 지난 후'에 실행할지를 나타내는 상대 시간(Delta Time)을 사용함.
        ticks_per_beat = mid.ticks_per_beat
        ticks_per_second = (bpm / 60.0) * ticks_per_beat
        
        # note_on과 note_off 이벤트를 시간순으로 하나의 배열로 병합
        midi_events = []
        for i, event in enumerate(sorted_events):
            # duration이 0이거나 없는 경우, 다음 노트 시작점까지로 계산 (최대 2초 제한)
            duration = getattr(event, 'duration', 0.0)
            if duration <= 0.0:
                if i < len(sorted_events) - 1:
                    duration = min(sorted_events[i+1].time - event.time, 2.0)
                else:
                    duration = 0.5 # 마지막 노트는 0.5초 고정

            # 절대 시간 기록
            on_time = event.time
            off_time = event.time + duration
            
            # 베이스 기타임을 명시하기 위해 채널 0, 적절한 Velocity 부여 (Confidence 반영 가능)
            velocity = int(64 + (getattr(event, 'confidence', 1.0) * 63)) # 64 ~ 127 사이
            
            midi_events.append({'type': 'note_on', 'time': on_time, 'note': event.midi_note, 'velocity': velocity})
            midi_events.append({'type': 'note_off', 'time': off_time, 'note': event.midi_note, 'velocity': 0})

        # 다시 절대 시간 기준으로 정렬
        midi_events.sort(key=lambda x: x['time'])

        # 5. Delta Time 계산 및 트랙 기록
        last_time_sec = 0.0
        for ev in midi_events:
            delta_sec = ev['time'] - last_time_sec
            delta_ticks = int(round(delta_sec * ticks_per_second))
            
            if ev['type'] == 'note_on':
                track.append(mido.Message('note_on', note=ev['note'], velocity=ev['velocity'], time=delta_ticks))
            else:
                track.append(mido.Message('note_off', note=ev['note'], velocity=ev['velocity'], time=delta_ticks))
            
            last_time_sec = ev['time']

        # 6. 디스크 저장
        mid.save(output_path)
        print(f"✔ [MIDI 렌더러] MIDI 파일 추출 완료: {output_path}")
        return output_path