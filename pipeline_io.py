import json
import sys
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path


def _run_id():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


class _Tee:
    def __init__(self, stream, file_handle):
        self.stream = stream
        self.file_handle = file_handle
        self.encoding = getattr(stream, "encoding", "utf-8")

    def write(self, data):
        self.stream.write(data)
        self.file_handle.write(data)
        self.file_handle.flush()

    def flush(self):
        self.stream.flush()
        self.file_handle.flush()

    def isatty(self):
        return getattr(self.stream, "isatty", lambda: False)()

    def fileno(self):
        return self.stream.fileno()


@contextmanager
def capture_stage(stage_dir, stage):
    stage_dir = Path(stage_dir)
    logs_dir = stage_dir / "logs"
    outputs_dir = stage_dir / "outputs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)

    run_id = _run_id()
    log_path = logs_dir / f"{stage}_{run_id}.log"
    json_path = outputs_dir / f"{stage}_{run_id}.json"
    started_at = datetime.now().isoformat(timespec="seconds")

    log_file = log_path.open("a", encoding="utf-8")
    previous_stdout = sys.stdout
    sys.stdout = _Tee(previous_stdout, log_file)

    print()
    print("=" * 80)
    print(f"{stage.upper()}  |  {started_at}  |  {run_id}")
    print("=" * 80)
    print(f"Log file: {log_path}")

    context = {
        "stage": stage,
        "run_id": run_id,
        "started_at": started_at,
        "log_path": log_path,
        "json_path": json_path,
    }

    try:
        yield context
    finally:
        sys.stdout = previous_stdout
        log_file.close()


def save_stage_result(context, result):
    payload = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "stage": context["stage"],
        "run_id": context["run_id"],
        "started_at": context["started_at"],
        "log_file": str(context["log_path"]),
        "result": result,
    }

    json_path = context["json_path"]
    json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print()
    print("=" * 80)
    print(f"Saved {context['stage']} result: {json_path}")
    print(f"Saved {context['stage']} log:    {context['log_path']}")
    print("=" * 80)

    return json_path
