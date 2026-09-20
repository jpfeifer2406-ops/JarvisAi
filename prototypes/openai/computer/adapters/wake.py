"""Reuses the documented Computer model identity, never the old mic loop."""

import hashlib
import json
import os
from pathlib import Path
import numpy as np


class ComputerWake:
    def __init__(self):
        from openwakeword.model import Model

        profile = json.loads((Path(__file__).parents[1] / "profiles/voice.json").read_text())
        path = Path(os.environ["COMPUTER_WAKE_MODEL"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != profile["wake_sha256"]:
            raise ValueError("Wake-Modell-Prüfsumme stimmt nicht.")
        self.model = Model(wakeword_models=[str(path)], inference_framework="onnx")
        self.buffer = bytearray()
        self.hits = 0

    def detect(self, pcm):
        self.buffer.extend(pcm)
        fired = False
        while len(self.buffer) >= 2560:
            block = bytes(self.buffer[:2560])
            del self.buffer[:2560]
            scores = self.model.predict(np.frombuffer(block, dtype=np.int16))
            score = max((float(x) for x in scores.values()), default=0)
            self.hits = self.hits + 1 if score >= 0.72 else 0
            if self.hits >= 2:
                self.hits = 0
                self.model.reset()
                fired = True
        return fired
