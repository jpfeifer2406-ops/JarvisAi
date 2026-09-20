"""Fixed inference entrypoints. Warm model cache; killable, NOT a code sandbox."""
import contextlib
import json
import os
import sys
from pathlib import Path

_MODELS = {}
_PROMPTS = {}


def infer(mode, payload, output):
    if mode == "stt":
        from faster_whisper import WhisperModel
        key = ("stt", payload["model"])
        if key not in _MODELS:
            _MODELS[key] = WhisperModel(payload["model"], device="cpu", compute_type="int8",
                cpu_threads=int(os.environ.get("COMPUTER_CPU_THREADS", "2")), num_workers=1,
                local_files_only=True)
        segments, _ = _MODELS[key].transcribe(payload["input"], language="de", beam_size=1,
                                             vad_filter=True, condition_on_previous_text=False)
        Path(output).write_text(json.dumps({"text": " ".join(s.text for s in segments)}))
    elif mode == "tts":
        import numpy as np
        import soundfile as sf
        import torch
        from qwen_tts import Qwen3TTSModel
        key = ("tts", payload["model"], payload["device"])
        if key not in _MODELS:
            torch.set_num_threads(int(os.environ.get("COMPUTER_CPU_THREADS", "2")))
            _MODELS[key] = Qwen3TTSModel.from_pretrained(payload["model"],device_map=payload["device"],
                dtype=torch.float32 if payload["device"] == "cpu" else torch.bfloat16,
                local_files_only=True, attn_implementation="eager")
        model = _MODELS[key]
        p = payload["profile"]
        with torch.inference_mode():
            if payload.get("reference"):
                reference=Path(payload["reference"])
                prompt_key=(key,str(reference.resolve()),reference.stat().st_mtime_ns)
                if prompt_key not in _PROMPTS:
                    _PROMPTS.clear()
                    _PROMPTS[prompt_key]=model.create_voice_clone_prompt(
                        ref_audio=str(reference),ref_text=p["reference_text"],x_vector_only_mode=False)
                wavs,sr=model.generate_voice_clone(text=payload["text"],language=p["language"],
                    voice_clone_prompt=_PROMPTS[prompt_key])
            else:
                wavs,sr=model.generate_voice_design(text=payload["text"],language=p["language"],
                                                   instruct=p["description"])
        audio=np.asarray(wavs[0],dtype=np.float32).reshape(-1)
        if not len(audio) or not np.isfinite(audio).all():
            raise ValueError("Ungültiges Audio")
        sf.write(output,np.clip(audio,-1,1),sr,subtype="PCM_16")
    else:
        raise ValueError("Unknown worker mode")


def main():
    if sys.argv[1:] == ["serve"]:
        # Protocol output is separate from dependency prints; no audio/text logged.
        protocol=sys.stdout
        for line in sys.stdin:
            try:
                request=json.loads(line)
                with contextlib.redirect_stdout(sys.stderr):
                    infer(request["mode"],request["payload"],request["output"])
                result={"ok":True}
            except Exception:
                result={"ok":False}
            protocol.write(json.dumps(result)+"\n")
            protocol.flush()
    else:
        mode,output=sys.argv[1:]
        infer(mode,json.load(sys.stdin),output)


if __name__ == "__main__":main()
