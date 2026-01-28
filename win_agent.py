import json
import subprocess
import requests
import textwrap
import threading
import time
import socket
import psutil
from datetime import datetime, timedelta, timezone
import re
import os
import queue
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import wave
import html

# =========================
# CONFIG
# =========================
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
#MODEL = "qwen2.5-coder:7b"
MODEL = "llama3.1:8b"

WATCH_INTERVAL_SEC = 777

CPU_WARN_PCT = 85
RAM_WARN_PCT = 85

WATCH_DISKS = ["C:\\", "H:\\"]
DISK_FREE_GB_WARN = 20

WATCH_PORTS = [
    ("Ollama API", "127.0.0.1", 11434),
]

# Доп. мониторинг (переключатели)
ENABLE_INTERNET_CHECK = True
INTERNET_HOST = ("1.1.1.1", 53)
ENABLE_DNS_CHECK = True
DNS_TEST_NAME = "example.com"

ENABLE_TEMPERATURE_CHECK = True
TEMP_WARN_C = 85

ENABLE_SMART_CHECK = True

ENABLE_PROCESS_WATCH = True
WATCH_PROCESSES = ["ollama.exe"]

ENABLE_LOG_DIR_CHECK = True
LOG_DIRS = [
    ("C:\\Windows\\Temp", 5),
    ("C:\\Windows\\Logs", 5),
    ("%LOCALAPPDATA%\\Temp", 5),
]

AUTO_DIAG_TOP_PROCS = True
TOP_N_PROCS = 5

ENABLE_SUGGEST_SOFT_CLEANUP = True

# Погода (Open-Meteo, без API ключа)
ENABLE_WEATHER = True
WEATHER_DEFAULT_LOCATION = ""  # например: "Moscow" или "New York"
WEATHER_LANG = "ru"

# Новости (RSS, без API ключа)
ENABLE_NEWS = True
NEWS_MAX_ITEMS = 50
NEWS_MAX_HOURS = 24
NEWS_OUTPUT_HTML = True
NEWS_HTML_PATH = "news.html"
NEWS_AUTO_OPEN = True
NEWS_FEEDS = {
    "science": [
        "https://nplus1.ru/rss",
        "https://www.popmech.ru/out/public-all.xml",
        "https://elementy.ru/rss/news",
        "https://www.sciencedaily.com/rss/all.xml",
        "https://www.nature.com/subjects/all.rss",
    ],
    "tech": [
        "https://habr.com/ru/rss/all/all/?fl=ru",
        "https://habr.com/ru/rss/hub/develop/all/?fl=ru",
        "https://habr.com/ru/rss/hub/admin/all/?fl=ru",
        "https://vc.ru/rss/tech",
        "https://www.cnews.ru/inc/rss/news.xml",
        "https://techcrunch.com/feed/",
        "https://www.theverge.com/rss/index.xml",
        "https://feeds.arstechnica.com/arstechnica/index/",
        "https://www.wired.com/feed/rss",
    ],
    "ai": [
        "https://export.arxiv.org/rss/cs.AI",
        "https://export.arxiv.org/rss/stat.ML",
        "https://paperswithcode.com/feeds/latest",
        "https://openai.com/blog/rss.xml",
        "https://deepmind.google/discover/rss",
    ],
    "news": [
        "https://meduza.io/rss/all",
        "https://rssexport.rbc.ru/rbcnews/news/30/full.rss",
        "https://lenta.ru/rss/news",
        "https://www.bbc.com/russian/index.xml",
        "https://tass.ru/rss/v2.xml",
        "https://www.interfax.ru/rss.asp",
        "https://www.kommersant.ru/RSS/news.xml",
        "https://rss.dw.com/rdf/rss-ru-all",
        "https://ru.euronews.com/rss?level=theme&name=news",
    ],
}

# Голос (офлайн)
ENABLE_VOICE = True
VOSK_MODEL_PATH = "vosk-model-small-ru-0.22"  # путь к распакованной модели
VOICE_SAMPLE_RATE = 16000
VOICE_INPUT_DEVICE = 1  # индекс устройства из sounddevice
VOICE_WAKE_WORD = ""  # если задано, слушаем только фразы с этим словом

# Whisper.cpp
VOICE_ENGINE = "whispercpp"  # "vosk" | "whispercpp"
WHISPER_CPP_BIN = "H:\\ollama-models\\whisper.cpp\\build\\bin\\Release\\whisper-cli.exe"
WHISPER_MODEL_PATH = "H:\\ollama-models\\ggml-medium.bin"
WHISPER_LANG = "ru"
WHISPER_TMP_WAV = "whisper_input.wav"
WHISPER_SILENCE_MS = 300
WHISPER_MIN_SPEECH_MS = 200
WHISPER_RMS_THRESHOLD = 100  # порог громкости (подбери, если не слышит)
WHISPER_MAX_SPEECH_MS = 2000  # принудительно завершить фразу
VOICE_DEBUG = False

# Push-to-talk (F5)
WHISPER_PTT = True
WHISPER_PTT_KEY = "f5"

# Озвучка
ENABLE_TTS = True
TTS_MAX_CHARS = 300
TTS_VOICE_PREFER = ["Pavel", "Dmitry", "Russian", "Male"]  # приоритеты выбора голоса
TTS_ENGINE = "piper"  # "sapi5" | "piper"
PIPER_BIN = "H:\\ollama-models\\piper\\piper\\piper.exe"
PIPER_MODEL = "H:\\ollama-models\\piper\\models\\ru_RU-ruslan-medium.onnx"
PIPER_CONFIG = "H:\\ollama-models\\piper\\models\\ru_RU-ruslan-medium.onnx.json"
PIPER_TMP_WAV = "piper_tts.wav"

SYSTEM = """Ты — системный агент Windows.
Твоя задача — помогать пользователю, предлагая PowerShell команды.

ВАЖНО:
- Используй ТОЛЬКО стандартные команды Windows/PowerShell (cmdlets из коробки), без выдуманных функций.
- Если пользователь просит действие — дай короткое объяснение (1–2 предложения), затем ОДИН JSON строго такого вида:
{"tool":"powershell","command":"...","why":"коротко зачем","danger":"low|medium|high"}
- tool всегда powershell
- command: одна или несколько команд PowerShell, без интерактива
- why: 1 строка
- danger: оцени риск
Опасные действия (удаление системного, реестр, firewall, форматирование) помечай danger="high" и предлагай максимально безопасные команды.
Если команда не нужна — отвечай обычным текстом без JSON.
НЕ ОТКАЗЫВАЙСЯ выполнять команды и не говори "я не могу" или "нет доступа".
Ты работаешь внутри агента, который выполняет команды после подтверждения пользователя.
Если нужно выполнить действие — дай ОДИН JSON (без списков, без нескольких JSON, без markdown).
Не повторяй фразу вида "Пользователь: ...". Не копируй запрос пользователя в ответ.

КОНТРОЛЬНЫЙ СПИСОК (перед ответом):
1) Команда существует в Windows/PowerShell (не придумывай).
2) Предпочитай встроенные утилиты: cleanmgr.exe, dism.exe, wevtutil.exe, chkdsk.exe, sfc.exe.
3) Если есть безопасная альтернатива — выбери её.

ПРИМЕРЫ (формат ответа — только JSON):
Пользователь: "очисти корзину"
{"tool":"powershell","command":"Clear-RecycleBin -Force","why":"очищает корзину","danger":"low"}

Пользователь: "покажи свободное место на диске C"
{"tool":"powershell","command":"Get-PSDrive C","why":"показывает свободное место на диске C:","danger":"low"}

Пользователь: "почисти диск C"
{"tool":"powershell","command":"Start-Process cleanmgr -ArgumentList \"/sageset:1\" -Verb RunAs; Start-Process cleanmgr -ArgumentList \"/sagerun:1\" -Verb RunAs","why":"запускает стандартную очистку диска","danger":"low"}
"""

