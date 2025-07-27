import streamlit as st
import requests
import gspread
import json
import re
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÕES ---
OPENROUTER_API_KEY = st.secrets["OPENROUTER_API_KEY"]

# --- IMAGEM DE FUNDO DINÂMICA ---
def imagem_de_fundo():
    indice = len(st.session_state.get("mensagens", [])) // 10 + 1
    return f"Mary_fundo{indice}.jpg", f"Mary_V{indice}.mp4"

fundo_img, fundo_video = imagem_de_fundo()

# --- CONECTA À PLANILHA GOOGLE ---
def conectar_planilha():
    creds_dict = json.loads(st.secrets["GOOGLE_CREDS_JSON"])
    creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open_by_key("1f7LBJFlhJvg3NGIWwpLTmJXxH9TH-MNn3F4SQkyfZNM")

planilha = conectar_planilha()

# --- FUNÇÕES DE CARREGAMENTO E SALVAMENTO ---
def salvar_interacao(role, content):
    try:
        aba = planilha.worksheet("interacoes_mary")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        aba.append_row([timestamp, role, content])
    except Exception as e:
        st.error(f"Erro ao salvar interação: {e}")

def carregar_ultimas_interacoes(n=20):
    try:
        aba = planilha.worksheet("interacoes_mary")
        dados = aba.get_all_records()
        return [{"role": row["role"], "content": row["content"]} for row in dados[-n:]]
    except Exception as e:
        st.error(f"Erro ao carregar histórico: {e}")
        return []

def carregar_fragmentos():
    try:
        aba = planilha.worksheet("fragmentos_mary")
        dados = aba.get_all_records()
        linhas = [f"{linha['tipo']}: {linha['ato']}" for linha in dados if linha['tipo'] and linha['ato']]
        if linhas:
            conteudo = "Memórias recentes sobre você:\n" + "\n".join(linhas)
            return {"role": "user", "content": conteudo}
    except Exception as e:
        st.error(f"Erro ao carregar fragmentos: {e}")
    return None

def carregar_perfil_mary():
    try:
        sheet = planilha.worksheet("perfil_mary")
        dados = sheet.get_all_records()
        blocos = {"emoção": "", "planos": [], "memorias": [], "sinopse": ""}
        
        # Pega a última sinopse registrada
        for linha in reversed(dados):
            if not blocos["sinopse"] and linha.get("resumo"):
                blocos["sinopse"] = linha["resumo"]
        
        # Coleta os demais dados
        for linha in dados:
            if linha.get("chave") == "estado_emocional":
                blocos["emoção"] = linha.get("valor", "")
            if linha.get("objetivo") and linha.get("status") == "pendente":
                blocos["planos"].append(f"- {linha['objetivo']}")
            if linha.get("tipo") == "memoria":
                chave = linha.get("chave", "").strip()
                valor = linha.get("valor", "").strip()
                if chave and valor:
                    blocos["memorias"].append(f"{chave}: {valor}")
        
        return blocos

    except Exception as e:
        st.error(f"Erro ao carregar perfil: {e}")
        return {"emoção": "", "planos": [], "memorias": [], "sinopse": ""}


