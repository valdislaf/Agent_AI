import json
import os
import re
import sys
import textwrap
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path

import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODELS = [
    "deepseek-coder-v2:latest",
    "llama3.1:8b",
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "gpt-oss:20b",
]
SUMMARY_MODEL = "gpt-oss:20b"
TIMEOUT_SEC = 180
URL_DEBUG = True

SYSTEM_PROMPT = (
    "Ты — полезный ассистент и всегда отвечаешь по‑русски. "
    "Если есть предоставленный контекст (файлы/URL), отвечай, опираясь только на него "
    "и обязательно цитируй короткие фрагменты (в кавычках). "
    "Если в контексте нет данных для ответа — так и скажи."
)


def ollama_chat(messages, model):
    r = requests.post(
        OLLAMA_URL,
        json={"model": model, "messages": messages, "stream": False},
        timeout=TIMEOUT_SEC,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]


def _read_pdf(path: Path, max_chars: int) -> str:
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        try:
            from PyPDF2 import PdfReader  # type: ignore
        except Exception as e:
            raise RuntimeError("PDF reader not installed (pypdf/PyPDF2).") from e
    reader = PdfReader(str(path))
    chunks = []
    total = 0
    for page in reader.pages:
        text = page.extract_text() or ""
        if text:
            chunks.append(text)
            total += len(text)
        if total >= max_chars:
            chunks.append("\n\n[TRUNCATED]")
            break
    return "\n\n".join(chunks)


def read_text_file(path: str, max_chars: int = 200_000) -> str:
    p = Path(path)
    ext = p.suffix.lower()
    if ext == ".pdf":
        return _read_pdf(p, max_chars)
    if ext in (".html", ".htm"):
        raw = p.read_text(encoding="utf-8", errors="ignore")
        text = strip_html(raw)
        if len(text) > max_chars:
            return text[:max_chars] + "\n\n[TRUNCATED]"
        return text
    data = p.read_text(encoding="utf-8", errors="ignore")
    if len(data) > max_chars:
        return data[:max_chars] + "\n\n[TRUNCATED]"
    return data


def fetch_url(url: str, max_chars: int = 200_000) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/120.0 Safari/537.36"
    }
    if URL_DEBUG:
        print(f"[URL] Fetching: {url}")
    r = requests.get(
        url,
        timeout=(5, 8),
        headers=headers,
        proxies={"http": None, "https": None},
        stream=True,
        allow_redirects=True,
    )
    try:
        r.raise_for_status()
        if URL_DEBUG:
            print(f"[URL] Status: {r.status_code}, encoding: {r.encoding}")
        chunks = []
        total = 0
        for chunk in r.iter_content(chunk_size=16384):
            if not chunk:
                continue
            if total == 0 and URL_DEBUG:
                print("[URL] First bytes received")
            chunks.append(chunk)
            total += len(chunk)
            if total >= max_chars:
                break
        raw = b"".join(chunks)
        enc = r.encoding or "utf-8"
        text = raw.decode(enc, errors="ignore")
    finally:
        try:
            r.close()
        except Exception:
            pass
    if URL_DEBUG:
        print(f"[URL] Read bytes: {len(text)}")
    if "<html" in text.lower():
        text = strip_html(text)
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._chunks = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip > 0:
            self._skip -= 1

    def handle_data(self, data):
        if self._skip == 0 and data:
            self._chunks.append(data)

    def get_text(self) -> str:
        return " ".join(self._chunks)


def strip_html(text: str) -> str:
    # HTMLParser avoids catastrophic regex backtracking on large pages.
    parser = _HTMLTextExtractor()
    parser.feed(text)
    parser.close()
    return re.sub(r"\\s+", " ", parser.get_text()).strip()


def normalize_cmd(s: str) -> str:
    return s.strip().lower()


def print_help():
    print(
        textwrap.dedent(
            """
            Commands:
              /help                Show this help
              /exit                Quit
              /clear               Clear conversation history
              /file <path>         Load a local text file into context
              /url <url>           Fetch URL and add its content to context
              /context             Show current context sources
            """
        ).strip()
    )


