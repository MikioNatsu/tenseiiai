import requests
import json
import time
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import cast

from rag import retrieve
from memory import init_db, get_user, upsert_user, add_message, last_messages
from behavior import build_yuki_injection

OLLAMA_BASE = "http://localhost:11434"
CHAT_MODEL = "llama3.1:8b"  # xohlasang o'zgartirasan


def ollama_chat(messages, model=CHAT_MODEL) -> str:
    print("OLLAMA_CHAT: timeout=(10,600)")
    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/chat",
            json={
                "model": model,
                "messages": messages,
                "stream": False,
                "options": {"num_predict": 200, "temperature": 0.7},
            },
            timeout=(10, 600),
        )
        r.raise_for_status()
        return r.json()["message"]["content"]
    except requests.exceptions.ReadTimeout:
        raise HTTPException(504, "Ollama timeout: prompt katta yoki model band.")
    except requests.exceptions.ConnectionError:
        raise HTTPException(503, "Ollama ulanmayapti: localhost:11434.")


def load_rules() -> str:
    with open("rules/yuki_rules.md", "r", encoding="utf-8") as f:
        return f.read()


app = FastAPI(title="YUKI AI Core")


class ChatIn(BaseModel):
    user_id: str
    text: str
    nickname: str | None = None
    premium: bool | None = None


@app.on_event("startup")
def _startup():
    init_db()


@app.post("/chat")
def chat(inp: ChatIn):
    import time

    def stamp(label: str, t_prev: float) -> float:
        t_now = time.perf_counter()
        print(f"{label}: {t_now - t_prev:.3f}s")
        return t_now

    t0 = time.perf_counter()

    # --- user state ---
    u = get_user(inp.user_id)
    if not u:
        upsert_user(
            inp.user_id,
            nickname=inp.nickname or "Otaku",
            premium=inp.premium or False,
        )
        u = get_user(inp.user_id)
    else:
        if inp.nickname is not None:
            upsert_user(inp.user_id, nickname=inp.nickname)
        if inp.premium is not None:
            upsert_user(inp.user_id, premium=inp.premium)
        u = get_user(inp.user_id)
    u = cast(dict, u)
    nickname = u.get("nickname") or "Otaku"
    premium = bool(u.get("premium"))
    t0 = stamp("T(user_state)", t0)

    # --- contexts ---
    rules = load_rules()
    t0 = stamp("T(load_rules)", t0)

    inj = build_yuki_injection(max_examples_total=6)
    t0 = stamp("T(build_injection)", t0)

    # --- RAG context ---
    kb_hits = retrieve(inp.text, k=4)
    kb_context = "\n\n---\n\n".join(kb_hits) if kb_hits else ""

    MAX_KB_CHARS = 2000
    if kb_context and len(kb_context) > MAX_KB_CHARS:
        kb_context = kb_context[:MAX_KB_CHARS] + "\n...[KB_TRUNCATED]"
    t0 = stamp("T(retrieve)", t0)

    # --- conversation history ---
    history = last_messages(inp.user_id, limit=8)
    t0 = stamp("T(history)", t0)

    # store user message
    add_message(inp.user_id, "user", inp.text)
    t0 = stamp("T(store_user_msg)", t0)

    # --- system message ---
    system_msg = f"""{rules}

{inj["style_guide"]}

{inj["few_shot"]}

USER_STATE:
- nickname: {nickname}
- premium: {premium}

IMPORTANT:
- Always stay in YUKI persona and follow YUKI STYLE.
- Spoilers: do NOT reveal by default. If user asks, request confirmation first.
- In serious support/payment/rules topics: be concise and avoid emojis.
"""
    t0 = stamp("T(build_system_msg)", t0)

    # --- build chat messages ---
    messages = [{"role": "system", "content": system_msg}]

    if history:
        # Safety: ensure history is in correct format
        # Expected: [{"role":"user","content":"..."}, {"role":"assistant","content":"..."}]
        if isinstance(history, list) and history and isinstance(history[0], dict):
            messages += history

    if kb_context:
        messages.append(
            {
                "role": "system",
                # yumshoqroq: KB har doim 100% fact emas
                "content": f"KNOWLEDGE_BASE_CONTEXT (optional reference):\n{kb_context}",
            }
        )

    messages.append({"role": "user", "content": inp.text})
    t0 = stamp("T(build_messages)", t0)

    # debug sizes
    msg_chars = sum(len(m.get("content", "")) for m in messages)
    sys_chars = (
        len(messages[0]["content"])
        if messages and messages[0]["role"] == "system"
        else 0
    )
    print("MSG_COUNT:", len(messages))
    print("MSG_CHARS:", msg_chars)
    print("FIRST_SYS_CHARS:", sys_chars)

    # --- model call ---
    answer = ollama_chat(messages)
    t0 = stamp("T(ollama_chat)", t0)

    # store assistant message
    add_message(inp.user_id, "assistant", answer)
    t0 = stamp("T(store_assistant_msg)", t0)

    return {"answer": answer, "nickname": nickname, "premium": premium}
