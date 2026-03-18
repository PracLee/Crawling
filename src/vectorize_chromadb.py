import os
import json
import chromadb
from chromadb.utils import embedding_functions

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
INPUT_FILE = os.path.join(DATA_DIR, 'final_rag_trends.json')
CHROMA_DIR = os.path.join(DATA_DIR, 'chromadb')
COLLECTION_NAME = "hair_trends"

# 한영 혼합 데이터에 적합한 다국어 임베딩 모델
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_data():
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_collection():
    data = load_data()
    print(f"총 {len(data)}건의 트렌드 데이터를 로드했습니다.")

    # ChromaDB 클라이언트 (로컬 영속 저장)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # 다국어 sentence-transformers 임베딩 함수
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    # 기존 컬렉션이 있으면 삭제 후 재생성
    try:
        client.delete_collection(COLLECTION_NAME)
        print(f"기존 '{COLLECTION_NAME}' 컬렉션을 삭제했습니다.")
    except ValueError:
        pass

    collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"description": "Hair trend RAG data from global magazines"}
    )

    # ChromaDB에 배치 삽입 (최대 5000건씩)
    batch_size = 500
    for start in range(0, len(data), batch_size):
        batch = data[start:start + batch_size]

        ids = []
        documents = []
        metadatas = []

        for i, item in enumerate(batch):
            idx = start + i
            ids.append(f"trend_{idx:04d}")

            # search_text를 임베딩 대상 문서로 사용
            documents.append(item.get("search_text", ""))

            # 나머지 필드를 메타데이터로 저장
            # ChromaDB 메타데이터는 str, int, float, bool만 지원하므로 리스트는 문자열로 변환
            metadatas.append({
                "canonical_name": item.get("canonical_name", ""),
                "display_title": item.get("display_title", ""),
                "category": item.get("category", ""),
                "style_tags": ", ".join(item.get("style_tags", [])),
                "color_tags": ", ".join(item.get("color_tags", [])),
                "summary": item.get("summary", ""),
                "source": item.get("source", ""),
                "year": item.get("year", ""),
            })

        collection.add(ids=ids, documents=documents, metadatas=metadatas)
        print(f"  [{start + len(batch)}/{len(data)}] 삽입 완료")

    print(f"\n====== 벡터화 완료! ======")
    print(f"컬렉션: {COLLECTION_NAME} ({collection.count()}건)")
    print(f"저장 경로: {CHROMA_DIR}")
    return collection


def query_test(collection, query_text, n_results=5):
    """간단한 검색 테스트"""
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results
    )
    print(f"\n🔍 검색어: \"{query_text}\"")
    print("-" * 60)
    for i, (doc_id, metadata, distance) in enumerate(
        zip(results["ids"][0], results["metadatas"][0], results["distances"][0])
    ):
        print(f"  [{i+1}] {metadata['display_title']}")
        print(f"      카테고리: {metadata['category']} | 소스: {metadata['source']}")
        print(f"      거리: {distance:.4f}")
        print()


if __name__ == "__main__":
    collection = build_collection()

    # 검색 테스트
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )
    client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = client.get_collection(COLLECTION_NAME, embedding_function=ef)

    query_test(collection, "2026 spring blonde hair trend")
    query_test(collection, "올봄 유행하는 단발 헤어스타일")
    query_test(collection, "celebrity bob haircut")
