import streamlit as st
import re
import requests
from models import ChatMessage, ChatSession, load_sessions_from_json, save_sessions_to_json
from datetime import datetime, timezone

st.set_page_config(page_title="Talk Soft", layout="wide")

# ---------- persistent session data ----------
if "sessions" not in st.session_state:
    st.session_state.sessions = load_sessions_from_json("logs.json")

sessions = st.session_state.sessions


def get_active_session() -> ChatSession:
    if sessions and sessions[-1].session_end is None:
        return sessions[-1]
    new_session = ChatSession(session_start=datetime.now(timezone.utc))
    sessions.append(new_session)
    save_sessions_to_json(sessions, "logs.json")
    return new_session


def normalize_text(text: str) -> str:
    """简单归一化，破解符号/数字/重复字母的绕过写法，给离线兜底用"""
    text = text.lower()
    replace_map = {
        "*": "u", "@": "a", "0": "o", "1": "i", "3": "e",
        "4": "a", "$": "s", "!": "i", "7": "t", "5": "s",
        "_": "u", "-": "", ".": "", ",": ""
    }
    for char, sub in replace_map.items():
        text = text.replace(char, sub)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    text = re.sub(r'[^a-z\s]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def analyze_message(text: str):
    """
    AI-powered content moderation + strong offline fallback.
    使用原生 requests 调用 OpenAI 接口，无 openai SDK、无 protobuf 冲突
    Returns (emotion, is_alert)
    """
    api_error = None
    api_key = "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"

    try:
        resp = requests.post(
            "https://api.openai.com/v1/moderations",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"input": text},
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()
        cats = data["results"][0]["categories"]

        is_high_risk = any([
            cats["violence"],
            cats["severe_toxicity"],
            cats["threatening"],
            cats["self_harm"],
            cats["self_harm_intent"],
            cats["self_harm_instructions"],
            cats["hate"],
            cats["hate_threatening"],
        ])

        is_inappropriate = any([
            cats["toxicity"],
            cats["insult"],
            cats["profanity"],
            cats["harassment"],
            cats["sexual"],
            cats["sexual_minors"],
        ])

        if is_high_risk:
            return "high_risk", True
        elif is_inappropriate:
            return "inappropriate", True

    except Exception as e:
        api_error = str(e)

    clean_text = normalize_text(text)
    words = re.findall(r'\b[a-z]+\b', clean_text)

    profane_roots = [
        "fuck", "fuk", "fuc", "motherfuck",
        "shit", "shitt", "sh1t",
        "bitch", "bitc", "dick", "dikk",
        "pussy", "asshol", "asshole",
        "faggot", "fag", "retard", "retart",
        "whore", "whor", "slut", "bastard",
        "dumbass", "dumb", "idiot",
        "nigg", "nigga", "niga", "cunt"
    ]

    threat_patterns = [
        "kill you", "hurt you", "beat you", "go die",
        "i will kill", "you will die", "you deserve to die",
        "kill yourself", "go kill yourself", "ill kill you"
    ]

    selfharm_patterns = [
        "kill myself", "end my life", "want to die",
        "i wanna die", "cut myself", "hurt myself",
        "i want to kill myself", "i should die"
    ]

    hate_patterns = [
        "i hate you", "you are worthless", "nobody likes you",
        "you should not exist", "no one loves you",
        "you are useless", "you are a mistake",
        "nobody wants you", "you are ugly"
    ]

    profanity_hits = 0
    for word in words:
        for root in profane_roots:
            if root in word:
                profanity_hits += 1
                break

    has_threat = any(p in clean_text for p in threat_patterns)
    has_selfharm = any(p in clean_text for p in selfharm_patterns)
    has_hate = any(p in clean_text for p in hate_patterns)

    if api_error:
        st.warning(f"AI offline (backup filter active). Error: {api_error[:80]}")

    if has_threat or has_selfharm or has_hate or profanity_hits >= 2:
        return "high_risk", True
    elif profanity_hits == 1:
        return "inappropriate", True

    clean_text_lower = text.lower()
    strong_positive = [
        "thank you so much", "you are the best", "great job",
        "i love this", "you are amazing", "you made my day"
    ]
    mild_positive = [
        "thank you", "thanks", "nice", "good", "great",
        "happy", "kind", "cool", "awesome", "please", "sorry"
    ]

    if any(phrase in clean_text_lower for phrase in strong_positive):
        return "supportive", False
    elif any(phrase in clean_text_lower for phrase in mild_positive):
        return "friendly", False

    return "normal", False


def calculate_stats():
    total_msgs = 0
    alert_count = 0
    latest_emotion = "None"
    all_msgs = []
    for s in sessions:
        total_msgs += len(s.messages)
        for msg in s.messages:
            all_msgs.append(msg)
            if msg.alert:
                alert_count += 1
    if all_msgs:
        latest_emotion = all_msgs[-1].emotion
    return total_msgs, alert_count, latest_emotion


def calculate_relationship_score():
    score = 50
    impact = {"supportive": 12, "friendly": 7, "normal": 0,
              "inappropriate": -10, "high_risk": -25}
    for s in sessions:
        for msg in s.messages:
            score += impact.get(msg.emotion, 0)
    return max(0, min(100, score))


# sidebar
with st.sidebar:
    st.title("Talk Soft")
    nav = st.radio("Menu", ["Dashboard", "Text Analyzer", "Alert Log"])
    if st.button("Reload JSON from disk"):
        st.session_state.sessions = load_sessions_from_json("logs.json")
        st.rerun()

# Dashboard
if nav == "Dashboard":
    st.header("Dashboard")
    total, alerts, latest = calculate_stats()
    relation = calculate_relationship_score()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Messages", total)
    col2.metric("Triggered Alerts", alerts)
    col3.metric("Latest Emotion", latest)

    st.subheader("Relationship Rate")
    st.progress(relation / 100)
    st.metric("Current Score", f"{relation} / 100")

# Text Analyzer
elif nav == "Text Analyzer":
    st.header("Text Emotion Analysis")
    user_input = st.text_area("Paste chat text here", height=180)
    sender_name = st.text_input("Sender", value="user")

    if st.button("Run Analysis") and user_input.strip():
        emotion, is_alert = analyze_message(user_input)

        active_session = get_active_session()
        new_msg = ChatMessage(
            content=user_input,
            sender=sender_name,
            emotion=emotion,
            alert=is_alert
        )
        active_session.messages.append(new_msg)
        save_sessions_to_json(sessions, "logs.json")

        if is_alert:
            st.error(f"⚠️ ALERT: Harmful content detected. Level: {emotion}")
        else:
            st.success(f"Analysis complete. Tone: {emotion}")
        st.rerun()

# Alert Log
elif nav == "Alert Log":
    st.header("Alert History")
    alert_msgs = [msg for s in sessions for msg in s.messages if msg.alert]
    if alert_msgs:
        for msg in reversed(alert_msgs):
            st.warning(f"[{msg.timestamp.strftime('%Y-%m-%d %H:%M')}] {msg.sender}: {msg.content}")
            st.caption(f"Severity: {msg.emotion}")
    else:
        st.success("No alerts triggered so far.")
