import json, queue, sys, time
import sounddevice as sd
from vosk import Model, KaldiRecognizer

MODEL_PATH = "H:\\ollama-models\\vosk-model-small-ru-0.22"
DEVICE = 1
RATE = 16000

q = queue.Queue()
def cb(indata, frames, time_info, status):
    if status:
        print("status:", status, file=sys.stderr)
    q.put(bytes(indata))

print("recording 6s...")
model = Model(MODEL_PATH)
rec = KaldiRecognizer(model, RATE)

with sd.RawInputStream(samplerate=RATE, blocksize=8000, device=DEVICE, dtype="int16", channels=1, callback=cb):
    t0 = time.time()
    while time.time() - t0 < 6:
        data = q.get()
        if rec.AcceptWaveform(data):
            print("partial:", json.loads(rec.Result()).get("text"))

print("final:", json.loads(rec.FinalResult()).get("text"))
