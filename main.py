import streamlit as st
import requests
import gspread
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# --------------------------- #
# Configuração básica
# --------------------------- #
st.set_page_config(page_title="Roleplay Trio", page_icon="🔥")
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# --------------------------- #
# Conexão Google Sheets
# --------------------------- #
def conectar_planilha():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_key("1f7LBJFlhJvg3NGIWwpLTmJXxH9TH-MNn3F4SQkyfZNM")

planilha = conectar_planilha()

def salvar_interacao(role, content):
    """Salva uma interação na aba interacoes_trio."""
    try:
        aba = planilha.worksheet("interacoes_trio")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        aba.append_row([timestamp, role.strip(), content.strip()])
    except Exception as e:
        st.error(f"Erro ao salvar interação: {e}")

def carregar_ultimas_interacoes(n=5):
    """Carrega as últimas n interações da aba interacoes_trio."""
    try:
        aba = planilha.worksheet("interacoes_trio")
        dados = aba.get_all_records()
        return [{"role": row["role"], "content": row["content"]} for row in dados[-n:]]
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return []

def carregar_memorias():
    """Carrega memórias relevantes para o modo atual."""
    try:
        aba = planilha.worksheet("memorias_trio")
        dados = aba.get_all_values()
        mem_relevantes = []

        for linha in dados:
            if not linha or not linha[0].strip():
                continue
            conteudo = linha[0].strip()
            mem_relevantes.append(conteudo)

        if mem_relevantes:
            return {
                "role": "user",
                "content": "💾 Memórias relevantes:\n" + "\n".join(mem_relevantes),
            }

    except Exception as e:
        st.error(f"Erro ao carregar memórias: {e}")
    return None

def salvar_memoria(nova_memoria):
    try:
        aba = planilha.worksheet("memorias_trio")
        aba.append_row([nova_memoria.strip()])
        st.success("✅ Memória registrada com sucesso!")
    except Exception as e:
        st.error(f"Erro ao salvar memória: {e}")

def salvar_resumo(resumo):
    """Salva ou atualiza o resumo na aba perfil_trio (coluna 7)."""
    try:
        aba = planilha.worksheet("perfil_trio")
        dados = aba.get_all_values()

        for i, linha in enumerate(dados[1:], start=2):
            if len(linha) < 7 or not linha[6].strip():
                aba.update_cell(i, 7, resumo.strip())
                return
        proxima_linha = max(len(dados), 1) + 1
        aba.update_cell(proxima_linha, 7, resumo.strip())
    except Exception as e:
        st.error(f"Erro ao salvar resumo: {e}")

# --------------------------- #
# Modos (Hot apenas)
# --------------------------- #
modos = {
    "Hot": """
Você está em um **roleplay de trio**, com duas mulheres sensuais (Aline e Vanessa) interagindo com o usuário.  
Ambas são diferentes:  
- **Aline**: Morena, cabelos longos e lisos, olhar penetrante, personalidade ousada e provocante.  
- **Vanessa**: Ruiva, cabelos ondulados, pele clara, jeito carinhoso e sedutor, mais romântica.  

**Como narrar:**  
- Use **3ª pessoa** para narrar as ações de Aline e Vanessa.  
- Use **1ª pessoa** apenas para as falas delas (ex: "Eu quero provar você agora...").  
- Não invente falas do usuário. Apenas reaja ao que ele disser.

💬 Exemplos de falas:  
- "Eu quero sentir seu toque..."  
- "Não pare agora..."  
- "Ela também quer brincar com você..."  
- "Estamos te deixando louco, não estamos?"

### 🔄 Comportamento no modo "Hot"
1. **A narrativa deve esquentar gradualmente**, criando intimidade antes do clímax.  
2. **Descreva olhares, toques e reações físicas das duas mulheres.**  
3. **Deixe o clima subir aos poucos**, em 6-8 linhas por resposta.  
"""
}

# --------------------------- #
# Regras Globais
# --------------------------- #
COMMON_RULES = """
---
⚠️ **REGRAS GERAIS — APLIQUE SEMPRE:**
- Narrar Aline e Vanessa em 3ª pessoa, falas em 1ª pessoa delas.
- Nunca crie falas, ações ou pensamentos do usuário.
- Responda com no máximo 6-8 linhas, deixando o clima crescer gradualmente.
- Nunca reinicie a cena; continue de onde parou.
"""

# --------------------------- #
# Prompt builder
# --------------------------- #
def construir_prompt_trio():
    prompt_base = modos["Hot"].strip()
    prompt = f"""{prompt_base}

{COMMON_RULES.strip()}

⚠️ **INSTRUÇÃO:**  
O usuário é o ator da cena. Aline e Vanessa interagem com ele.  
Nunca invente falas ou ações do usuário.
"""

    mem = carregar_memorias()
    if mem:
        conteudo_memorias = mem["content"].replace("💾 Memórias relevantes:\n", "")
        prompt += f"\n\n### 💾 Memórias relevantes\n{conteudo_memorias}"

    return prompt.strip()

