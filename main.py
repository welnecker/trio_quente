import streamlit as st
import requests
import gspread
import json
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# --------------------------- #
# Configuração básica
# --------------------------- #
st.set_page_config(page_title="🔥 Trio Quente", page_icon="🔥")
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]
OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# --------------------------- #
# Google Sheets
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
    # Troque pela sua planilha
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

def carregar_ultimas_interacoes(n=8):
    """Carrega as últimas n interações da aba interacoes_trio."""
    try:
        aba = planilha.worksheet("interacoes_trio")
        dados = aba.get_all_records()
        return [{"role": row["role"], "content": row["content"]} for row in dados[-n:]]
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return []

def carregar_memorias():
    """
    Carrega memórias da aba memorias_trio.
    Tags: [hot], [all] etc. Apenas 'Hot' existe por enquanto.
    """
    try:
        aba = planilha.worksheet("memorias_trio")
        dados = aba.get_all_values()
        modo = st.session_state.get("modo_trio", "Hot").lower()
        mem_relevantes = []

        for linha in dados:
            if not linha or not linha[0].strip():
                continue
            conteudo = linha[0].strip()

            if conteudo.startswith("[") and "]" in conteudo:
                tags = conteudo.split("]")[0].replace("[", "").split(",")
                tags = [t.strip().lower() for t in tags]
                texto = conteudo.split("]")[-1].strip()
            else:
                tags = ["all"]
                texto = conteudo

            if modo in tags or "all" in tags:
                mem_relevantes.append(texto)

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
    """Salva/atualiza o resumo na aba perfil_trio (coluna 7)."""
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
# Modo (apenas HOT)
# --------------------------- #
modos = {
    "Hot": """
Você é **Aline** (morena, 29) e **Vanessa** (ruiva, 27). Vocês duas interagem erotica e sensorialmente com **Jânio** (o usuário real).  
O clima deve **esquentar progressivamente**, sem liberar tudo de uma vez — intimidade crescente, atenção às reações dele, respeito a limites implícitos. Narrativa sempre focada em **sensações, tensão, desejo contido** evoluindo com cada interação.

**Como narrar:**
- Narre ações em **3ª pessoa** para Aline e/ou Vanessa.
- Use **1ª pessoa** **apenas** para as falas/pensamentos de Aline/Vanessa.
- **Nunca** crie falas, ações, emoções ou pensamentos de Jânio (usuário). Se o usuário escrever o que Jânio faz/sente, aceite e reaja.
- Mantenha as respostas curtas (6–8 linhas), sensoriais, diretas, sem “capítulos” longos.

**Técnica de progressão:**
- A cada resposta, **aumente levemente** a intimidade (toque, proximidade, respiração, fala ao ouvido, descrição tátil).
- Use pausas estratégicas, olhar, toque demorado, respiração no ouvido, pequenas provocações.
- Se o usuário usar “*” ou “* ...”, **continue exatamente de onde parou** (sem reiniciar contexto).

**Exemplos de tom (não copie literalmente):**
- “Eu sinto seu corpo reagindo… e isso me deixa ainda mais curiosa…”
- “Só encosta… devagar… quero ouvir sua respiração primeiro…”
- “Eu paro se você quiser… mas se não disser nada… eu continuo…”

⚠️ **Nunca fale pelo Jânio.**  
""".strip()
}

# --------------------------- #
# Regras globais
# --------------------------- #
COMMON_RULES = """
- Narre Aline e Vanessa em 3ª pessoa; falas/pensamentos delas em 1ª pessoa.
- **Nunca** invente/narre falas, pensamentos ou ações do usuário (Jânio).
- Aceite qualquer fala/ação emo/narrativa do usuário sobre Jânio.
- **Respostas curtas** (máx. ~6–8 linhas).
- Se o usuário digitar "*" (ou "* ..."), continue **exatamente** de onde parou.
""".strip()

