"""
VivekAI_App - Transcript Manager
Auto-saves all sessions to local files (TXT + JSON)
"""

import os
import json
import threading
import time
from datetime import datetime
import config

class TranscriptManager:
    def __init__(self):
        self.session_data = {
            "session": {},
            "transcript": []
        }
        self.session_start = None
        self.mode = "General"
        self.engine = "Groq"
        self.save_lock = threading.Lock()
        self.auto_save_timer = None
        self._ensure_dir()

    def _ensure_dir(self):
        os.makedirs(config.TRANSCRIPT_DIR, exist_ok=True)

    def start_session(self, mode, engine):
        self.session_start = datetime.now()
        self.mode = mode
        self.engine = engine
        self.session_data = {
            "session": {
                "mode": mode,
                "engine": engine,
                "date": self.session_start.strftime("%Y-%m-%d"),
                "start_time": self.session_start.strftime("%H:%M:%S"),
                "end_time": "",
                "duration_seconds": 0
            },
            "transcript": []
        }
        self._start_auto_save()

    def add_entry(self, heard_text, ai_response):
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = {
            "timestamp": timestamp,
            "heard": heard_text,
            "response": ai_response
        }
        with self.save_lock:
            self.session_data["transcript"].append(entry)

    def _start_auto_save(self):
        """Auto-save every 30 seconds"""
        self._save_files()
        self.auto_save_timer = threading.Timer(
            config.AUTO_SAVE_INTERVAL, self._start_auto_save
        )
        self.auto_save_timer.daemon = True
        self.auto_save_timer.start()

    def stop_session(self):
        if self.auto_save_timer:
            self.auto_save_timer.cancel()
        if self.session_start:
            end_time = datetime.now()
            duration = int((end_time - self.session_start).total_seconds())
            self.session_data["session"]["end_time"] = end_time.strftime("%H:%M:%S")
            self.session_data["session"]["duration_seconds"] = duration
        self._save_files()

    def _get_filename_base(self):
        date_str = self.session_start.strftime("%Y-%m-%d") if self.session_start else datetime.now().strftime("%Y-%m-%d")
        time_str = self.session_start.strftime("%H%M") if self.session_start else datetime.now().strftime("%H%M")
        return os.path.join(config.TRANSCRIPT_DIR, f"{date_str}_{self.mode}_{time_str}")

    def _save_files(self):
        with self.save_lock:
            self._save_txt()
            self._save_json()

    def _save_txt(self):
        try:
            base = self._get_filename_base()
            path = base + ".txt"
            s = self.session_data["session"]
            lines = [
                "=" * 55,
                f"  VIVEK AI - SESSION TRANSCRIPT",
                "=" * 55,
                f"  Mode    : {s.get('mode', '')}",
                f"  Engine  : {s.get('engine', '')}",
                f"  Date    : {s.get('date', '')}",
                f"  Started : {s.get('start_time', '')}",
                "=" * 55,
                ""
            ]
            for entry in self.session_data["transcript"]:
                lines.append(f"[{entry['timestamp']}] 🎙️  {entry['heard']}")
                lines.append(f"[{entry['timestamp']}] 🤖  {entry['response']}")
                lines.append("")

            if s.get("end_time"):
                dur = s.get("duration_seconds", 0)
                mins, secs = divmod(dur, 60)
                lines += [
                    "=" * 55,
                    f"  SESSION END : {s['end_time']}  |  Duration: {mins}m {secs}s",
                    "=" * 55
                ]

            with open(path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
        except Exception as e:
            print(f"TXT save error: {e}")

    def _save_json(self):
        try:
            base = self._get_filename_base()
            path = base + ".json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.session_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"JSON save error: {e}")

    def get_transcript_dir(self):
        return config.TRANSCRIPT_DIR

    def get_entry_count(self):
        return len(self.session_data["transcript"])
