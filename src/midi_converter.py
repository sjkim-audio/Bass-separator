!pip install pretty_midi

# based for Bass

import pretty_midi

def save_as_midi(events, output_path, tempo=120):
    """
    events: [{'time': 1.2, 'pitch': 45, 'duration': 0.5}, ...] 형태의 리스트
    """
    # 1. MIDI 객체 생성 (Bass 악기 설정)
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    instrument = pretty_midi.Instrument(program=33) # 33: Electric Bass (Finger)
    
    # 2. 노트 추가
    for event in events:
        # duration이 너무 짧으면(노이즈) 최소 길이 보장
        duration = max(event.get('duration', 0.1), 0.1) 
        note = pretty_midi.Note(
            velocity=100,       # 타건 강도 (기본값)
            pitch=int(event['pitch']),
            start=event['time'],
            end=event['time'] + duration
        )
        instrument.notes.append(note)

    # 3. 악기 추가 및 저장
    midi.instruments.append(instrument)
    midi.write(output_path)
    print(f"💾 MIDI 파일 저장 완료: {output_path}")
