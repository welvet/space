import asyncio
import json
from datetime import datetime
from pathlib import Path
from statistics import median

from backend import Automation

READER = "NFC_READER_582ABDD8ED94"
RECORDING = Path(__file__).with_name("nfc-consistency.jsonl")
SPEEDS = (50, 60, 100, 80, 90)


class Script(Automation):
    async def start(self):
        self._run = datetime.now().astimezone().isoformat()
        self._speed = 0
        self._record("start")
        self._devices.on_detection(self._record_detection)
        while not self._train.info()["arctic_express"]["connected"]:
            await asyncio.sleep(1)
        try:
            for speed in SPEEDS:
                await self.setSpeed("arctic_express", speed)
                self._speed = speed
                self._record("speed")
                self.event(f"Arctic Express: speed {speed} for 1 minute")
                await asyncio.sleep(60)
        finally:
            await self.setSpeed("arctic_express", 0)
            self._record("stop")
            self._speed = 0
        self._analyse()

    def _record(self, kind, **details):
        row = {
            "timestamp": datetime.now().astimezone().isoformat(),
            "run": self._run,
            "kind": kind,
            "speed": self._speed,
            **details,
        }
        with RECORDING.open("a") as recording:
            recording.write(json.dumps(row) + "\n")

    def _record_detection(self, device, tag, detected):
        if device == READER and detected and self._speed:
            self._record("detected", device=device, tag=tag)

    def _analyse(self):
        with RECORDING.open() as recording:
            rows = [json.loads(line) for line in recording]
        rows = [row for row in rows if row["run"] == self._run]
        tags = sorted({row["tag"] for row in rows if row["kind"] == "detected" and self._normalize(row["tag"]).strip("0")})
        for speed in SPEEDS:
            phase = next(row for row in rows if row["kind"] == "speed" and row["speed"] == speed)
            end = next(row for row in rows if row["kind"] in ("speed", "stop") and row["timestamp"] > phase["timestamp"])
            for tag in tags or [None]:
                timestamps = [
                    datetime.fromisoformat(row["timestamp"])
                    for row in rows
                    if row["kind"] == "detected" and row["speed"] == speed and row["tag"] == tag
                ]
                gaps = [(right - left).total_seconds() for left, right in zip(timestamps, timestamps[1:])]
                typical = median(gaps) if gaps else None
                first_delay = (timestamps[0] - datetime.fromisoformat(phase["timestamp"])).total_seconds() if timestamps else None
                last_delay = (datetime.fromisoformat(end["timestamp"]) - timestamps[-1]).total_seconds() if timestamps else None
                suspects = [
                    {"after": left.isoformat(), "before": right.isoformat(), "seconds": gap}
                    for left, right, gap in zip(timestamps, timestamps[1:], gaps)
                    if typical and gap > typical * 1.5
                ]
                if typical:
                    for after, before, gap in (
                        (phase["timestamp"], timestamps[0].isoformat(), first_delay),
                        (timestamps[-1].isoformat(), end["timestamp"], last_delay),
                    ):
                        if gap > typical * 1.5:
                            suspects.append({"after": after, "before": before, "seconds": gap, "boundary": True})
                status = "no detections" if not timestamps else "insufficient detections" if len(gaps) < 3 else "suspected misses" if suspects else "no long gaps observed"
                self._record(
                    "analysis", analysis_version=2, speed=speed, tag=tag, detections=len(timestamps),
                    invalid_uid_detections=sum(row["kind"] == "detected" and row["speed"] == speed and not self._normalize(row["tag"]).strip("0") for row in rows),
                    phase_start=phase["timestamp"], phase_end=end["timestamp"],
                    median_interval_seconds=typical, suspected_gaps=suspects,
                    first_detection_delay_seconds=first_delay,
                    last_detection_to_end_seconds=last_delay,
                    status=status,
                )
                self.event(f"NFC speed {speed}, tag {tag}: {status}; {len(timestamps)} detections, {len(suspects)} suspected gaps; median interval {typical}")
