import os
import time
import shutil
import asyncio
from pathlib import Path
from dotenv import load_dotenv
from celery import Celery

# 윈도우 및 리눅스 환경의 OpenMP 라이브러리 중복 로드 충돌 방지
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# 로컬 .env 환경변수 자동 로드
load_dotenv(override=False)

# DB 의존성 및 ORM 모델 임포트
from app.database.core import engine, AsyncSessionLocal
from app.database.models import TranscriptionTask, TaskStatus

# 내부 모듈 및 렌더러 임포트
from app.schemas.response import (
    TranscriptionResponse,
    TranscriptionMetadata,
    BassNoteEvent,
)
from src.renderers.midi_renderer import MidiRenderer
from src.core.demucs_runner import separate_and_generate_stems
from src.core.pipeline import run_transcription_pipeline

# 로컬 네이티브(localhost) 및 Docker(redis) 환경 이원화 지원
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
RESULT_DIR = "outputs"

os.makedirs(RESULT_DIR, exist_ok=True)

celery_app = Celery(
    "bass_transcription_worker",
    broker=CELERY_BROKER_URL,
)

celery_app.conf.update(
    # 직렬화 보안 및 규격 통일
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # 상태 및 메타데이터 영속성은 PostgreSQL(SSOT)이 전담하므로 Redis 결과 저장 비활성화
    task_ignore_result=True,
    # 단일 GPU 워커 보호: 한 번에 1개의 태스크만 가져오며, 작업 완료 후 ACK 전송
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    broker_connection_retry_on_startup=True,
)


def cleanup_files(*file_paths: str) -> None:
    """임시 업로드 파일 삭제"""
    for path in file_paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            print(f"⚠️ [Celery Worker] 임시 파일 삭제 실패: {path} - {e}")


@celery_app.task(name="worker.ping")
def ping_worker() -> str:
    """브로커-워커 간 연결 무결성 검증을 위한 헬스체크 태스크"""
    print("⚡ [Celery Worker] Ping 수신 완료 - 워커가 정상 대기 중입니다.")
    return "pong"


@celery_app.task(name="worker.cleanup_sandbox")
def cleanup_sandbox_task(task_dir_str: str) -> None:
    """
    [ADR-016 Queue-Aware TTL]
    추론 완료 시점으로부터 지정된 지연 시간(countdown) 경과 후 태스크 샌드박스를 삭제합니다.
    """
    task_dir = Path(task_dir_str)
    if task_dir.exists():
        shutil.rmtree(task_dir, ignore_errors=True)
        print(f"🧹 [TTL 클린업] 스토리지 최적화: 만료된 태스크 삭제 완료 ({task_dir})")


