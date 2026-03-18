"""
ChromaDB + GPT API RAG 파이프라인
- ChromaDB에서 관련 트렌드 데이터를 검색 (retrieval)
- GPT API에 컨텍스트로 전달하여 답변 생성 (generation)
"""

import os
import json
import chromadb
from chromadb.utils import embedding_functions
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ── 설정 ──
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
CHROMA_DIR = os.path.join(DATA_DIR, 'chromadb')
COLLECTION_NAME = "hair_trends"
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"

# GPT 모델 설정
GPT_MODEL = "gpt-4o-mini"
TOP_K = 10  # 검색할 문서 수

# OpenAI 클라이언트
client_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ChromaDB 클라이언트
client_chroma = chromadb.PersistentClient(path=CHROMA_DIR)
ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name=EMBEDDING_MODEL
)
collection = client_chroma.get_collection(COLLECTION_NAME, embedding_function=ef)

SYSTEM_PROMPT = """당신은 전문 헤어 트렌드 컨설턴트입니다.
아래 제공되는 [참고 자료]는 2025-2026년 글로벌·한국 패션 매거진에서 수집한 최신 헤어 트렌드 데이터입니다.

중요 배경 정보:
- 데이터의 대부분은 여성 헤어 트렌드입니다. "남자", "men", "male", "grooming" 등이 명시되지 않은 자료는 여성 대상입니다.
- 따라서 "여자 머리", "여성 헤어" 관련 질문에는 제공된 자료 대부분이 해당됩니다.

규칙:
1. 반드시 [참고 자료]에 기반하여 답변하세요.
2. 참고 자료의 요약(summary)과 스타일 태그를 적극 활용하여 구체적으로 답변하세요.
3. 각 추천 스타일마다 출처(source)를 반드시 함께 언급해주세요.
4. 한국어로 답변하세요.
5. 구체적인 스타일링 팁이 자료에 있으면 반드시 포함해주세요.
6. 자료에 완전히 관련 없는 주제(헤어가 아닌 질문)에만 "해당 정보는 현재 데이터에 없습니다"라고 안내하세요.
7. 답변은 3~5개 스타일을 추천하되, 각 스타일별로 어떤 사람에게 어울리는지, 연출 방법도 포함하세요.
"""


def expand_query(query: str) -> str:
    """짧은 한국어 질문을 검색에 적합한 키워드로 확장"""
    response = client_openai.chat.completions.create(
        model=GPT_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "사용자의 헤어 관련 질문을 벡터 검색에 최적화된 키워드로 확장하세요.\n"
                    "한국어와 영어 키워드를 모두 포함하세요.\n"
                    "키워드만 쉼표로 구분하여 출력하세요. 설명은 하지 마세요.\n"
                    "예시: '여자 봄 머리' → '2026 spring women hairstyle trend, 여성 봄 헤어스타일, bob, lob, layers, bangs, 단발, 레이어드, 뱅'"
                ),
            },
            {"role": "user", "content": query},
        ],
        temperature=0,
        max_tokens=200,
    )
    expanded = response.choices[0].message.content.strip()
    return f"{query}, {expanded}"


def retrieve(query: str, n_results: int = TOP_K, expand: bool = True) -> list[dict]:
    """ChromaDB에서 쿼리와 관련된 트렌드 데이터를 검색"""
    search_query = expand_query(query) if expand else query

    results = collection.query(
        query_texts=[search_query],
        n_results=n_results,
    )

    docs = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        doc = results["documents"][0][i]
        distance = results["distances"][0][i]
        docs.append({
            "title": meta.get("display_title", ""),
            "category": meta.get("category", ""),
            "summary": meta.get("summary", ""),
            "style_tags": meta.get("style_tags", ""),
            "color_tags": meta.get("color_tags", ""),
            "source": meta.get("source", ""),
            "year": meta.get("year", ""),
            "distance": distance,
        })
    return docs


def build_context(docs: list[dict]) -> str:
    """검색 결과를 GPT에 전달할 컨텍스트 문자열로 변환"""
    context_parts = []
    for i, doc in enumerate(docs, 1):
        part = f"""[자료 {i}]
제목: {doc['title']}
카테고리: {doc['category']}
요약: {doc['summary']}
스타일 태그: {doc['style_tags']}
컬러 태그: {doc['color_tags']}
출처: {doc['source']} ({doc['year']})
"""
        context_parts.append(part)
    return "\n".join(context_parts)


def ask(query: str, n_results: int = TOP_K) -> str:
    """RAG 파이프라인: 검색 → 컨텍스트 구성 → GPT 답변 생성"""
    # 1. Retrieve
    docs = retrieve(query, n_results)
    context = build_context(docs)

    # 2. Generate
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": f"[참고 자료]\n{context}\n\n[질문]\n{query}",
        },
    ]

    response = client_openai.chat.completions.create(
        model=GPT_MODEL,
        messages=messages,
        temperature=0.3,
        max_tokens=2000,
    )

    return response.choices[0].message.content


# ── 대화형 모드 ──
if __name__ == "__main__":
    print("=" * 60)
    print("💇 헤어 트렌드 RAG 챗봇 (ChromaDB + GPT)")
    print(f"   DB: {collection.count()}건 | 모델: {GPT_MODEL}")
    print("   종료: quit / exit / q")
    print("=" * 60)

    while True:
        query = input("\n🔍 질문: ").strip()
        if query.lower() in ("quit", "exit", "q", ""):
            print("👋 종료합니다.")
            break

        print("\n검색 중...")
        docs = retrieve(query)
        print(f"📄 관련 자료 {len(docs)}건 검색 완료 (최소 거리: {docs[0]['distance']:.4f})")

        print("\n💬 GPT 답변 생성 중...\n")
        answer = ask(query)
        print(answer)
        print("\n" + "-" * 60)
