import json
import os
import re
import sys
import textwrap
from datetime import datetime
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

SYSTEM_PROMPT = (
    "Ты — полезный ассистент и всегда отвечаешь по‑русски. "
    "Если просят анализ, ссылайся на конкретные фрагменты из предоставленного контекста "
    "(файлы/URL) и явно отмечай неопределённость."
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
    r = requests.get(url, timeout=TIMEOUT_SEC)
    r.raise_for_status()
    text = r.text
    if len(text) > max_chars:
        return text[:max_chars] + "\n\n[TRUNCATED]"
    return text


def strip_html(text: str) -> str:
    # Basic tag stripper to keep dependencies minimal.
    text = re.sub(r"(?is)<(script|style).*?>.*?</\\1>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = re.sub(r"\\s+", " ", text).strip()
    return text


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
    print("Ollama multi-model chat (4 models).")
    print("Type /help for commands.\n")

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    context_sources = []

    while True:
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
            "You are the final summarizer. Review the discussion and provide the best final answer "
            "in Russian. Be concise, correct, and explicit about any uncertainty.\n\n"
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


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