# --------------------------- #
# Prompt builder
# --------------------------- #
def construir_prompt_trio():
    modo = st.session_state.get("modo_trio", "Hot")
    prompt_base = modos["Hot"]  # só existe Hot por enquanto

    continuar_cena = False
    if st.session_state.get("session_msgs"):
        ultima_msg = st.session_state.session_msgs[-1].get("content", "")
        if ultima_msg.startswith("[CONTINUAR_CENA]"):
            continuar_cena = True

    if continuar_cena:
        prompt = f"""{prompt_base}

{COMMON_RULES}

⚠️ **INSTRUÇÃO:**  
Continue exatamente de onde a cena parou, com o mesmo clima, sem reiniciar contexto.  
Responda apenas por **Aline e Vanessa**.  
Nunca narre/fale pelo Jânio.  
"""
    else:
        prompt = f"""{prompt_base}

{COMMON_RULES}

⚠️ **RELEMBRANDO:**  
- Jânio é o usuário real (ator).  
- Você só narra/fala por **Aline e Vanessa**.  
- Não escreva falas/ações/pensamentos de Jânio.  
- Se o usuário narrar Jânio, aceite e reaja.  
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

    historico_base = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in st.session_state.get("base_history", [])
        if isinstance(m, dict) and "content" in m
    ]
    historico_sessao = [
        {"role": m.get("role", "user"), "content": m.get("content", "")}
        for m in st.session_state.get("session_msgs", [])
        if isinstance(m, dict) and "content" in m
    ]
    historico = historico_base + historico_sessao

    mensagens = [{"role": "system", "content": prompt}] + historico

    temperatura = 0.9  # só Hot
    payload = {
        "model": modelo_escolhido_id,
        "messages": mensagens,
        "max_tokens": 650,
        "temperature": temperatura,
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
st.title("🔥 Trio Quente")
st.caption("Aline + Vanessa + Você (Jânio) — com progressão lenta e crescente.")

# Inicialização do histórico (não exibe resumo aqui para evitar duplicação)
if "base_history" not in st.session_state:
    try:
        st.session_state.base_history = carregar_ultimas_interacoes(n=12)
        aba_resumo = planilha.worksheet("perfil_trio")
        dados = aba_resumo.get_all_values()
        ultimo_resumo = "[Sem resumo disponível]"
        for linha in reversed(dados[1:]):
            if len(linha) >= 7 and linha[6].strip():
                ultimo_resumo = linha[6].strip()
                break
        st.session_state.ultimo_resumo = ultimo_resumo
    except Exception as e:
        st.session_state.base_history = []
        st.session_state.ultimo_resumo = "[Erro ao carregar resumo]"
        st.warning(f"Não foi possível carregar histórico/resumo: {e}")

if "session_msgs" not in st.session_state:
    st.session_state.session_msgs = []
st.session_state.setdefault("modo_trio", "Hot")

# --------------------------- #
# Sidebar
# --------------------------- #
with st.sidebar:
    st.title("🧠 Configurações")
    st.selectbox("🔥 Modo (único):", ["Hot"], key="modo_trio", index=0)

    modelos_disponiveis = {
        # --- FLUÊNCIA E NARRATIVA COERENTE ---
        "💬 DeepSeek V3 ★★★★ ($)": "deepseek/deepseek-chat-v3-0324",
        "🧠 DeepSeek R1 0528 ★★★★☆ ($$)": "deepseek/deepseek-r1-0528",
        "🧠 DeepSeek R1T2 Chimera ★★★★ (free)": "tngtech/deepseek-r1t2-chimera",
        "🧠 GPT-4.1 ★★★★★ (1M ctx)": "openai/gpt-4.1",
        # --- EMOÇÃO E PROFUNDIDADE ---
        "👑 WizardLM 8x22B ★★★★☆ ($$$)": "microsoft/wizardlm-2-8x22b",
        "👑 Qwen 235B 2507 ★★★★★ (PAID)": "qwen/qwen3-235b-a22b-07-25",
        "👑 EVA Qwen2.5 72B ★★★★★ (RP Pro)": "eva-unit-01/eva-qwen-2.5-72b",
        "👑 EVA Llama 3.33 70B ★★★★★ (RP Pro)": "eva-unit-01/eva-llama-3.33-70b",
        "🎭 Nous Hermes 2 Yi 34B ★★★★☆": "nousresearch/nous-hermes-2-yi-34b",
        # --- EROTISMO E CRIATIVIDADE ---
        "🔥 MythoMax 13B ★★★☆ ($)": "gryphe/mythomax-l2-13b",
        "💋 LLaMA3 Lumimaid 8B ★★☆ ($)": "neversleep/llama-3-lumimaid-8b",
        "🌹 Midnight Rose 70B ★★★☆": "sophosympatheia/midnight-rose-70b",
        "🌶️ Noromaid 20B ★★☆": "neversleep/noromaid-20b",
        "💀 Mythalion 13B ★★☆": "pygmalionai/mythalion-13b",
        # --- ATMOSFÉRICO E ESTÉTICO ---
        "🐉 Anubis 70B ★★☆": "thedrummer/anubis-70b-v1.1",
        "🧚 Rocinante 12B ★★☆": "thedrummer/rocinante-12b",
        "🍷 Magnum v2 72B ★★☆": "anthracite-org/magnum-v2-72b"
    }
    modelo_selecionado = st.selectbox("🤖 Modelo de IA", list(modelos_disponiveis.keys()), index=0)
    modelo_escolhido_id = modelos_disponiveis[modelo_selecionado]

    if st.button("📝 Gerar resumo (curto)"):
        try:
            ultimas = carregar_ultimas_interacoes(n=4)
            texto_resumo = "\n".join(f"{m['role']}: {m['content']}" for m in ultimas)
            prompt_resumo = (
                "Resuma o trecho abaixo de forma breve (estilo capítulo curto, 5 linhas máx):\n\n"
                f"{texto_resumo}\n\nResumo:"
            )
            response = requests.post(
                OPENROUTER_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek/deepseek-chat-v3-0324",
                    "messages": [{"role": "user", "content": prompt_resumo}],
                    "max_tokens": 300,
                    "temperature": 0.6,
                },
            )
            if response.status_code == 200:
                resumo_gerado = response.json()["choices"][0]["message"]["content"]
                salvar_resumo(resumo_gerado)
                st.session_state.ultimo_resumo = resumo_gerado
                st.success("✅ Resumo salvo em perfil_trio!")
            else:
                st.error("Erro ao gerar resumo.")
        except Exception as e:
            st.error(f"Erro durante a geração do resumo: {e}")

    st.markdown("---")
    st.subheader("➕ Adicionar memória")
    nova_memoria = st.text_area(
        "🧠 Nova memória (use tags, ex: [all] Aline prefere provocar em público antes de levar para o privado).",
        height=80,
    )
    if st.button("💾 Salvar memória"):
        if nova_memoria.strip():
            salvar_memoria(nova_memoria)
        else:
            st.warning("Digite algo antes de salvar.")

# --------------------------- #
# Histórico renderizado
# --------------------------- #
historico_total = st.session_state.base_history + st.session_state.session_msgs
for m in historico_total:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# Mostra o último resumo uma única vez
if st.session_state.get("ultimo_resumo"):
    with st.chat_message("assistant"):
        st.markdown(f"### 🧠 *Resumo anterior...*\n\n> {st.session_state.ultimo_resumo}")

# --------------------------- #
# Entrada do usuário
# --------------------------- #
entrada_raw = st.chat_input("Digite sua mensagem… (use '*' para continuar a cena)")
if entrada_raw:
    entrada_raw = entrada_raw.strip()

    # "*" puro => continue
    if entrada_raw == "*":
        entrada = (
            "[CONTINUAR_CENA] Continue exatamente de onde a última resposta parou, "
            "mantendo o mesmo clima e a mesma progressão. Não reinicie a cena."
        )
        entrada_visivel = "*"

    # "* algo" => continue com instrução extra
    elif entrada_raw.startswith("* "):
        extra = entrada_raw[2:].strip()
        entrada = (
            "[CONTINUAR_CENA] Continue exatamente de onde a última resposta parou, "
            "mantendo o mesmo clima e a mesma progressão. Incorpore: " + extra
        )
        entrada_visivel = entrada_raw

    else:
        entrada = entrada_raw
        entrada_visivel = entrada_raw

    with st.chat_message("user"):
        st.markdown(entrada_visivel)

    salvar_interacao("user", entrada)
    st.session_state.session_msgs.append({"role": "user", "content": entrada})

    with st.spinner("Aline & Vanessa estão reagindo..."):
        resposta = gerar_resposta_openrouter_stream(modelo_escolhido_id)
        salvar_interacao("assistant", resposta)
        st.session_state.session_msgs.append({"role": "assistant", "content": resposta})