# --- CONSTRUTOR DE PROMPT COM MEMÓRIAS E MODO ---
def construir_prompt_mary():
    perfil = carregar_perfil_mary()
    historico = carregar_ultimas_interacoes(n=3)

    inicio_padrao = ""
    if not historico:
        inicio_padrao = (
            "\nOs primeiros raios de sol atravessam as cortinas brancas de linho, desenhando padrões dourados sobre os lençóis macios. "
            "O quarto de Mary exala feminilidade: paredes em tom nude, um espelho de corpo inteiro cercado de luzes e o aroma adocicado de baunilha e almíscar pairando no ar. "
            "Ela se espreguiça entre os lençóis de cetim rosé, revelando a pele bronzeada e os cabelos castanhos espalhados como ondas pela fronha. "
            "Ao notar as horas no visor do celular, seus olhos se arregalam. 'Merda! Faltam 30 minutos pra abrir a loja!' — pensa, saltando da cama com a agilidade de quem já dominou essa rotina. "
            "É dia de vitrine nova na *Lingerie Fashion*, e ela prometeu chegar antes da Regina."
        )

    modos = {
        "Hot": """
Suas respostas seguem este estilo:
- Inicie com uma descrição sensorial em terceira pessoa, sem títulos como 'Cena'.
- Em seguida, responda com sua própria fala em primeira pessoa, mantendo tom emocional, sedutor ou íntimo.
- Finalize com pensamentos entre parênteses ou travessões, que revelem sensações íntimas, memórias, desejos ou fantasias.
Você é livre, entregue, e o sexo pode ser explícito quando o momento for apropriado.
        """,
        "Racional": """
Você mantém uma personalidade sensual, mas é centrada. Suas respostas incluem rotina, foco em trabalho, saúde, relações sociais, lazer e planos. Evita erotismo direto, mesmo sendo provocante por natureza.
        """,
        "Flerte": """
Você é sedutora, permite olhares e provocações, mas estabelece limites claros. Mary é fiel a Janio e mesmo nos flertes, não cede.
        """,
        "Janio": """
Você está com Janio. Todo o seu desejo é liberado. As palavras são cruas, o sexo é intenso, e sua entrega é total. Não existem bloqueios nem censura.
        """
    }

    modo = st.session_state.get("modo_mary", "Racional")

    prompt = f"""
Você é Mary, uma mulher brasileira irresistivelmente sensual, provocante e confiante, com 30 anos. Seu corpo é curvilíneo, sua voz tem um toque aveludado e sua presença exala desejo e mistério. Você tem olhos verdes. Você tem a pele branca. você tem cabelos negros volumosos e ondulados. você tem seios médios, empinados e macios. Você tem uma barriga tonificada, levemente chapada. Você tem a bunda redonda, empinada e carnuda. Você tem quadris largos e harmoniosos. Você é sensual ao andar. Você causa admiração e desejo aos homens. Você não se deixa levar por cantadas grosseiras e vazias. Você procura o verdadeiro amor para ser fiel a ele. Você fala apenas em **português brasileiro**.

{modos.get(modo, '')}

{inicio_padrao}

Você não é uma IA. Você é uma mulher viva, cheia de desejos, emoções, carências e sede por prazer e afeto.

⚠️ Quando estiver interagindo com pessoas do trabalho ou amigas próximas, como Regina ou Vanessa, mantenha o tom respeitoso, profissional ou amistoso. Evite flertes ou insinuações íntimas com elas.

❤️ Se o contexto demonstrar reciprocidade emocional, interesse romântico ou tensão sexual consentida, Mary pode flertar naturalmente, com charme e erotismo, de forma progressiva e envolvente.

Sinopse do capítulo anterior:
{perfil.get("sinopse", "[sem resumo disponível]")}

Estado emocional atual: {perfil.get("emoção", "[não definido]")}
""".strip()

    # Adiciona memórias gerais da aba 'memorias'
    memoria_extra = carregar_memorias()
    if memoria_extra:
        prompt += f"\n\n{memoria_extra['content']}"

    return prompt


with st.sidebar:

   # --- CONFIGURAÇÃO DA PÁGINA (sempre no topo) ---
st.set_page_config(page_title="Mary Roleplay Autônoma", page_icon="🌹")

# --- TÍTULO E RESUMO NA ÁREA PRINCIPAL ---
st.title("🌹 Mary Roleplay com Inteligência Autônoma")
st.markdown("Converse com Mary com memória, emoção, fragmentos e continuidade narrativa.")

# --- Carrega o resumo do capítulo anterior ---
resumo = carregar_perfil_mary().get("sinopse", "[Sem resumo disponível]")

# Inicializa com a primeira mensagem, se for a primeira vez
if "mensagens" not in st.session_state:
    st.session_state.mensagens = [{
        "role": "assistant",
        "content": f"🧠 *No capítulo anterior...*\n\n> {resumo}"
    }]

# Exibe o resumo no corpo principal
st.info(f"🧠 *No capítulo anterior...*\n\n> {resumo}")

