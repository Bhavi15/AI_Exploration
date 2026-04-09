import json
import streamlit as st
import requests

BRIDGE_URL = "http://localhost:3001"

st.set_page_config(page_title="Copilot Chat", page_icon="💬")
st.title("💬 Copilot Chat (via VS Code Bridge)")

# --- Check if bridge is running ---
try:
    health = requests.get(f"{BRIDGE_URL}/health", timeout=2)
    if health.status_code == 200:
        st.sidebar.success("✅ VS Code Bridge connected")
    else:
        st.sidebar.error("Bridge returned unexpected status")
        st.stop()
except requests.ConnectionError:
    st.error(
        "Cannot connect to VS Code Bridge at localhost:3001.\n\n"
        "Make sure VS Code is open with the Copilot Chat extension running."
    )
    st.stop()

# --- Fetch available models from the bridge ---
try:
    models_resp = requests.get(f"{BRIDGE_URL}/models", timeout=5)
    available_models = models_resp.json()
    model_names = [f"{m['name']} ({m['vendor']}/{m['family']})" for m in available_models]
except Exception:
    available_models = []
    model_names = []

if not model_names:
    st.sidebar.warning("No models found")
    st.stop()

selected_idx = st.sidebar.selectbox("Model", range(len(model_names)), format_func=lambda i: model_names[i])
selected_vendor = available_models[selected_idx]['vendor']
selected_family = available_models[selected_idx]['family']

st.sidebar.caption(f"Vendor: `{selected_vendor}` | Family: `{selected_family}`")

# --- Chat history ---
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# --- Chat input ---
if prompt := st.chat_input("Ask a question..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call the VS Code bridge with SSE streaming
    with st.chat_message("assistant"):
        placeholder = st.empty()

        payload = {
            "question": prompt,
            "vendor": selected_vendor,
            "family": selected_family,
        }

        response = requests.post(
            f"{BRIDGE_URL}/chat",
            json=payload,
            stream=True,
            timeout=60,
        )

        if response.status_code != 200:
            placeholder.error(f"Bridge Error ({response.status_code}): {response.text}")
            st.stop()

        # Stream the SSE response
        full_response = ""
        for line in response.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if not decoded.startswith("data: "):
                continue
            data = decoded[6:]
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
                if "chunk" in chunk:
                    full_response += chunk["chunk"]
                    placeholder.markdown(full_response + "▌")
            except (json.JSONDecodeError, KeyError):
                continue

        placeholder.markdown(full_response)
        st.session_state.messages.append({"role": "assistant", "content": full_response})