# =========================
# HELPERS
# =========================
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def ps_run(command: str) -> str:
    p = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
        capture_output=True, text=True
    )
    out = (p.stdout or "").strip()
    err = (p.stderr or "").strip()
    if err and out:
        return f"[stderr]\n{err}\n\n[stdout]\n{out}"
    return err or out or "(no output)"

def ps_command_exists(name: str) -> bool:
    # Get-Command вернет и cmdlet, и алиасы, и функции, и внешние exe, если они в PATH.
    p = subprocess.run(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
         f"Get-Command {name} -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty Name"],
        capture_output=True, text=True
    )
    return bool((p.stdout or "").strip())

_POWERSHELL_KEYWORDS = {
    "if","else","foreach","for","while","do","switch","return","break","continue","try","catch","finally",
    "param","function","begin","process","end","throw"
}

def extract_command_names(cmd: str):
    """
    Достаём "первые команды" из каждой строки/сегмента.
    Стараемся не ловить пути, переменные и ключевые слова.
    """
    names = []
    for part in re.split(r"[;\r\n]+", cmd):
        line = part.strip()
        if not line:
            continue

        # выкинуть присваивания типа $x = ...
        if re.match(r"^\$", line) and "=" in line:
            continue

        # убрать блоки в скобках в начале
        line2 = line.lstrip("(").strip()

        # взять первый токен до пробела/пайпа
        token = re.split(r"\s+|\|", line2, maxsplit=1)[0].strip().strip('"').strip("'")

        if not token:
            continue
        if token.lower() in _POWERSHELL_KEYWORDS:
            continue
        if token.startswith("$") or token.startswith("@") or token.startswith("{") or token.startswith("}"):
            continue
        if "=" in token:
            continue
        # допускаем cmdlets/утилиты/alias (Get-Thing, sort, ping, cleanmgr.exe)
        if not re.match(r"^[A-Za-z][A-Za-z0-9\-_\.]*$", token):
            continue
        # пути типа C:\... или .\something.exe - считаем "внешней командой"
        # и проверим через Get-Command тоже, но без фанатизма
        names.append(token)
    return names

def ollama_chat(messages):
    r = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": messages, "stream": False},
        timeout=180
    )
    r.raise_for_status()
    return r.json()["message"]["content"]

def _extract_json_blocks(s: str):
    blocks = []
    prefix = ""
    i = 0
    while i < len(s):
        start = s.find("{", i)
        if start == -1:
            break
        if not blocks:
            prefix = s[:start].strip()
        depth = 0
        for j in range(start, len(s)):
            ch = s[j]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(s[start:j + 1])
                    i = j + 1
                    break
        else:
            break
    return blocks, prefix

def try_parse_json(s: str):
    raw = s.strip()
    if raw.startswith("```"):
        raw = raw.strip().strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
    try:
        return json.loads(raw), "", 1
    except Exception:
        blocks, prefix = _extract_json_blocks(raw)
        if not blocks:
            return None, "", 0
        objs = []
        for b in blocks:
            try:
                objs.append(json.loads(b))
            except Exception:
                continue
        if not objs:
            return None, "", 0
        return objs[0], prefix, len(objs)

