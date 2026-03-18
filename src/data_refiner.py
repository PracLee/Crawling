import os
import json
import re

class DataRefiner:
    def __init__(self):
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
        self.output_file = os.path.join(self.data_dir, 'refined_trends.json')
        
        # 보일러플레이트(불필요한 문구) 제거용 패턴들
        self.junk_patterns = [
            r"Currently, only residents from GDPR countries.*?Privacy Policy for more information\.",
            r"©2026Condé Nast.*?Ad Choices\s*CN Fashion & Beauty",
            r"All products featured on.*?through these links\.",
            r"Sign up for.*?newsletter.*?wellness\.",
            r"The Vogue Runway app has expanded!.*?\bcontributors\.",
            r"Become a.*?Member—the ultimate resource.*?\bprofessionals\.",
            r"Have a beauty or wellness trend you’re curious about\?.*?@vogue\.com\.",
            r"More from Vogue.*?See More Stories",
            r"Related Video.*?(?=\n|$)",
            r"Shop the look.*?(?=\n|$)",
            r"Shop our favorite.*?(?=\n|$)",
            r"Available at Amazon.*?(?=\n|$)",
            r"Available at Sephora.*?(?=\n|$)",
            r"Available at Nordstrom.*?(?=\n|$)"
        ]
        
        # 간단한 텍스트 매칭을 통한 속성 추출용 사전 (영문 + 한국어)
        self.hair_styles = [
            "bob", "pixie", "layered", "curtain bangs", "bangs", "updo",
            "bun", "braid", "ponytail", "lob", "shag", "mullet", "extensions",
            "chignon", "waves", "curls", "knot", "half-up",
            # 한국어 헤어스타일 키워드
            "단발", "숏컷", "레이어드", "시스루뱅", "앞머리", "업스타일",
            "번헤어", "브레이드", "포니테일", "허쉬컷", "울프컷", "빌드컷",
            "웨이브", "컬", "펌", "히피펌", "레이어컷", "가르마",
            "보브컷", "태슬컷", "샤기컷", "헤어스타일", "머리스타일",
            "투블럭", "리젠트", "댄디컷", "포마드", "바버컷", "크롭컷",
            "애즈펌", "다운펌", "가일컷", "리프컷"
        ]

        self.hair_colors = [
            "blonde", "brunette", "red", "copper", "balayage", "highlights",
            "ombre", "silver", "gray", "black", "brown", "caramel", "chocolate",
            "strawberry", "auburn", "platinum",
            # 한국어 헤어컬러 키워드
            "염색", "탈색", "블론드", "브루넷", "발레아쥬", "하이라이트",
            "옴브레", "애쉬", "밀크티컬러", "핑크브라운", "초코브라운",
            "카라멜", "구리빛", "레드브라운", "로즈골드", "베이지브라운",
            "흑발", "다크브라운", "톤다운", "톤업", "컬러링", "새치염색",
            "그레이컬러", "실버컬러", "머쉬룸블론드"
        ]
        
        # 역사적/결혼식/향수 및 제품 리뷰/쇼핑 관련 가비지 데이터를 걸러낼 키워드 (영문 + 한국어)
        self.banned_keywords = [
            "1990s", "1980s", "1970s", "1960s", "1950s", "vintage", "old hollywood",
            "history", "retro", "nuptials", "wedding", "bridal", "bride", "royal", "princess",
            "how to use", "best shampoo", "best conditioner", "hair dryer", "curling iron",
            "flat iron", "serum", "scalp scrub", "hair growth", "hair loss", "thinning hair",
            "dandruff", "vitamin c", "pillowcase", "leggings", "showerhead", "shop now",
            "buy now", "amazon", "sephora", "nordstrom", "ulta", "price:",
            # 한국어 비헤어 배제 키워드 (스킨케어/메이크업/향수/패션/제품리뷰)
            "스킨케어", "피부관리", "피부과", "여드름", "주름", "모공",
            "파운데이션", "립스틱", "아이섀도", "마스카라", "컨실러", "블러셔",
            "선크림", "자외선", "톤크림", "쿠션팩트", "비비크림",
            "향수", "퍼퓸", "디퓨저", "바디로션", "바디워시", "핸드크림",
            "네일", "매니큐어", "페디큐어", "젤네일",
            "구매하기", "최저가", "할인", "쿠폰", "무료배송",
            "다이어트", "운동", "필라테스", "요가", "헬스",
            "패션위크", "컬렉션 리뷰", "런웨이 리뷰", "스트리트패션",
            "가방", "신발", "시계", "주얼리", "악세서리", "선글라스",
            "인테리어", "레시피", "맛집", "여행", "호텔"
        ]
        
        # 정규식을 이용해 연도(예: 1952, '80s)나 구체적인 튜토리얼(spray 6 to 10 inches) 문구 제거용 필터
        self.banned_patterns = [
            r"\b19\d{2}\b",        # 1900년대 연도
            r"\'?[89]0s",          # '80s, 90s, '90s
            r"spray \d+ to \d+",   # 스프레이 사용 지시문구
            r"how to use"          # 제품 사용법
        ]

    def clean_text(self, text):
        if not text:
            return ""
            
        # 정규식을 통한 불필요 문구 제거
        for pattern in self.junk_patterns:
            text = re.sub(pattern, "", text, flags=re.IGNORECASE | re.DOTALL)
            
        # 연속된 공백 및 줄바꿈 정리
        text = re.sub(r'\n+', '\n', text)
        text = text.strip()
        return text

    def extract_attributes(self, text, title):
        # 제목과 본문을 합쳐서 검색
        combined_text = f"{title} {text}".lower()
        
        found_styles = [style for style in self.hair_styles if style in combined_text]
        found_colors = [color for color in self.hair_colors if color in combined_text]
        
        # 중복 제거 및 쉼표로 연결
        style_text = ", ".join(list(set(found_styles)))
        color_text = ", ".join(list(set(found_colors)))
        
        return style_text, color_text

    def refine(self):
        print("====== 데이터 정제 작업 시작 ======")
        all_items = []
        
        # 수집된 json 파일들 모두 읽기 (reddit이나 잡지 데이터 등)
        excluded_files = ['refined_trends.json', 'llm_refined_trends.json', 'final_rag_trends.json']
        target_files = [f for f in os.listdir(self.data_dir) if f.endswith('.json') and f not in excluded_files]
        
        for filename in target_files:
            filepath = os.path.join(self.data_dir, filename)
            if not os.path.exists(filepath):
                print(f"[{filename}] 파일이 없습니다. 스킵합니다.")
                continue
                
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                for item in data:
                    # 1. 본문 텍스트 정리
                    cleaned_desc = self.clean_text(item.get('description', ''))
                    
                    # 2. 내용이 너무 짧은 항목 필터링 (가비지 데이터 방지)
                    if len(cleaned_desc) < 30:
                        continue
                        
                    # 3. 빈 속성 채우기(휴리스틱 매칭)
                    current_style = item.get('hairstyle_text', '')
                    current_color = item.get('color_text', '')
                    
                    ext_style, ext_color = self.extract_attributes(cleaned_desc, item.get('trend_name', ''))
                    
                    # RAG 품질 향상을 위한 엄격한 필터 1: 역사/웨딩(노이즈) 문서 배제
                    combined_text_for_filter = f"{item.get('trend_name', '')} {cleaned_desc}".lower()
                    if any(banned_word in combined_text_for_filter for banned_word in self.banned_keywords):
                        continue
                        
                    # 정규식 패턴 기반 배제 (과거 연도 및 튜토리얼)
                    if any(re.search(pattern, combined_text_for_filter, re.IGNORECASE) for pattern in self.banned_patterns):
                        continue
                    
                    # RAG 품질 향상을 위한 엄격한 필터 2: 스타일이나 색상 키워드가 하나도 없으면 드랍
                    if not current_style and not ext_style and not current_color and not ext_color:
                        continue
                        
                    if not current_style:
                        item['hairstyle_text'] = ext_style
                    if not current_color:
                        item['color_text'] = ext_color
                            
                    item['description'] = cleaned_desc
                    all_items.append(item)
                    
                print(f"[{filename}] {len(data)}건 중 유효 데이터 추출 완료.")
            except Exception as e:
                print(f"[{filename}] 처리 중 에러: {e}")

        # 4. 중복 항목 제거 (제목 + 내용 일부 기준)
        unique_items = []
        seen = set()
        for item in all_items:
            # 트렌드 이름과 설명 앞 50자리를 결합해 고유 키로 사용
            key = (item.get('trend_name', '') + item.get('description', '')[:50]).strip()
            if key not in seen:
                seen.add(key)
                unique_items.append(item)

        # 5. 최종 결과 저장
        with open(self.output_file, 'w', encoding='utf-8') as f:
            json.dump(unique_items, f, ensure_ascii=False, indent=2)
            
        print(f"====== 정제 완료! 총 {len(unique_items)}건의 트렌드 데이터가 병합 및 저장되었습니다. ======")
        print(f"저장 경로: {self.output_file}")


if __name__ == '__main__':
    Refiner = DataRefiner()
    Refiner.refine()
