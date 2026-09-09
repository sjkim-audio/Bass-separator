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
        tempo = mido.bpm2tempo(bpm)
        track.append(mido.MetaMessage('set_tempo', tempo=tempo, time=0))
        track.append(mido.MetaMessage('track_name', name='Bass Transcription', time=0))

        # 3. 노트 이벤트 시간순 정렬 및 Duration 보정
        sorted_events = sorted(events, key=lambda e: e.time)
        
        # 4. 절대 시간(sec) -> 델타 타임(ticks) 변환 로직
        ticks_per_beat = mid.ticks_per_beat
        ticks_per_second = (bpm / 60.0) * ticks_per_beat
        
        midi_events = []
        for i, event in enumerate(sorted_events):
            duration = getattr(event, 'duration', 0.0)
            if duration <= 0.05: 
                duration = 0.05 

            on_time = event.time
            off_time = event.time + duration
            
            # 🔴 [핵심 수정] 단선율(Monophonic) 오버랩 커팅 로직 교정
            if i < len(sorted_events) - 1:
                next_on_time = sorted_events[i+1].time
                if off_time > next_on_time:
                    # 임의의 값을 빼지 않고, 다음 노트의 시작점과 정확히 일치시킴 (Legato)
                    off_time = next_on_time
            
            # 파이프라인 업스트림 버그로 인해 시작과 끝이 같거나 역전된 기형적 노트는 렌더링 무시
            if off_time <= on_time:
                continue

            velocity = int(64 + (getattr(event, 'confidence', 1.0) * 63))
            
            midi_events.append({'type': 'note_on', 'time': on_time, 'note': event.midi_note, 'velocity': velocity})
            midi_events.append({'type': 'note_off', 'time': off_time, 'note': event.midi_note, 'velocity': 0})

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