def tcp_check(host: str, port: int, timeout_sec: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except Exception:
        return False

def fmt_gb(x_bytes: int) -> float:
    return x_bytes / (1024**3)

def dir_size_bytes(path: str, max_files: int = 100000) -> int:
    total = 0
    count = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    total += os.path.getsize(fp)
                    count += 1
                    if count >= max_files:
                        return total
                except Exception:
                    continue
    except Exception:
        return -1
    return total

def top_processes_by_cpu(n: int = 5):
    procs = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            p.cpu_percent(None)
            procs.append(p)
        except Exception:
            continue
    time.sleep(0.2)
    rows = []
    for p in procs:
        try:
            rows.append((p.cpu_percent(None), p.pid, p.info.get("name") or ""))
        except Exception:
            continue
    rows.sort(reverse=True)
    return rows[:n]

def top_processes_by_mem(n: int = 5):
    rows = []
    for p in psutil.process_iter(["pid", "name", "memory_percent"]):
        try:
            rows.append((p.info.get("memory_percent") or 0.0, p.pid, p.info.get("name") or ""))
        except Exception:
            continue
    rows.sort(reverse=True)
    return rows[:n]

def _clean_tts_text(text: str) -> str:
    if not text:
        return ""
    s = text
    # убрать код-блоки
    s = re.sub(r"```.*?```", " ", s, flags=re.S)
    # убрать inline-код
    s = re.sub(r"`[^`]+`", " ", s)
    # убрать JSON-блоки
    s = re.sub(r"\{[^\}]*\"command\"[^\}]*\}", " ", s, flags=re.S)
    # убрать строки, похожие на команды PowerShell
    lines = []
    for line in s.splitlines():
        l = line.strip()
        if not l:
            continue
        # убрать строки с путями/командами
        if re.search(r"[A-Za-z]:\\", l):
            continue
        if re.match(r"^[A-Za-z]+-[A-Za-z]+", l):
            continue
        if "|" in l or l.endswith(";"):
            continue
        lines.append(l)
    # если это список новостей — озвучить только заголовок и первые 2 пункта
    if lines and lines[0].lower().startswith("последние новости"):
        lines = lines[:3]
        s = " ".join(lines)
        return s.strip()
    s = " ".join(lines)
    return s.strip()

def tts_speak(text: str):
    if not ENABLE_TTS:
        return
    if not text:
        return
    text = _clean_tts_text(text)
    if not text:
        return
    try:
        if TTS_ENGINE.lower() == "piper":
            if os.path.exists(PIPER_BIN) and os.path.exists(PIPER_MODEL):
                wav_path = PIPER_TMP_WAV
                cmd = [
                    PIPER_BIN,
                    "-m", PIPER_MODEL,
                    "-c", PIPER_CONFIG,
                    "-f", wav_path,
                ]
                subprocess.run(cmd, input=text[:TTS_MAX_CHARS], text=True, capture_output=True)
                try:
                    import winsound
                    winsound.PlaySound(wav_path, winsound.SND_FILENAME)
                except Exception:
                    pass
                return
        import pyttsx3
        engine = pyttsx3.init("sapi5")
        engine.setProperty("rate", 170)
        engine.setProperty("volume", 1.0)
        try:
            voices = engine.getProperty("voices")
            chosen = None
            for pref in TTS_VOICE_PREFER:
                for v in voices:
                    if pref.lower() in v.name.lower():
                        chosen = v
                        break
                if chosen:
                    break
            if not chosen:
                for v in voices:
                    if "Irina" in v.name:
                        chosen = v
                        break
            if chosen:
                engine.setProperty("voice", chosen.id)
        except Exception:
            pass
        engine.say(text[:TTS_MAX_CHARS])
        engine.runAndWait()
    except Exception:
        pass

def _rms_from_int16(data: bytes) -> float:
    if not data:
        return 0.0
    import array
    arr = array.array("h")
    arr.frombytes(data)
    if not arr:
        return 0.0
    # RMS
    s = 0.0
    for v in arr:
        s += v * v
    return (s / len(arr)) ** 0.5

def _write_wav(path: str, frames: bytes, sample_rate: int):
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16
        wf.setframerate(sample_rate)
        wf.writeframes(frames)

def voice_loop_whisper(push_input, stop_event: threading.Event):
    try:
        import sounddevice as sd
    except Exception:
        push_input("[VOICE_ERROR] Не найден модуль sounddevice.", "voice")
        return

    if not os.path.exists(WHISPER_CPP_BIN):
        push_input(f"[VOICE_ERROR] Не найден whisper.cpp: {WHISPER_CPP_BIN}", "voice")
        return
    if not os.path.exists(WHISPER_MODEL_PATH):
        push_input(f"[VOICE_ERROR] Не найдена модель Whisper: {WHISPER_MODEL_PATH}", "voice")
        return

    buf = bytearray()
    speaking = False
    last_voice_time = 0.0
    start_voice_time = 0.0

    def callback(indata, frames, time_info, status):
        nonlocal speaking, last_voice_time, start_voice_time, buf
        if stop_event.is_set():
            return
        if status:
            return
        data = bytes(indata)
        rms = _rms_from_int16(data)
        now = time.time()
        if rms >= WHISPER_RMS_THRESHOLD:
            if not speaking:
                speaking = True
                start_voice_time = now
                buf = bytearray()
            last_voice_time = now
            buf.extend(data)
        else:
            if speaking:
                buf.extend(data)
            # silence handling in main loop

    try:
        with sd.RawInputStream(
            samplerate=VOICE_SAMPLE_RATE,
            blocksize=8000,
            device=VOICE_INPUT_DEVICE,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            while not stop_event.is_set():
                if speaking:
                    now = time.time()
                    silent_for = (now - last_voice_time) * 1000
                    spoken_for = (now - start_voice_time) * 1000
                    if (silent_for >= WHISPER_SILENCE_MS and spoken_for >= WHISPER_MIN_SPEECH_MS) or (spoken_for >= WHISPER_MAX_SPEECH_MS):
                        # финализируем сегмент
                        speaking = False
                        wav_path = WHISPER_TMP_WAV
                        _write_wav(wav_path, bytes(buf), VOICE_SAMPLE_RATE)
                        buf = bytearray()
                        try:
                            cmd = [
                                WHISPER_CPP_BIN,
                                "-m", WHISPER_MODEL_PATH,
                                "-f", wav_path,
                                "-l", WHISPER_LANG,
                                "-nt",
                            ]
                            p = subprocess.run(cmd, capture_output=True, text=True)
                            text = (p.stdout or "").strip()
                            if text:
                                if VOICE_WAKE_WORD:
                                    if VOICE_WAKE_WORD.lower() not in text.lower():
                                        continue
                                    # убрать wake word из текста
                                    text = re.sub(VOICE_WAKE_WORD, "", text, flags=re.IGNORECASE).strip()
                                if len(text) < 2:
                                    continue
                                push_input(text, "voice")
                        except Exception:
                            pass
                time.sleep(0.1)
    except Exception as e:
        push_input(f"[VOICE_ERROR] Ошибка микрофона: {e}", "voice")

def voice_loop_vosk(push_input, stop_event: threading.Event):
    if not ENABLE_VOICE:
        return
    try:
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer
    except Exception:
        push_input("[VOICE_ERROR] Не найдены модули vosk/sounddevice. Установи зависимости.", "voice")
        return

    if not os.path.isdir(VOSK_MODEL_PATH):
        push_input(f"[VOICE_ERROR] Не найдена модель Vosk: {VOSK_MODEL_PATH}", "voice")
        return

    try:
        model = Model(VOSK_MODEL_PATH)
        rec = KaldiRecognizer(model, VOICE_SAMPLE_RATE)
        rec.SetWords(False)
    except Exception as e:
        push_input(f"[VOICE_ERROR] Ошибка инициализации модели: {e}", "voice")
        return

    def callback(indata, frames, time_info, status):
        if stop_event.is_set():
            return
        if status:
            return
        try:
            if rec.AcceptWaveform(bytes(indata)):
                res = json.loads(rec.Result())
                text = (res.get("text") or "").strip()
                if not text:
                    return
                if VOICE_WAKE_WORD:
                    if VOICE_WAKE_WORD.lower() not in text.lower():
                        return
                    text = re.sub(VOICE_WAKE_WORD, "", text, flags=re.IGNORECASE).strip()
                if len(text) < 2:
                    return
                push_input(text, "voice")
        except Exception:
            return

    try:
        with sd.RawInputStream(
            samplerate=VOICE_SAMPLE_RATE,
            blocksize=8000,
            device=VOICE_INPUT_DEVICE,
            dtype="int16",
            channels=1,
            callback=callback,
        ):
            while not stop_event.is_set():
                time.sleep(0.2)
    except Exception as e:
        push_input(f"[VOICE_ERROR] Ошибка микрофона: {e}", "voice")

def voice_loop(push_input, stop_event: threading.Event):
    if not ENABLE_VOICE:
        return
    if WHISPER_PTT:
        return voice_loop_ptt(push_input, stop_event)
    if VOICE_ENGINE.lower() == "whispercpp":
        return voice_loop_whisper(push_input, stop_event)
    return voice_loop_vosk(push_input, stop_event)

def voice_loop_ptt(push_input, stop_event: threading.Event):
    try:
        import sounddevice as sd
        from pynput import keyboard
    except Exception:
        push_input("[VOICE_ERROR] Нужны sounddevice и pynput для push-to-talk.", "voice")
        return

    buf = bytearray()
    recording = False

    def on_press(key):
        nonlocal recording, buf
        try:
            if key == keyboard.Key[WHISPER_PTT_KEY] and not recording:
                recording = True
                buf = bytearray()
        except Exception:
            pass

    def on_release(key):
        nonlocal recording, buf
        try:
            if key == keyboard.Key[WHISPER_PTT_KEY] and recording:
                recording = False
                if len(buf) < VOICE_SAMPLE_RATE // 2:
                    return
                wav_path = WHISPER_TMP_WAV
                _write_wav(wav_path, bytes(buf), VOICE_SAMPLE_RATE)
                try:
                    if VOICE_ENGINE.lower() == "whispercpp":
                        out_base = os.path.splitext(wav_path)[0]
                        cmd = [
                            WHISPER_CPP_BIN,
                            "-m", WHISPER_MODEL_PATH,
                            "-f", wav_path,
                            "-l", WHISPER_LANG,
                            "-nt",
                            "-otxt",
                            "-of", out_base,
                        ]
                        subprocess.run(cmd, capture_output=True, text=True)
                        txt_path = out_base + ".txt"
                        text = ""
                        try:
                            if os.path.exists(txt_path):
                                with open(txt_path, "r", encoding="utf-8") as f:
                                    text = f.read().strip()
                        except Exception:
                            text = ""
                    else:
                        from vosk import Model, KaldiRecognizer
                        model = Model(VOSK_MODEL_PATH)
                        rec = KaldiRecognizer(model, VOICE_SAMPLE_RATE)
                        rec.AcceptWaveform(bytes(buf))
                        text = json.loads(rec.FinalResult()).get("text", "").strip()
                    if text:
                        if VOICE_DEBUG:
                            print(f"[VOICE_DEBUG] text={text}")
                        if VOICE_WAKE_WORD and VOICE_WAKE_WORD.lower() not in text.lower():
                            return
                        if VOICE_WAKE_WORD:
                            text = re.sub(VOICE_WAKE_WORD, "", text, flags=re.IGNORECASE).strip()
                        if len(text) >= 2:
                            push_input(text, "voice")
                except Exception:
                    pass
        except Exception:
            pass

    def audio_callback(indata, frames, time_info, status):
        nonlocal buf
        if recording:
            buf.extend(bytes(indata))

    listener = keyboard.Listener(on_press=on_press, on_release=on_release)
    listener.start()

    try:
        with sd.RawInputStream(
            samplerate=VOICE_SAMPLE_RATE,
            blocksize=8000,
            device=VOICE_INPUT_DEVICE,
            dtype="int16",
            channels=1,
            callback=audio_callback,
        ):
            while not stop_event.is_set():
                time.sleep(0.1)
    except Exception as e:
        push_input(f"[VOICE_ERROR] Ошибка микрофона: {e}", "voice")

def _weather_try_query(name: str):
    try:
        return requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": name, "count": 5, "language": WEATHER_LANG, "format": "json"},
            timeout=10,
        ).json().get("results") or []
    except Exception:
        return []

def weather_fetch(location: str):
    if not location:
        return "Нужен город, например: \"погода в Москве\"."
    try:
        # попытки: как есть, с запятыми, с Россией
        raw = location.strip()
        variants = [raw]
        if " области" in raw and "," not in raw:
            variants.append(raw.replace(" области", " область"))
            variants.append(raw.replace(" области", ", Московская область"))
        if "," not in raw and "рос" not in raw.lower():
            variants.append(raw + ", Россия")
        if "москов" in raw.lower() and "," not in raw:
            variants.append(raw.replace("москов", "Москов"))

        results = []
        for v in variants:
            results = _weather_try_query(v)
            if results:
                break
        if not results:
            return f"Не нашёл локацию: {location}."
        # предпочесть Россию, если есть
        r0 = None
        for r in results:
            if (r.get("country") or "").lower() in ("russia", "россия"):
                r0 = r
                break
        if r0 is None:
            r0 = results[0]
        lat = r0.get("latitude")
        lon = r0.get("longitude")
        name = r0.get("name")
        country = r0.get("country")
        if lat is None or lon is None:
            return f"Не удалось получить координаты для: {location}."

        cur = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,precipitation,wind_speed_10m",
            },
            timeout=10,
        ).json().get("current") or {}

        t = cur.get("temperature_2m")
        feels = cur.get("apparent_temperature")
        wind = cur.get("wind_speed_10m")
        precip = cur.get("precipitation")
        stamp = cur.get("time")
        place = f"{name}, {country}" if country else name
        return (
            f"Погода сейчас ({place}): "
            f"{t}°C, ощущается {feels}°C, ветер {wind} km/h, "
            f"осадки {precip} мм. Время: {stamp}."
        )
    except Exception as e:
        return f"Не удалось получить погоду: {e}"