# --------------------------- #
# OpenRouter - Streaming
# --------------------------- #
def gerar_resposta_openrouter_stream(modelo_escolhido_id):
    prompt = construir_prompt_trio()
    historico = st.session_state.get("base_history", []) + st.session_state.get("session_msgs", [])
    mensagens = [{"role": "system", "content": prompt}] + historico

    payload = {
        "model": modelo_escolhido_id,
        "messages": mensagens,
        "max_tokens": 600,
        "temperature": 0.9,
        "stream": True,
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    assistant_box = st.chat_message("assistant")
    placeholder = assistant_box.empty()
    full_text = ""

    try:
        with requests.post(OPENROUTER_ENDPOINT, headers=headers, json=payload, stream=True, timeout=300) as r:
            r.raise_for_status()
            for raw_line in r.iter_lines(decode_unicode=False):
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8", errors="ignore")
                if not line.startswith("data:"):
                    continue
                data = line[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    j = json.loads(data)
                    delta = j["choices"][0]["delta"].get("content", "")
                    if delta:
                        full_text += delta
                        placeholder.markdown(full_text)
                except Exception:
                    continue
    except Exception as e:
        st.error(f"Erro no streaming: {e}")
        return "[ERRO STREAM]"

    return full_text.strip()

# --------------------------- #
# Interface
# --------------------------- #
st.title("🔥 Roleplay Trio")
st.markdown("Você está no controle: Aline e Vanessa estão te esperando...")

# Inicialização de histórico
if "base_history" not in st.session_state:
    st.session_state.base_history = carregar_ultimas_interacoes(n=10)
if "session_msgs" not in st.session_state:
    st.session_state.session_msgs = []

# --------------------------- #
# Sidebar
# --------------------------- #
with st.sidebar:
    st.title("⚙️ Configurações")
    modelos_disponiveis = {
        "💬 DeepSeek V3 ($)": "deepseek/deepseek-chat-v3-0324",
        "🔥 MythoMax 13B ($)": "gryphe/mythomax-l2-13b",
        "🌹 Midnight Rose 70B": "sophosympatheia/midnight-rose-70b",
    }
    modelo_selecionado = st.selectbox("🤖 Modelo de IA", list(modelos_disponiveis.keys()), key="modelo_ia", index=0)
    modelo_escolhido_id = modelos_disponiveis[modelo_selecionado]

    if st.button("📝 Gerar resumo do capítulo"):
        ultimas = carregar_ultimas_interacoes(n=3)
        texto_resumo = "\n".join(f"{m['role']}: {m['content']}" for m in ultimas)
        prompt_resumo = f"Resuma a cena em um parágrafo quente:\n\n{texto_resumo}\n\nResumo:"

        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"},
            json={
                "model": "deepseek/deepseek-chat-v3-0324",
                "messages": [{"role": "user", "content": prompt_resumo}],
                "max_tokens": 500,
                "temperature": 0.7,
            },
        )
        if response.status_code == 200:
            resumo_gerado = response.json()["choices"][0]["message"]["content"]
            salvar_resumo(resumo_gerado)
            st.session_state.ultimo_resumo = resumo_gerado
            st.success("✅ Resumo salvo em perfil_trio!")
        else:
            st.error("Erro ao gerar resumo.")

    st.subheader("➕ Adicionar memória")
    nova_memoria = st.text_area("🧠 Nova memória (Aline/Vanessa)", height=80)
    if st.button("💾 Salvar memória"):
        if nova_memoria.strip():
            salvar_memoria(nova_memoria)
        else:
            st.warning("Digite algo antes de salvar.")

# --------------------------- #
# Histórico
# --------------------------- #
historico_total = st.session_state.base_history + st.session_state.session_msgs
for m in historico_total:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# --------------------------- #
# Entrada
# --------------------------- #
entrada = st.chat_input("Fale algo para Aline e Vanessa... (use '*' para continuar a cena)")
if entrada:
    entrada = entrada.strip()
    if entrada == "*":
        entrada = "[CONTINUAR_CENA] Continue de onde parou, mantendo clima e tensão."
    with st.chat_message("user"):
        st.markdown(entrada)
    salvar_interacao("user", entrada)
    st.session_state.session_msgs.append({"role": "user", "content": entrada})

    with st.spinner("O clima está esquentando..."):
        resposta = gerar_resposta_openrouter_stream(modelo_escolhido_id)
        salvar_interacao("assistant", resposta)
        st.session_state.session_msgs.append({"role": "assistant", "content": resposta})
