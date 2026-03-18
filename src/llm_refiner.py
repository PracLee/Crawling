import os
import json
import time
from dotenv import load_dotenv
from google import genai
from pydantic import BaseModel, Field
from typing import List, Literal

class TrendInfo(BaseModel):
    is_valid: bool = Field(description="내용이 쓸모없는 단순 광고, 빈약한 잡담이면 false, 데이터로서 가치가 있으면 true")
    canonical_name: str = Field(description="정규화된 트렌드명 (예: faux bob, soft mullet, hydro bob). 영문 소문자 권장")
    category: Literal["style_trend", "color_trend", "celebrity_example", "styling_guide", "drop"] = Field(
        description="""
        style_trend: 실제 헤어스타일의 유행 
        color_trend: 시즌 헤어컬러의 트렌드 
        celebrity_example: 특정 셀럽의 헤어스타일 예시와 일화 
        styling_guide: 단순 관리법, 고데기/드라이기 사용법, 가르마 또는 얼굴형 팁 (트렌드라기보단 가이드 아카이브용)
        drop: 내용이 너무 얕거나 상관없는 제품판매/광고일 경우
        """
    )
    style_tags: List[str] = Field(description="추출된 주요 스타일 키워드 배열 (예: ['layered cut', 'bob'])")
    color_tags: List[str] = Field(description="추출된 주요 컬러 키워드 배열 (예: ['ash blonde', 'copper'])")
    summary: str = Field(description="핵심 내용만 간추린 2~3문장 요약. (스타일 가이드나 불필요한 미사여구 제거)")
    search_text: str = Field(description="RAG 검색 성능을 극대화하기 위해 'canonical_name, 특징, 관련 키워드'를 자연스럽게 이어붙인 검색용 합성 텍스트")

class LLMRefiner:
    def __init__(self):
        load_dotenv()
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("⚠️ 경고: .env 파일에 GEMINI_API_KEY가 설정되어 있지 않습니다.")
            return
            
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "gemini-2.5-flash"
        
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        # 원본 데이터는 refined_trends.json에서 가져옴
        self.input_file = os.path.join(self.data_dir, 'refined_trends.json')
        self.output_file = os.path.join(self.data_dir, 'final_rag_trends.json')

    def refine_with_llm(self):
        if not self.api_key:
            return
            
        if not os.path.exists(self.input_file):
            print(f"입력 파일이 없습니다: {self.input_file}")
            return
            
        with open(self.input_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        print(f"====== 최상위 LLM RAG 데이터 정제 작업 시작 (총 {len(data)}건) ======")
        valid_items = []
        
        for i, item in enumerate(data):
            # 터미널에 중간 진행상황 출력
            print(f"[{i+1}/{len(data)}] {item.get('trend_name')[:30]}...")
            
            prompt = f"""
당신은 최고의 헤어 트렌드 분석가이자 RAG 엔지니어입니다.
주어진 뷰티 매거진 텍스트를 분석하여, RAG 검색용 벡터 데이터베이스에 적합한 완벽한 스키마 구조로 파싱하세요.

[분리 및 필터링 기준]
1. 완벽한 트렌드 DB 남기기 (category: style_trend, color_trend, celebrity_example)
   - "이 시즌엔 이런 컷이 유행이다" (style_trend)
   - "올가을 유행할 염색" (color_trend)
   - "특정 셀럽이 시도한 머리" (celebrity_example)
2. 헤어 가이드 분리하기 (category: styling_guide)
   - 펌핑/드라이하는 관리법, 고데기 How-to, 얼굴형별 추천, 가르마 타는법 등은 트렌드가 아니라 가이드 아카이브용이므로 분리합니다.
3. 배제하기 (category: drop, is_valid: false)
   - "무조건 예뻐보인다", "너무 아름답다" 수준의 얕고 영양가 없는 글
   - 쇼핑몰 구매 유도, 광고 꼬리문구만 남은 글
   - 헤어와 무관한 콘텐츠: 스킨케어, 메이크업, 향수, 네일, 패션(의류/가방/신발), 다이어트, 인테리어, 여행 등
   - 제품 리뷰/추천만 있고 트렌드 정보가 없는 글 (예: "이 샴푸 좋다", "이 고데기 추천")

입력 텍스트:
제목: {item.get('trend_name')}
본문 내용: {item.get('description')}
"""
            
            try:
                # API Rate Limit 보호를 위해 초당 1회 지연시간 부여 
                time.sleep(1)
                
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=genai.types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=TrendInfo,
                        temperature=0.2, # 좀 더 일관되고 정직한 요약을 위해 온도를 낮춤
                    ),
                )
                
                result = json.loads(response.text)
                
                if result.get("is_valid") and result.get("category") != "drop":
                    # 최종 스키마에 맞춰 새 아이템 생성
                    new_item = {
                        "canonical_name": result.get("canonical_name", ""),
                        "display_title": item.get("trend_name", ""),
                        "category": result.get("category", ""),
                        "style_tags": result.get("style_tags", []),
                        "color_tags": result.get("color_tags", []),
                        "summary": result.get("summary", ""),
                        "search_text": result.get("search_text", ""),
                        "source": item.get("source", "Unknown"),
                        "year": item.get("year", "2026")
                    }
                    valid_items.append(new_item)
                    print(f"   ✓ [채택] 카테고리: {new_item['category']} | 정규화: {new_item['canonical_name']}")
                else:
                    print("   X [드롭] 얕은 기사 또는 제품 광고 처리됨")
                    
            except Exception as e:
                print(f"   ! [에러] 처리 중 예외: {e}")
                
        # 최종 중복 제거 (canonical_name + category 조합이 같은 경우)
        print("\n====== 중복 제거 작업 ======")
        deduplicated = []
        seen = set()
        for v in valid_items:
            # 완전 동일한 트렌드와 카테고리라면 내용도 비슷할 확률이 높아 1차 필터링
            uniq_key = f"{v['canonical_name'].lower().strip()}_{v['category']}"
            if uniq_key not in seen:
                seen.add(uniq_key)
                deduplicated.append(v)
            else:
                pass # 이미 넣었으므로 중복 생략. RAG 성능 향상
                
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(deduplicated, f, ensure_ascii=False, indent=2)
            
        print(f"\n====== 최종 정제 완료! 원본 {len(data)}건 -> 1차 정제 {len(valid_items)}건 -> 중복제거 최종 {len(deduplicated)}건 ======")
        print(f"결과물 저장 경로: {self.output_file}")

if __name__ == '__main__':
    refiner = LLMRefiner()
    refiner.refine_with_llm()
