"""
Background extraction worker thread.
Processes captured frames: OCR pre-filter -> LM Studio local vision/text -> validation -> deduplication -> CSV.
"""

import time
import queue
from typing import Optional, Dict, Any
from PySide6.QtCore import QThread, Signal
from config import CONFIG
from app.services.ocr_service import OCRService
from app.services.lm_studio_client import LMStudioClient
from app.services.contact_validator import clean_and_validate_record, ContactRecord
from app.services.deduplication import Deduplicator
from app.services.csv_service import CSVService
from app.database.repository import ContactRepository
from app.utils.image_utils import scale_image_for_model
from app.utils.logger import logger

class ExtractionWorker(QThread):
    """Processes captured frames through the intelligence extraction pipeline."""

    record_extracted = Signal(object, bool)   # (ContactRecord, is_duplicate)
    pipeline_progress = Signal(str, float)    # (stage_message, elapsed_ms)
    stats_updated = Signal(dict)              # (metrics dictionary)
    error_occurred = Signal(str)              # (error message)

    def __init__(
        self,
        repo: ContactRepository = None,
        csv_service: CSVService = None,
        parent=None
    ):
        super().__init__(parent)
        self.repo = repo or ContactRepository()
        self.csv_service = csv_service or CSVService(repo=self.repo)
        self.ocr_service = OCRService()
        self.lm_client = LMStudioClient()
        self.deduplicator = Deduplicator()

        # Bounded queue to avoid memory ballooning on 16GB RAM / 2GB VRAM
        self._queue = queue.Queue(maxsize=CONFIG.hardware.max_frame_buffer_size)
        self.is_running = False
        self._is_processing = False

        self.extracted_count = 0
        self.duplicate_count = 0
        self._lm_studio_cooldown_until = 0.0

    def is_busy(self) -> bool:
        """Returns True if worker is currently busy running OCR or model inference."""
        return self._is_processing or (not self._queue.empty())

    def enqueue_frame(self, image, window_info: dict, diff_percent: float) -> bool:
        """Adds a newly captured frame to the processing queue. Drops stale if full."""
        try:
            self._queue.put_nowait((image, window_info, diff_percent))
            return True
        except queue.Full:
            logger.debug("Extraction queue full; dropping stale frame to conserve memory.")
            return False

    def run(self):
        self.is_running = True
        logger.info("ExtractionWorker started.")

        while self.is_running:
            try:
                # Wait up to 1 second for a frame
                item = self._queue.get(timeout=1.0)
            except queue.Empty:
                continue

            image, window_info, diff_percent = item
            start_time = time.time()
            self._is_processing = True

            try:
                self._process_frame(image, window_info)
            except Exception as e:
                logger.error(f"Error processing frame: {e}", exc_info=True)
                self.error_occurred.emit(f"Extraction error: {str(e)}")
            finally:
                self._is_processing = False
                elapsed_ms = (time.time() - start_time) * 1000.0
                self.pipeline_progress.emit("Cycle complete", elapsed_ms)
                self._queue.task_done()

        logger.info("ExtractionWorker stopped.")

    def _persist_and_emit(self, record: ContactRecord) -> bool:
        """Saves validated record to DB and CSV immediately in real-time, emitting UI signals."""
        dedup_hash = self.deduplicator.generate_fingerprint(record)
        is_dup = self.deduplicator.is_duplicate(record) or self.repo.is_hash_exists(dedup_hash)

        if is_dup:
            self.duplicate_count += 1
            logger.info(f"Duplicate record skipped: {record.person_or_profile_name or record.business_email or record.normalized_phone}")
            self.record_extracted.emit(record, True)
            return False
        else:
            self.extracted_count += 1
            self.deduplicator.register(record)

            # 1. Persist to SQLite
            self.repo.insert_contact(record, dedup_hash)

            # 2. Append to CSV with immediate disk fsync
            csv_saved = self.csv_service.append_record(record)
            if not csv_saved:
                logger.warning(f"Record {record.record_id} saved to DB and queued for CSV flush.")

            ident = record.person_or_profile_name or record.business_email or record.normalized_phone or "Contact"
            logger.info(f"⚡ [REAL-TIME] New contact extracted & saved: {ident} ({record.business_email or record.normalized_phone or ''})")
            self.record_extracted.emit(record, False)

            # 3. Emit Updated Metrics
            stats = self.repo.get_summary_stats()
            stats["duplicates_skipped"] = self.duplicate_count
            self.stats_updated.emit(stats)
            return True

    def _process_frame(self, image, window_info: dict):
        """Executes the full extraction pipeline for a single frame."""
        self.pipeline_progress.emit("Running real-time OCR...", 0.0)

        # 1. OCR Text Extraction
        ocr_text = self.ocr_service.extract_text(image)

        # 2. FAST-PATH: Real-time instant multi-contact extraction (<50ms)
        fast_records = self.ocr_service.extract_structured_contacts(ocr_text, window_info)
        if fast_records:
            for rec in fast_records:
                self._persist_and_emit(rec)
            self.pipeline_progress.emit("OCR extraction complete", 0.0)
            # When contacts were identified from screen text, return immediately.
            # This guarantees zero-latency performance and prevents redundant LLM calls on already-extracted contacts.
            return

        # 3. FALLBACK: Only invoke LM Studio if OCR found no contacts, queue has NO pending frames,
        # and LM Studio is not on timeout cooldown (prevents blocking real-time extraction)
        if not ocr_text or len(ocr_text.strip()) < 20:
            return

        if not self._queue.empty():
            # Keep up with continuous real-time scrolling; do not freeze the pipeline
            return

        if time.time() < self._lm_studio_cooldown_until:
            return

        self.pipeline_progress.emit("Analyzing visual layout...", 0.0)

        scaled_img, data_url = scale_image_for_model(
            image,
            max_dimension=CONFIG.hardware.max_screenshot_dimension,
            jpeg_quality=CONFIG.hardware.screenshot_jpeg_quality
        )

        app_name = window_info.get("process_name", "Desktop")
        win_title = window_info.get("title", "")
        context_str = f"Application: {app_name} | Window: {win_title}"

        # 4. Optional LM Studio inference
        success, raw_data, msg = self.lm_client.extract_contact_info(
            ocr_text=ocr_text,
            image_data_url=data_url if CONFIG.lm_studio.enable_vision else None,
            app_context=context_str
        )

        if not success and ("timed out" in msg.lower() or "connection refused" in msg.lower()):
            # Brief 30-second cooldown so transient timeouts don't block real-time extraction
            self._lm_studio_cooldown_until = time.time() + 30.0
            logger.info("LM Studio offline or timed out; pausing model calls for 30 seconds.")

        if success and raw_data:
            records_to_process = raw_data if isinstance(raw_data, list) else [raw_data]
            for item in records_to_process:
                if not isinstance(item, dict):
                    continue
                item["source_application"] = app_name
                item["source_url"] = item.get("website_url") or item.get("social_profile_url") or window_info.get("url") or win_title
                record = clean_and_validate_record(item)
                if record:
                    self._persist_and_emit(record)

    def stop(self):
        """Signals worker to terminate."""
        self.is_running = False