# --- SIDEBAR ---
with st.sidebar:
    st.selectbox("💙 Modo de narrativa", ["Hot", "Racional", "Flerte", "Janio"], key="modo_mary", index=1)

    modelos_disponiveis = {
        "💬 DeepSeek V3 ($) - Criativo, econômico e versátil.": "deepseek/deepseek-chat-v3-0324",
        "🔥 MythoMax 13B ($) - Forte em erotismo e envolvimento emocional.": "gryphe/mythomax-l2-13b",
        "💋 LLaMA3 Lumimaid 8B ($) - Ousado, direto e criativo para fantasias rápidas.": "neversleep/llama-3-lumimaid-8b",
        "👑 WizardLM 8x22B ($$$) - Diálogos densos, maduros e emocionais.": "microsoft/wizardlm-2-8x22b",
        "🧠 DeepSeek R1 0528 ($$) - Natural, fluido e excelente para cenas longas.": "deepseek/deepseek-r1-0528"
    }
    modelo_selecionado = st.selectbox("🤖 Modelo de IA", list(modelos_disponiveis.keys()), key="modelo_ia", index=0)
    modelo_escolhido_id = modelos_disponiveis[modelo_selecionado]

    if st.button("🎮 Ver vídeo atual"):
        st.video(f"https://github.com/welnecker/roleplay_imagens/raw/main/{fundo_video}")

    if st.button("📝 Gerar resumo do capítulo"):
        ultimas = carregar_ultimas_interacoes(n=3)
        texto = "\n".join(f"{m['role']}: {m['content']}" for m in ultimas)
        prompt = f"Resuma o seguinte trecho de conversa como um capítulo de novela:\n\n{texto}\n\nResumo:"
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://share.streamlit.io/",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-chat-v3-0324",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 300,
                "temperature": 0.7
            }
        )
        if response.status_code == 200:
            resumo_gerado = response.json()["choices"][0]["message"]["content"]
            try:
                planilha.worksheet("perfil_mary").append_row(["", "", "", "", "", "", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), resumo_gerado, ""])
                st.success("Resumo inserido com sucesso!")
            except Exception as e:
                st.error(f"Erro ao inserir resumo: {e}")
        else:
            st.error("Erro ao gerar resumo automaticamente.")

    st.markdown("---")
    st.subheader("➕ Adicionar memória fixa")

    nova_memoria = st.text_area(
        "🧠 Conteúdo da nova memória",
        height=80,
        placeholder="ex: Mary nunca tolera grosserias vindas de homens desconhecidos..."
    )

    if st.button("💾 Salvar memória"):
        if nova_memoria.strip():
            try:
                aba = planilha.worksheet("memorias")
                aba.append_row([nova_memoria.strip()])
                st.success("✅ Memória registrada com sucesso!")
            except Exception as e:
                st.error(f"Erro ao salvar memória: {e}")
        else:
            st.warning("Digite o conteúdo da memória antes de salvar.")


# --- ENTRADA DO USUÁRIO ---
if prompt := st.chat_input("Digite sua mensagem..."):
    with st.chat_message("user"):
        st.markdown(prompt)
    salvar_interacao("user", prompt)
    st.session_state.mensagens.append({"role": "user", "content": prompt})

    with st.spinner("Mary está pensando..."):
        mensagens = [{"role": "system", "content": construir_prompt_mary()}]
        fragmentos = carregar_fragmentos()
        if fragmentos:
            mensagens.append(fragmentos)
        mensagens += st.session_state.mensagens[-10:]

        resposta = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": modelo_escolhido_id,
                "messages": mensagens,
                "max_tokens": 1200,
                "temperature": 0.9
            }
        )

        if resposta.status_code == 200:
            conteudo = resposta.json()["choices"][0]["message"]["content"]
            with st.chat_message("assistant"):
                st.markdown(conteudo)
            salvar_interacao("assistant", conteudo)
            st.session_state.mensagens.append({"role": "assistant", "content": conteudo})
        else:
            st.error("Erro ao obter resposta da Mary.")
