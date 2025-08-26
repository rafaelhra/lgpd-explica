import streamlit as st
import traceback
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate
from langchain_huggingface.llms import HuggingFacePipeline

# --- CONFIGURAÇÃO DA PÁGINA STREAMLIT ---
st.set_page_config(
    page_title="LGPD-Explica",
    page_icon="⚖️",
    layout="wide"
)

# --- TÍTULO E DESCRIÇÃO ---
st.title("⚖️ LGPD-Explica: Seu Assistente Inteligente para a LGPD")
st.markdown("""
Bem-vindo! Este chatbot usa um modelo de linguagem rodando localmente para responder suas perguntas sobre a Lei Geral de Proteção de Dados, com base no texto oficial.
""")

# --- LÓGICA DE BACK-END ---

@st.cache_resource
def load_and_process_knowledge_base():
    """ Carrega e processa o PDF para criar um retriever. """
    try:
        loader = PyPDFLoader("data/lgpd.pdf")
        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        docs = text_splitter.split_documents(documents)
        model_name = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        embeddings = HuggingFaceEmbeddings(model_name=model_name, model_kwargs={'device': 'cpu'})
        vector_store = FAISS.from_documents(docs, embeddings)
        return vector_store.as_retriever(search_kwargs={"k": 2})
    except Exception as e:
        st.error(f"Erro ao carregar a base de conhecimento: {e}")
        return None

@st.cache_resource
def load_llm():
    """ Carrega o modelo de linguagem local (TinyLlama). """
    llm = HuggingFacePipeline.from_model_id(
        model_id="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        task="text-generation",
        device_map="auto",  # Usa GPU se disponível, senão CPU
        pipeline_kwargs={
            "max_new_tokens": 1024,
            "do_sample": True,
            "temperature": 0.7,
            "top_k": 50
        },
    )
    return llm

# --- CRIAÇÃO DA CADEIA RAG ---
try:
    retriever = load_and_process_knowledge_base()
    llm = load_llm()

    prompt_template = """
    <|system|>
    Você é um assistente especializado na Lei Geral de Proteção de Dados (LGPD) do Brasil.
    Use o contexto fornecido para responder à pergunta do usuário de forma clara e objetiva.
    Responda apenas em português.</s>
    <|user|>
    Contexto: {context}
    Pergunta: {input}</s>
    <|assistant|>
    Resposta:
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)

    document_chain = create_stuff_documents_chain(llm, prompt)
    retrieval_chain = create_retrieval_chain(retriever, document_chain)
except Exception as e:
    st.error("Ocorreu um erro crítico durante a inicialização do modelo. Verifique o terminal.")
    st.code(traceback.format_exc())
    retrieval_chain = None


# --- INTERFACE DO USUÁRIO ---
question = st.text_input("Faça sua pergunta sobre a LGPD aqui:", placeholder="Ex: Quais são os direitos do titular dos dados?")

if st.button("Enviar Pergunta"):
    if retrieval_chain:
        if question:
            with st.spinner("Pensando... (o carregamento inicial do modelo pode levar alguns minutos) 🧠"):
                try:
                    response = retrieval_chain.invoke({"input": question})
                    st.success("Resposta Gerada!")
                    # O TinyLlama Chat pode incluir o prompt na resposta, então limpamos isso.
                    answer = response["answer"].split("Resposta:")[-1].strip()
                    st.markdown(answer)

                    with st.expander("Ver fontes consultadas"):
                        for i, doc in enumerate(response["context"]):
                            st.write(f"**Fonte {i+1}:**")
                            st.write(doc.page_content)
                except Exception as e:
                    st.error("Ocorreu um erro ao gerar a resposta.")
                    st.code(traceback.format_exc())
        else:
            st.warning("Por favor, digite uma pergunta.")
    else:
        st.error("A cadeia de RAG não foi inicializada corretamente. Verifique os logs.")