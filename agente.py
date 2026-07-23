from pathlib import Path
from typing import Dict, List

from google import genai
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


STOP_WORDS_ES = [
    "a", "al", "algo", "algunas", "algunos", "ante", "antes", "como",
    "con", "contra", "cual", "cuando", "de", "del", "desde", "donde",
    "durante", "e", "el", "ella", "ellas", "ellos", "en", "entre",
    "era", "es", "esa", "ese", "eso", "esta", "este", "esto", "fue",
    "ha", "hay", "la", "las", "lo", "los", "más", "me", "mi", "muy",
    "no", "o", "para", "pero", "por", "porque", "que", "qué", "se",
    "según", "ser", "si", "sin", "sobre", "son", "su", "sus", "también",
    "te", "tiene", "un", "una", "uno", "unos", "unas", "y", "ya"
]


class IncidentAssistant:
    """Agente RAG sencillo para responder preguntas basadas en un PDF."""

    def __init__(self, pdf_path: Path, api_key: str, top_k: int = 6) -> None:
        self.pdf_path = Path(pdf_path)
        self.top_k = top_k
        self.client = genai.Client(api_key=api_key)

        self.fragments = self._load_and_split_pdf()

        if not self.fragments:
            raise ValueError("El PDF no contiene texto procesable.")

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            stop_words=STOP_WORDS_ES,
            ngram_range=(1, 3),
            sublinear_tf=True,
            max_features=50000,
        )

        self.fragment_matrix = self.vectorizer.fit_transform(self.fragments)

    def _load_and_split_pdf(self) -> List[str]:
        reader = PdfReader(str(self.pdf_path))
        pages: List[str] = []

        for page_number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()

            if text:
                pages.append(f"[Página {page_number}]\n{text}")

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=150,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

        return splitter.split_text("\n\n".join(pages))

    def _expand_question(self, question: str) -> str:
        """
        Agrega palabras relacionadas para mejorar la recuperación
        de fragmentos en preguntas frecuentes.
        """
        normalized = question.lower().strip()
        expanded = question

        if "qué es un incidente" in normalized or "que es un incidente" in normalized:
            expanded += (
                " definición incidente evento no planificado "
                "degradación interrupción servicios producción"
            )

        if "diferencia" in normalized and "incidente" in normalized and "problema" in normalized:
            expanded += (
                " incidente síntoma observable problema causa raíz "
                "causa sistémica gestión de incidentes"
            )

        if "sev-1" in normalized or "sev 1" in normalized:
            expanded += (
                " SEV-1 crítico SLA respuesta 15 minutos "
                "actualización cada 30 minutos"
            )

        if "cambio planificado" in normalized:
            expanded += (
                " aprobación comunicación previa 48 horas "
                "plan rollback ventana mantenimiento"
            )

        if "blameless" in normalized or "sin culpa" in normalized:
            expanded += (
                " cultura sin culpa análisis sistema no individuo "
                "post-mortem aprendizaje"
            )

        return expanded

    def _retrieve(self, question: str) -> List[str]:
        expanded_question = self._expand_question(question)

        question_vector = self.vectorizer.transform([expanded_question])

        scores = cosine_similarity(
            question_vector,
            self.fragment_matrix
        ).flatten()

        best_indices = scores.argsort()[::-1][: self.top_k]

        return [
            self.fragments[index]
            for index in best_indices
            if scores[index] > 0
        ]

    def responder(self, question: str) -> Dict[str, object]:
        sources = self._retrieve(question)

        if not sources:
            return {
                "respuesta": (
                    "No encontré información suficiente en el documento "
                    "para responder esa pregunta."
                ),
                "fuentes": [],
            }

        context = "\n\n---\n\n".join(sources)

        prompt = f"""
Eres un asistente corporativo especializado en respuesta a incidentes.

Tu tarea es responder usando únicamente el contenido incluido en el CONTEXTO.

Instrucciones:

- Analiza cuidadosamente todos los fragmentos.
- Responde aunque la información esté redactada con palabras distintas.
- No uses conocimiento externo.
- No inventes datos.
- Si la respuesta aparece en alguno de los fragmentos, debes responderla.
- Solo indica que no existe información suficiente cuando ninguno de los
  fragmentos permita responder.
- Responde de forma clara, directa y en español.
- Cuando corresponda, menciona plazos, severidades, roles o procedimientos.

CONTEXTO:

{context}

PREGUNTA:

{question}
"""

        response = self.client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt,
        )

        answer = (response.text or "").strip()

        if not answer:
            answer = "No fue posible generar una respuesta en este momento."

        return {
            "respuesta": answer,
            "fuentes": sources,
        }
    