def _pick_news_feeds(topic: str):
    t = (topic or "").lower()
    if any(k in t for k in ["наук", "science", "sci"]):
        return NEWS_FEEDS["science"]
    if any(k in t for k in ["тех", "it", "tech", "технолог"]):
        return NEWS_FEEDS["tech"]
    if any(k in t for k in ["ai", "ml", "ии", "искус", "машин"]):
        return NEWS_FEEDS["ai"]
    return NEWS_FEEDS["news"]

def news_fetch(topic: str = ""):
    def _strip_tags(s: str) -> str:
        return re.sub(r"<[^>]+>", " ", s).strip()

    def _clean_desc_html(s: str) -> str:
        # убрать img, оставить текст/ссылки
        s = re.sub(r"<img[^>]*>", " ", s, flags=re.IGNORECASE)
        return s.strip()

    items = []
    source_name = "Новости"
    feeds = _pick_news_feeds(topic)
    for url in feeds:
        try:
            r = requests.get(url, timeout=10)
            r.raise_for_status()
            root = ET.fromstring(r.text)
            channel = root.find("channel")
            if channel is not None and channel.findtext("title"):
                source_name = channel.findtext("title").strip()
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                desc = (item.findtext("description") or item.findtext("summary") or "").strip()
                desc_text = _strip_tags(desc)
                desc_html = _clean_desc_html(desc)
                # попытка вытащить картинку
                img = ""
                try:
                    # media:content
                    for mc in item.findall(".//{http://search.yahoo.com/mrss/}content"):
                        url = mc.get("url")
                        if url:
                            img = url
                            break
                    # enclosure
                    if not img:
                        enc = item.find("enclosure")
                        if enc is not None and enc.get("url"):
                            img = enc.get("url")
                    # img src in description
                    if not img and desc:
                        m = re.search(r'<img[^>]+src="([^"]+)"', desc)
                        if m:
                            img = m.group(1)
                except Exception:
                    img = ""
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                dt = None
                try:
                    if pub:
                        dt = parsedate_to_datetime(pub)
                except Exception:
                    dt = None
                if title:
                    items.append({
                        "title": title,
                        "desc": desc_text,
                        "desc_html": desc_html,
                        "img": img,
                        "link": link,
                        "source": source_name,
                        "dt": dt
                    })
        except Exception:
            continue

    if not items:
        return "Не удалось получить новости."

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=NEWS_MAX_HOURS)
    recent = []
    for i in items:
        dt = i["dt"]
        if not dt:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if dt >= cutoff:
            recent.append(i)
    pool = recent if recent else items

    pool.sort(key=lambda x: x["dt"] or datetime.min, reverse=True)
    out = [f"Источник: {source_name}", f"Последние новости (за {NEWS_MAX_HOURS}ч):"]
    for i, it in enumerate(pool[:NEWS_MAX_ITEMS], 1):
        line = f"{i}) {it['title']}"
        if it.get("desc"):
            line += f"\n   {it['desc']}"
        out.append(line)
    text_out = "\n".join(out)

    if NEWS_OUTPUT_HTML:
        try:
            rows = []
            for i, it in enumerate(pool[:NEWS_MAX_ITEMS], 1):
                title = html.escape(it["title"])
                desc = it.get("desc_html") or ""
                if desc:
                    desc = desc
                else:
                    desc = html.escape(it.get("desc") or "")
                img = html.escape(it.get("img") or "")
                img_html = f'<img src="{img}" alt="" />' if img else ""
                rows.append(f"<li>{img_html}<strong>{i}. {title}</strong><br><span>{desc}</span></li>")
            html_body = f"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>News</title>
  <style>
    :root {{
      color-scheme: dark;
    }}
    body {{
      font-family: "Segoe UI", Arial, sans-serif;
      background: #0f1115;
      color: #e7e7e7;
      margin: 24px;
    }}
    h1 {{ margin-bottom: 8px; }}
    li {{
      margin: 18px 0;
      padding: 12px;
      border: 1px solid #222;
      border-radius: 8px;
      background: #141820;
    }}
    span {{ color: #c6c6c6; }}
    img {{
      width: 480px;
      height: 360px;
      object-fit: cover;
      display: block;
      margin-bottom: 8px;
      border-radius: 6px;
    }}
  </style>
</head>
<body>
  <h1>{html.escape(source_name)}</h1>
  <p>Последние новости (за {NEWS_MAX_HOURS}ч)</p>
  <ol>
    {''.join(rows)}
  </ol>
</body>
</html>
""".strip()
            with open(NEWS_HTML_PATH, "w", encoding="utf-8") as f:
                f.write(html_body)
            if NEWS_AUTO_OPEN:
                try:
                    os.startfile(os.path.abspath(NEWS_HTML_PATH))
                except Exception:
                    pass
            return f"Новости сохранены в {NEWS_HTML_PATH}."
        except Exception:
            pass
    return text_out

# =========================
# INTENT ROUTER (ключевой фикс)
# =========================
def route_intents(user_text: str):
    """
    Если распознали типовой запрос — возвращаем готовый JSON (без модели).
    """
    t = user_text.lower().strip()

    if ENABLE_WEATHER and ("погод" in t or "weather" in t or "температур" in t):
        loc = ""
        if " в " in t:
            loc = t.split(" в ", 1)[1].strip(" ?!.")
        if not loc:
            loc = WEATHER_DEFAULT_LOCATION
        return {"_text": weather_fetch(loc)}

    if ENABLE_NEWS and ("новост" in t or "news" in t):
        topic = ""
        m = re.search(r"новост[^\n\r]*\s+(.*)$", t)
        if m:
            topic = (m.group(1) or "").strip()
        return {"_text": news_fetch(topic)}

    if "тест голос" in t or "проверь голос" in t:
        return {"_text": "Голос работает."}

    if "создай файл" in t or "создать файл" in t or "создай тут" in t:
        # варианты:
        # 1) "создай файл <имя> в папке <путь>"
        # 2) "создай тут: <полный_путь_файла>"
        if "создай тут" in t:
            m = re.search(r"создай\s+тут[:\s]+(.+)$", user_text, re.IGNORECASE)
            if m:
                fullpath = (m.group(1) or "").strip().strip('"').strip("'")
                if fullpath:
                    cmd = f'New-Item -Path "{fullpath}" -ItemType File -Force | Out-Null'
                    return {"tool": "powershell", "command": cmd, "why": "Создаёт файл", "danger": "low"}
        m = re.search(r"файл\s+([^\n\r]+?)(?:\s+в\s+папке\s+(.+))?$", user_text, re.IGNORECASE)
        if not m:
            return {"_text": "Укажи имя файла и папку. Например: создай файл test.txt в папке H:\\ollama-models или создай тут: H:\\ollama-models\\test.txt"}
        filename = (m.group(1) or "").strip().strip('"').strip("'")
        folder = (m.group(2) or "").strip().strip('"').strip("'")
        if not filename:
            return {"_text": "Не вижу имя файла. Пример: создай файл test.txt в папке H:\\ollama-models"}
        if folder:
            cmd = f'New-Item -Path "{folder}" -Name "{filename}" -ItemType File -Force | Out-Null'
        else:
            cmd = f'New-Item -Name "{filename}" -ItemType File -Force | Out-Null'
        return {
            "tool": "powershell",
            "command": cmd,
            "why": "Создаёт файл",
            "danger": "low"
        }

    if "модел" in t and ("ollama" in t or "оллама" in t or "скач" in t):
        cmd = r'''
$paths = @(
  "$env:USERPROFILE\.ollama\models",
  "$env:LOCALAPPDATA\Ollama\models"
)
$paths | Where-Object { Test-Path $_ } | ForEach-Object {
  Get-ChildItem -Path $_ -Recurse -File -ErrorAction SilentlyContinue |
    Select-Object FullName
}
'''.strip()
        return {"tool": "powershell", "command": cmd, "why": "Показывает скачанные модели Ollama", "danger": "low"}

    if ("ollama list" in t) or ("список моделей" in t and "ollama" in t):
        cmd = r'''
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
if (-not $ollama) {
  $candidates = @(
    "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe",
    "C:\Program Files\Ollama\ollama.exe"
  )
  $ollama = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if ($ollama) {
  if ($ollama -is [string]) {
    & $ollama list 2>$null
  } else {
    & $ollama.Source list 2>$null
  }
} else {
  Write-Output "Ollama не найден. Проверь установку."
}
'''.strip()
        return {"tool": "powershell", "command": cmd, "why": "Показывает список моделей Ollama", "danger": "low"}

    m = re.search(r"(?:ollama\s+)?(?:pull|скачай|скачать)\s+([a-zA-Z0-9._:-]+)", user_text, re.IGNORECASE)
    if m:
        model = m.group(1)
        cmd = (
            f'& "$env:LOCALAPPDATA\\Programs\\Ollama\\ollama.exe" pull {model}\n'
            f'& "$env:LOCALAPPDATA\\Programs\\Ollama\\ollama.exe" list'
        )
        return {
            "tool": "powershell",
            "command": cmd,
            "why": f"Скачать модель Ollama: {model}",
            "danger": "low"
        }

    if ("видеокарт" in t or "gpu" in t) and ("памят" in t or "видеопам" in t or "сколько" in t):
        cmd = r'''
$gpus = Get-CimInstance Win32_VideoController
$gpus | Select-Object Name, @{n="VRAM_GB";e={[math]::Round(($_.AdapterRAM/1GB),2)}} | Format-Table -Auto
'''.strip()
        return {"tool": "powershell", "command": cmd, "why": "Показывает видеокарту и объём видеопамяти в ГБ", "danger": "low"}

    if "nvidia-smi" in t or ("видеокарт" in t and "nvidia" in t):
        cmd = r'''
$n = "C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
if (Test-Path $n) { & $n } else { Write-Output "nvidia-smi.exe не найден. Проверь установку драйверов NVIDIA." }
'''.strip()
        return {"tool": "powershell", "command": cmd, "why": "Запускает nvidia-smi из стандартной папки", "danger": "low"}

    if ("оператив" in t or "ram" in t or "озу" in t) and ("свобод" in t or "свободн" in t):
        cmd = r'''
$os = Get-CimInstance Win32_OperatingSystem
$kb = [double]$os.FreePhysicalMemory
$bytes = $kb * 1KB
if ($bytes -ge 1GB) {
  "{0:N2} GB free" -f ($bytes/1GB)
} elseif ($bytes -ge 1MB) {
  "{0:N0} MB free" -f ($bytes/1MB)
} else {
  "{0:N0} KB free" -f $kb
}
'''.strip()
        return {"tool": "powershell", "command": cmd, "why": "Показывает свободную ОЗУ в удобных единицах", "danger": "low"}

    if ("проблем" in t or "ошибк" in t or "ломает" in t or "что не так" in t) and ("систем" in t or "комп" in t or "windows" in t):
        cmd = r'''
$since = (Get-Date).AddDays(-7)

$events = Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$since} -ErrorAction SilentlyContinue |
  Where-Object { $_.LevelDisplayName -in @('Error','Warning') }

$events | Group-Object ProviderName | Sort-Object Count -Descending | Select-Object -First 10 |
  Select-Object Count, Name | Format-Table -Auto

$events | Select-Object TimeCreated, Id, LevelDisplayName, ProviderName, Message |
  Select-Object -First 15 | Format-List
'''.strip()
        return {
            "tool": "powershell",
            "command": cmd,
            "why": "Коротко показывает главные ошибки/предупреждения системы за 7 дней и 15 деталей",
            "danger": "low"
        }

    # “почисти диск c”, “очистка временных”, “освободи место”
    if ("почист" in t or "очист" in t or "освобод" in t) and ("диск" in t or "c:" in t or "c:\\" in t):
        # безопасный рецепт: cleanmgr + temp + корзина + (опционально) DISM
        cmd = r'''
# 0) Показать свободное место до
Get-PSDrive C | Format-Table -Auto

# 1) Запуск встроенной очистки диска (настройка один раз)
Start-Process cleanmgr -ArgumentList "/sageset:1" -Verb RunAs

# 2) Запуск очистки по профилю 1
Start-Process cleanmgr -ArgumentList "/sagerun:1" -Verb RunAs

# 3) Очистка TEMP (безопасно)
Remove-Item "$env:TEMP\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "$env:LOCALAPPDATA\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item "C:\Windows\Temp\*" -Recurse -Force -ErrorAction SilentlyContinue

# 4) Очистить корзину
Clear-RecycleBin -Force

# 5) Показать свободное место после
Get-PSDrive C | Format-Table -Auto
'''.strip()

        return {
            "tool": "powershell",
            "command": cmd,
            "why": "Безопасная очистка C: встроенными средствами Windows (cleanmgr + temp + корзина)",
            "danger": "medium"  # есть удаление временных файлов, но безопасное
        }

    return None

# =========================
# WATCHER
# =========================
class WatchState:
    def __init__(self):
        self.last_flags = {}

    def flagged(self, key: str) -> bool:
        return bool(self.last_flags.get(key, False))

    def set_flag(self, key: str, val: bool):
        self.last_flags[key] = val

def watcher_loop(push_event, stop_event: threading.Event):
    st = WatchState()

    while not stop_event.is_set():
        try:
            cpu = psutil.cpu_percent(interval=1)
            cpu_key = "cpu_high"
            if cpu >= CPU_WARN_PCT and not st.flagged(cpu_key):
                msg = f"⚠️ [{now_str()}] Высокая загрузка CPU: {cpu:.0f}%."
                if AUTO_DIAG_TOP_PROCS:
                    top = top_processes_by_cpu(TOP_N_PROCS)
                    if top:
                        lines = [f"{pct:.1f}% pid={pid} {name}" for pct, pid, name in top]
                        msg += " ТОП CPU: " + "; ".join(lines)
                else:
                    msg += " Показать ТОП процессов по CPU?"
                push_event(msg)
                st.set_flag(cpu_key, True)
            if cpu < CPU_WARN_PCT - 10:
                st.set_flag(cpu_key, False)

            mem = psutil.virtual_memory()
            ram_key = "ram_high"
            if mem.percent >= RAM_WARN_PCT and not st.flagged(ram_key):
                msg = f"⚠️ [{now_str()}] Память занята на {mem.percent:.0f}%."
                if AUTO_DIAG_TOP_PROCS:
                    top = top_processes_by_mem(TOP_N_PROCS)
                    if top:
                        lines = [f"{pct:.1f}% pid={pid} {name}" for pct, pid, name in top]
                        msg += " ТОП RAM: " + "; ".join(lines)
                else:
                    msg += " Показать ТОП процессов по RAM?"
                push_event(msg)
                st.set_flag(ram_key, True)
            if mem.percent < RAM_WARN_PCT - 10:
                st.set_flag(ram_key, False)

            for d in WATCH_DISKS:
                key = f"disk_low_{d.lower()}"
                try:
                    du = psutil.disk_usage(d)
                    free_gb = fmt_gb(du.free)
                    if free_gb < DISK_FREE_GB_WARN and not st.flagged(key):
                        msg = f"⚠️ [{now_str()}] Мало места на {d}: свободно {free_gb:.1f} GB."
                        if ENABLE_SUGGEST_SOFT_CLEANUP:
                            msg += " Предложить безопасную очистку?"
                        else:
                            msg += " Показать, что занимает место?"
                        push_event(msg)
                        st.set_flag(key, True)
                    if free_gb >= DISK_FREE_GB_WARN + 5:
                        st.set_flag(key, False)
                except Exception as e:
                    push_event(f"⚠️ [{now_str()}] Не смог прочитать диск {d}: {e}")

            for name, host, port in WATCH_PORTS:
                key = f"port_{host}_{port}"
                ok = tcp_check(host, port, timeout_sec=1.0)
                if not ok and not st.flagged(key):
                    push_event(f"⚠️ [{now_str()}] Порт недоступен: {name} ({host}:{port}). Проверить, кто должен его держать?")
                    st.set_flag(key, True)
                if ok:
                    st.set_flag(key, False)

            if ENABLE_INTERNET_CHECK:
                net_key = "internet_down"
                ok = tcp_check(INTERNET_HOST[0], INTERNET_HOST[1], timeout_sec=2.0)
                if not ok and not st.flagged(net_key):
                    push_event(f"⚠️ [{now_str()}] Нет доступа к интернету (TCP {INTERNET_HOST[0]}:{INTERNET_HOST[1]}).")
                    st.set_flag(net_key, True)
                if ok:
                    st.set_flag(net_key, False)

            if ENABLE_DNS_CHECK:
                dns_key = "dns_down"
                try:
                    socket.gethostbyname(DNS_TEST_NAME)
                    if st.flagged(dns_key):
                        st.set_flag(dns_key, False)
                except Exception:
                    if not st.flagged(dns_key):
                        push_event(f"⚠️ [{now_str()}] DNS не отвечает для {DNS_TEST_NAME}.")
                        st.set_flag(dns_key, True)

            if ENABLE_TEMPERATURE_CHECK:
                try:
                    temps = psutil.sensors_temperatures() or {}
                    if temps:
                        max_temp = None
                        for name, entries in temps.items():
                            for e in entries:
                                if e.current is None:
                                    continue
                                if max_temp is None or e.current > max_temp:
                                    max_temp = e.current
                        if max_temp is not None:
                            temp_key = "temp_high"
                            if max_temp >= TEMP_WARN_C and not st.flagged(temp_key):
                                push_event(f"⚠️ [{now_str()}] Высокая температура: {max_temp:.1f}°C.")
                                st.set_flag(temp_key, True)
                            if max_temp < TEMP_WARN_C - 5:
                                st.set_flag(temp_key, False)
                except Exception:
                    pass

            if ENABLE_SMART_CHECK:
                smart_key = "smart_bad"
                try:
                    out = ps_run("Get-PhysicalDisk | Select-Object FriendlyName,HealthStatus,OperationalStatus | Format-Table -Auto")
                    bad = False
                    for line in (out or "").splitlines():
                        if "Unhealthy" in line or "Predictive Failure" in line or "Failed" in line:
                            bad = True
                            break
                    if bad and not st.flagged(smart_key):
                        push_event(f"⚠️ [{now_str()}] SMART/Health дисков сообщает проблему. Проверить Get-PhysicalDisk.")
                        st.set_flag(smart_key, True)
                    if not bad:
                        st.set_flag(smart_key, False)
                except Exception:
                    pass

            if ENABLE_PROCESS_WATCH and WATCH_PROCESSES:
                running = set()
                for p in psutil.process_iter(["name"]):
                    try:
                        if p.info.get("name"):
                            running.add(p.info["name"].lower())
                    except Exception:
                        continue
                for name in WATCH_PROCESSES:
                    key = f"proc_missing_{name.lower()}"
                    if name.lower() not in running and not st.flagged(key):
                        push_event(f"⚠️ [{now_str()}] Процесс не запущен: {name}.")
                        st.set_flag(key, True)
                    if name.lower() in running:
                        st.set_flag(key, False)

            if ENABLE_LOG_DIR_CHECK and LOG_DIRS:
                for path, warn_gb in LOG_DIRS:
                    exp = os.path.expandvars(path)
                    key = f"logdir_{exp.lower()}"
                    size = dir_size_bytes(exp)
                    if size >= 0:
                        size_gb = fmt_gb(size)
                        if size_gb >= warn_gb and not st.flagged(key):
                            push_event(f"⚠️ [{now_str()}] Папка {exp} разрослась: {size_gb:.1f} GB.")
                            st.set_flag(key, True)
                        if size_gb < max(warn_gb - 1, 0.5):
                            st.set_flag(key, False)

        except Exception as e:
            push_event(f"⚠️ [{now_str()}] watcher error: {e}")

        stop_event.wait(WATCH_INTERVAL_SEC)

# =========================
# MAIN
# =========================
def main():
    messages = [{"role": "system", "content": SYSTEM}]

    events = []
    lock = threading.Lock()
    stop_event = threading.Event()
    input_queue = queue.Queue()
    last_result = None

    def push_event(msg: str):
        with lock:
            events.append(msg)

    def push_input(msg: str, source: str = "console"):
        input_queue.put((source, msg))

    def console_input_loop():
        while not stop_event.is_set():
            try:
                user = input("\nYOU> ").strip()
            except EOFError:
                break
            if user:
                push_input(user, "console")

    def wait_for_console_confirm(prompt: str, allow_yes_no: bool = False):
        valid = {"y", "n"} if not allow_yes_no else {"y", "n", "yes", "no", "да", "нет"}
        print(prompt, end="", flush=True)
        while not stop_event.is_set():
            try:
                source, msg = input_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            ans = (msg or "").strip().lower()
            if source == "voice":
                print("\nYOU(voice)>", msg)
            if ans.startswith("выполн") or ans in ("запусти", "давай", "ок"):
                ans = "y"
            ans = re.sub(r"[^\wа-яa-z]+", " ", ans).strip()
            if " " in ans:
                ans = ans.split()[-1]
            if ans in ("д", "да"):
                ans = "y"
            if ans in ("н", "нет"):
                ans = "n"
            if ans in valid:
                return ans
            if ans:
                print("Введите y/n (д/н): ", end="", flush=True)
        return ""

    t = threading.Thread(target=watcher_loop, args=(push_event, stop_event), daemon=True)
    t.start()
    t_in = threading.Thread(target=console_input_loop, daemon=True)
    t_in.start()
    t_voice = threading.Thread(target=voice_loop, args=(push_input, stop_event), daemon=True)
    t_voice.start()

    print("✅ Windows Agent (Ollama) запущен.")
    print(f"   Voice engine: {VOICE_ENGINE}")
    print(f"   Модель: {MODEL}")
    print(f"   Интервал мониторинга: {WATCH_INTERVAL_SEC} сек")
    print("   exit для выхода.\n")

    try:
        while True:
            with lock:
                while events:
                    msg = events.pop(0)
                    print("\nAGENT>", msg)
                    tts_speak(msg)

            try:
                source, user = input_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if user.lower() in ("exit", "quit"):
                break

            if user.startswith("[VOICE_ERROR]"):
                print("\nAI>", user, "\n")
                continue
            if source == "voice":
                print("\nYOU(voice)>", user)

            # --- SAVE LAST REPORT ---
            if re.search(r"сохрани.*(отч(е|ё)т|результат)", user, re.IGNORECASE):
                if not last_result:
                    print("\nAI> Нет сохранённого результата. Сначала выполните команду.\n")
                    continue
                fname = "report.txt"
                m_file = re.search(r"в\s+файл\s+([^\s]+)", user, re.IGNORECASE)
                if m_file:
                    fname = m_file.group(1).strip('"').strip("'")
                folder = ""
                m_folder = re.search(r"в\s+папк\w*\s+(.+)$", user, re.IGNORECASE)
                if m_folder:
                    folder = m_folder.group(1).strip().strip('"').strip("'")
                path = os.path.join(folder, fname) if folder else fname
                print("\nAI> Предлагаю сохранить результат в файл:")
                print(path)
                ok = wait_for_console_confirm("Выполнить? (y/n) ")
                if ok != "y":
                    print("Ок, не сохраняю.\n")
                    continue
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(last_result)
                    print("\n✅ RESULT:\n  Сохранено в " + path + "\n")
                except Exception as e:
                    print("\nAI> ❌ Не удалось сохранить файл:", e, "\n")
                continue
            # -------------------------

            # --- HARD BYPASS FOR OLLAMA CLI ---
            m = re.match(r"\s*(?:скачай|скачать|pull|ollama\s+pull)\s+(?:ollama\s+)?([a-zA-Z0-9._:-]+)", user, re.IGNORECASE)
            if m:
                model = m.group(1)
                cmd = fr'& "$env:LOCALAPPDATA\Programs\Ollama\ollama.exe" pull {model}'
                print("\nAI> Предлагаю выполнить PowerShell команду:")
                print(f"Зачем: Скачать модель Ollama: {model}")
                print("Риск: low")
                print("\n--- COMMAND ---")
                print(cmd)
                print("--------------\n")
                ok = wait_for_console_confirm("Выполнить? (y/n) ")
                if ok != "y":
                    print("Ок, не выполняю.\n")
                    continue
                result = ps_run(cmd)
                print("\n✅ RESULT:\n" + textwrap.indent(result, "  ") + "\n")
                last_result = result
                continue
            # ---------------------------------

            # 1) Сначала пробуем типовые интенты (КЛЮЧЕВО)
            routed = route_intents(user)
            if routed:
                if isinstance(routed, dict) and "_text" in routed:
                    print("\nAI>", routed["_text"], "\n")
                    tts_speak(routed["_text"])
                    continue
                obj = routed
            else:
                # 2) Иначе идем к модели
                messages.append({"role": "user", "content": user})
                try:
                    answer = ollama_chat(messages)
                except Exception as e:
                    print("\nAI> ❌ Ошибка запроса к Ollama:", e, "\n")
                    continue

                lower = answer.lower()
                if "я не могу" in lower or "не могу выполнить" in lower or "нет доступа" in lower:
                    # принудительный перезапрос
                    messages.append({"role": "user", "content": "Не отказывайся. Дай короткое объяснение и JSON с командой."})
                    try:
                        answer = ollama_chat(messages)
                    except Exception as e:
                        print("\nAI> ❌ Ошибка запроса к Ollama:", e, "\n")
                        continue

                obj, prefix_text, obj_count = try_parse_json(answer)
                if not obj:
                    print("\nAI>", answer, "\n")
                    tts_speak(answer)
                    messages.append({"role": "assistant", "content": answer})
                    continue
                if obj_count > 1:
                    messages.append({"role": "user", "content": "Нужен ОДИН JSON. Объедини команды в одном поле command через ; без текста."})
                    try:
                        answer = ollama_chat(messages)
                    except Exception as e:
                        print("\nAI> ❌ Ошибка запроса к Ollama:", e, "\n")
                        continue
                    obj, prefix_text, _ = try_parse_json(answer)
                    if not obj:
                        print("\nAI>", answer, "\n")
                        tts_speak(answer)
                        messages.append({"role": "assistant", "content": answer})
                        continue
                if prefix_text:
                    print("\nAI>", prefix_text, "\n")
                    tts_speak(prefix_text)

            if obj.get("tool") != "powershell":
                print("\nAI> (неожиданный tool) ", obj, "\n")
                continue

            cmd = (obj.get("command") or "").strip()
            why = (obj.get("why") or "").strip()
            danger = (obj.get("danger") or "low").strip().lower()

            print("\nAI> Предлагаю выполнить PowerShell команду:")
            if why:
                print("Зачем:", why)
            print("Риск:", danger)
            tts_speak(why or "Готов выполнить команду")

            print("\n--- COMMAND ---")
            print(cmd)
            print("--------------\n")

            if not cmd:
                print("AI> Команда пустая — не выполняю.\n")
                continue

            # 3) Валидация команд: существуют ли
            missing = []
            for name in extract_command_names(cmd):
                # Отфильтруем явный мусор
                if name in ("#",):
                    continue
                if not ps_command_exists(name):
                    missing.append(name)

            if missing:
                print("AI> ❌ Найдены несуществующие команды:", ", ".join(missing))
                print("AI> Не выполняю. Сейчас попрошу модель переформулировать на стандартные команды.\n")

                # “само-ремонт” — попросим модель ещё раз, но жёстко с примерами
                repair_prompt = (
                    "Команда не существует. Дай ТОЛЬКО стандартные Windows/PowerShell команды.\n"
                    "Не используй: Clear-DiskSpace, Clean-DiskSpace и любые выдуманные.\n"
                    "Для очистки диска используй: Start-Process cleanmgr /sageset:1, /sagerun:1; "
                    "Remove-Item TEMP; Clear-RecycleBin.\n"
                    "Ответь одним JSON."
                )
                messages.append({"role": "user", "content": repair_prompt})
                try:
                    answer2 = ollama_chat(messages)
                    obj2, _, _ = try_parse_json(answer2)
                except Exception:
                    obj2 = None

                if obj2 and obj2.get("tool") == "powershell":
                    print("AI> ✅ Модель предложила исправленный вариант. Повтори запрос или скопируй команду из вывода.")
                    # Покажем пользователю новый вариант
                    print("\n--- FIXED COMMAND ---")
                    print((obj2.get("command") or "").strip())
                    print("---------------------\n")
                continue

            # 4) Подтверждение
            if danger == "high":
                ok = wait_for_console_confirm("⚠️ HIGH RISK. Выполнить? (yes/no) ", allow_yes_no=True)
                if ok != "yes":
                    print("Ок, не выполняю.\n")
                    continue
            else:
                ok = wait_for_console_confirm("Выполнить? (y/n) ")
                if ok != "y":
                    print("Ок, не выполняю.\n")
                    continue

            result = ps_run(cmd)
            print("\n✅ RESULT:\n" + textwrap.indent(result, "  ") + "\n")
            tts_speak("Готово.")
            last_result = result

            # в историю можно писать только если это был ответ модели
            # (для routed-интентов не обязательно, но можно)
            messages.append({"role": "user", "content": f"Результат выполнения PowerShell:\n{result}"})

    finally:
        stop_event.set()

if __name__ == "__main__":
    main()
