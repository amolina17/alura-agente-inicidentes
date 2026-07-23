import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from agente import IncidentAssistant

load_dotenv()

st.set_page_config(page_title="Agente de Incidentes", page_icon="🚨", layout="centered")

st.title("🚨 Agente de Respuesta a Incidentes")
st.caption("Consulta el Protocolo de Respuesta a Incidentes y Post-Mortems de Santo Pegasus Soluciones.")

pdf_path = Path(__file__).parent / "data" / "protocolo_incidentes.pdf"
api_key = os.getenv("GEMINI_API_KEY")

if not pdf_path.exists():
    st.error("No se encontró el PDF en data/protocolo_incidentes.pdf")
    st.stop()

if not api_key:
    st.warning("Configura la variable GEMINI_API_KEY antes de ejecutar la aplicación.")
    st.code('GEMINI_API_KEY="tu_clave"', language="bash")
    st.stop()

@st.cache_resource(show_spinner="Procesando el documento...")
def cargar_agente() -> IncidentAssistant:
    return IncidentAssistant(pdf_path=pdf_path, api_key=api_key)

try:
    agente = cargar_agente()
except Exception as exc:
    st.error(f"No fue posible iniciar el agente: {exc}")
    st.stop()

with st.expander("Preguntas de ejemplo"):
    st.markdown(
        """
- ¿Cuál es la diferencia entre un incidente y un problema?
- ¿Cuál es el tiempo de respuesta para un incidente SEV-1?
- ¿Qué requisitos debe cumplir un cambio planificado?
- ¿Qué significa una cultura blameless?
- ¿Cada cuánto debe actualizarse un incidente SEV-2?
        """
    )

pregunta = st.text_input("Escribe tu pregunta sobre el protocolo:")

if st.button("Consultar", type="primary", disabled=not pregunta.strip()):
    with st.spinner("Buscando en el documento..."):
        try:
            resultado = agente.responder(pregunta.strip())
            st.subheader("Respuesta")
            st.write(resultado["respuesta"])

            with st.expander("Fragmentos utilizados como contexto"):
                for i, fragmento in enumerate(resultado["fuentes"], start=1):
                    st.markdown(f"**Fragmento {i}**")
                    st.write(fragmento)
        except Exception as exc:
            st.error(f"Ocurrió un error al generar la respuesta: {exc}")

st.divider()
st.caption("La respuesta se genera únicamente a partir del contenido recuperado del PDF.")