def main():
    print("Ollama multi-model chat (multiple  models).")
    print("Type /help for commands.\n")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    context_sources = []
    rounds_total = 3
    round_index = 1
    next_auto_user = None

    try:
        raw_rounds = input("Сколько раундов обсуждения? (Enter = 3, 0 = бесконечно): ").strip()
        if raw_rounds:
            rounds_total = int(raw_rounds)
            if rounds_total < 0:
                rounds_total = 0
    except Exception:
        rounds_total = 3

    while True:
        if next_auto_user:
            user = next_auto_user.strip()
            next_auto_user = None
        else:
            try:
                user = input("YOU> ").strip()
            except EOFError:
                break

        if not user:
            continue

        cmd = normalize_cmd(user)
        if cmd in ("/exit", "/quit"):
            break
        if cmd == "/help":
            print_help()
            continue
        if cmd == "/clear":
            history = [{"role": "system", "content": SYSTEM_PROMPT}]
            context_sources = []
            print("History cleared.")
            continue
        if cmd.startswith("/file "):
            path = user[6:].strip().strip('"')
            try:
                content = read_text_file(path)
                context_sources.append((f"file:{path}", content))
                print(f"Loaded file: {path}")
            except Exception as e:
                print(f"Failed to read file: {e}")
            continue
        if cmd.startswith("/url "):
            url = user[5:].strip()
            try:
                content = fetch_url(url)
                context_sources.append((f"url:{url}", content))
                print(f"Fetched URL: {url}")
            except Exception as e:
                print(f"Failed to fetch URL: {e}")
            continue
        if cmd == "/context":
            if not context_sources:
                print("No context sources loaded.")
            else:
                for i, (src, _) in enumerate(context_sources, 1):
                    print(f"{i}) {src}")
            continue

        # Auto-load local file path if user mentions it (e.g., "C:\\path\\file.pdf")
        auto_paths = re.findall(r'([A-Za-z]:\\[^\"\\n\\r]+)', user)
        for raw_path in auto_paths:
            path = raw_path.strip().strip('"')
            try:
                if Path(path).exists():
                    content = read_text_file(path)
                    context_sources.append((f"file:{path}", content))
                    print(f"Auto-loaded file: {path}")
            except Exception as e:
                print(f"Failed to auto-load file {path}: {e}")

        context_blob = ""
        if context_sources:
            parts = []
            for src, content in context_sources:
                parts.append(f"[SOURCE {src}]\n{content}")
            context_blob = "\n\n".join(parts)

        if context_blob:
            history.append({
                "role": "user",
                "content": f"Context sources:\n{context_blob}\n\nUser request:\n{user}",
            })
        else:
            history.append({"role": "user", "content": user})

        last_user_text = user

        model_outputs = []
        for model in MODELS:
            try:
                reply = ollama_chat(history, model)
            except Exception as e:
                reply = f"[ERROR] {e}"
            model_outputs.append((model, reply))
            print(f"\n[{model}]\n{reply}\n")

        summary_inputs = []
        for model, reply in model_outputs:
            summary_inputs.append(f"Model {model} response:\n{reply}")
        summary_text = "\n\n".join(summary_inputs)

        summary_prompt = (
            "Ты — финальный модератор. Дай лучший итоговый ответ по-русски, "
            "опираясь ТОЛЬКО на контекст источников и ответы моделей. "
            "Если в контексте нет точных данных — скажи это. "
            "Цитируй короткие фрагменты из контекста в кавычках.\n\n"
            "Discussion:\n"
            f"{summary_text}"
        )

        try:
            final = ollama_chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": summary_prompt},
            ], SUMMARY_MODEL)
        except Exception as e:
            final = f"[ERROR] {e}"

        print(f"\n[{SUMMARY_MODEL} FINAL]\n{final}\n")

        history.append({"role": "assistant", "content": final})

        if rounds_total and round_index >= rounds_total:
            round_index = 1
            next_auto_user = None
            print("\n[Сессия] Готов продолжать. Введите новый запрос.\n")
            continue

        # Moderator asks a follow-up question for the next round.
        moderator_prompt = (
            "Ты — модератор обсуждения. Сформулируй ОДИН короткий вопрос "
            "пользователю по теме, чтобы уточнить задачу и улучшить следующий раунд. "
            "Только вопрос, без пояснений.\n\n"
            f"Последний запрос пользователя:\n{last_user_text}\n\n"
            f"Итог последнего раунда:\n{final}"
        )
        try:
            moderator_question = ollama_chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": moderator_prompt},
                ],
                SUMMARY_MODEL,
            )
        except Exception as e:
            moderator_question = f"[ERROR] {e}"

        moderator_question = moderator_question.strip()
        if moderator_question:
            print(f"\n[MODERATOR]\n{moderator_question}\n")
            history.append({"role": "assistant", "content": moderator_question})
            if rounds_total:
                next_auto_user = moderator_question

        round_index += 1


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