async def _run_pipeline_async(task_id: str, temp_file_path: str) -> None:
    """
    비동기 DB 트랜잭션(Short-lived Session)과 코어 추론 파이프라인을 수행하는 내부 코루틴.
    워커가 --pool=solo로 구동되므로 별도의 인메모리 Semaphore 없이 단일 GPU 직렬화가 보장됩니다.
    """
    task_out_dir = Path(RESULT_DIR) / task_id
    task_out_dir.mkdir(parents=True, exist_ok=True)

    bass_path = None
    bassless_path = None

    # [DB Update 1] 상태: PROCESSING (단명 세션: 커밋 후 즉시 커넥션 반환)
    async with AsyncSessionLocal() as db:
        task = await db.get(TranscriptionTask, task_id)
        if task:
            task.status = TaskStatus.PROCESSING
            await db.commit()

    try:
        # 1. 4-Stem 분리 및 MR 병합 로직 호출
        raw_bass_path, raw_bassless_path = await separate_and_generate_stems(
            temp_file_path,
            output_dir=str(task_out_dir),
        )

        # [Cleanup & Isolation] 핵심 파일만 샌드박스 루트로 이동
        new_bass_path = task_out_dir / "bass.wav"
        new_bassless_path = task_out_dir / "bassless_backing.wav"

        shutil.move(str(raw_bass_path), str(new_bass_path))
        if raw_bassless_path and os.path.exists(raw_bassless_path):
            shutil.move(str(raw_bassless_path), str(new_bassless_path))
            bassless_path = str(new_bassless_path)

        bass_path = str(new_bass_path)

        htdemucs_dir = task_out_dir / "htdemucs"
        if htdemucs_dir.exists():
            shutil.rmtree(htdemucs_dir, ignore_errors=True)

        loop = asyncio.get_running_loop()
        start_time_perf = time.perf_counter()

        # 2. 추출된 베이스 및 MR 경로를 채보 파이프라인으로 전달 (DB 무관)
        ascii_tab, bpm, fingered_events, quantized_events = await loop.run_in_executor(
            None, run_transcription_pipeline, bass_path, bassless_path
        )

        # 3. 빈 노트 예외 처리 방어 로직 (MIDI 렌더링 우회)
        midi_filename = f"{task_id}.mid"
        midi_output_path = task_out_dir / midi_filename
        midi_url = None

        if fingered_events:
            MidiRenderer.render_midi(fingered_events, bpm, str(midi_output_path))
            midi_url = f"/api/v1/downloads/{task_id}/{midi_filename}"
        else:
            print(f"⚠️ [{task_id}] 베이스 노트가 감지되지 않아 MIDI 생성을 건너뜁니다.")
            ascii_tab = "⚠️ 감지된 베이스 노트가 없습니다."

        note_dtos = [
            BassNoteEvent(
                start_time=e.time,
                duration=max(getattr(e, "duration", 0.05), 0.001),
                midi_note=e.midi_note,
                string_idx=e.string_idx,
                fret=e.fret,
                confidence=getattr(e, "confidence", 1.0),
            )
            for e in quantized_events
        ]

        processing_time_ms = (time.perf_counter() - start_time_perf) * 1000

        response_data = TranscriptionResponse(
            bpm=bpm,
            ascii_tab=ascii_tab,
            metadata=TranscriptionMetadata(
                task_id=task_id,
                processing_time_ms=processing_time_ms,
                bass_audio_url=f"/api/v1/downloads/{task_id}/bass.wav",
                bassless_audio_url=f"/api/v1/downloads/{task_id}/bassless_backing.wav",
                midi_url=midi_url,
            ),
            events=note_dtos,
        )

        # [DB Update 2] 상태: SUCCESS 및 결과 영구 저장
        async with AsyncSessionLocal() as db:
            task = await db.get(TranscriptionTask, task_id)
            if task:
                task.status = TaskStatus.SUCCESS
                task.result_metadata = response_data.model_dump()
                await db.commit()
                print(f"💾 [{task_id}] DB 상태 업데이트 완료: SUCCESS")

    except Exception as e:
        print(f"❌ 파이프라인 에러 [{task_id}]: {repr(e)}")
        # [DB Update 3] 상태: FAILED 및 예외 로그 저장
        async with AsyncSessionLocal() as db:
            task = await db.get(TranscriptionTask, task_id)
            if task:
                task.status = TaskStatus.FAILED
                task.error_log = repr(e)
                await db.commit()

    finally:
        cleanup_files(temp_file_path)
        await engine.dispose()


@celery_app.task(name="worker.run_pipeline_task")
def run_pipeline_celery_task(task_id: str, temp_file_path: str, ttl_sec: int = 3600) -> None:
    """
    FastAPI 라우터가 발행한 작업을 수신하여 비동기 파이프라인을 구동하는 Celery 엔트리포인트.
    """
    task_out_dir = Path(RESULT_DIR) / task_id
    try:
        asyncio.run(_run_pipeline_async(task_id, temp_file_path))
    finally:
        # 추론이 완전히 종료된 시점(finally)부터 카운트다운을 시작하는 Queue-Aware TTL 스케줄링
        cleanup_sandbox_task.apply_async(args=[str(task_out_dir)], countdown=ttl_sec)
