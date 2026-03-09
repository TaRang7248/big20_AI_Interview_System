import re
import unicodedata

# 한글 숫자 매핑 (일~구, 십, 백, 천, 만 대응)
# 참고: 제한적인 간단한 정규화만 수행하며, 복잡한 한국어 수사 정규화는 STT 특성에 맞게 보수적으로 처리.
_KOR_NUMBERS = {
    '영': 0, '공': 0,
    '일': 1, '이': 2, '삼': 3, '사': 4, '오': 5,
    '육': 6, '칠': 7, '팔': 8, '구': 9
}

def remove_punctuation(text: str) -> str:
    """구두점 및 특수문자를 제거한다."""
    # 유니코드 카테고리가 구두점(P)인 문자 제거
    return "".join(ch for ch in text if not unicodedata.category(ch).startswith('P'))

def normalize_whitespace(text: str) -> str:
    """연속된 공백을 하나로 줄이고 앞뒤 공백을 제거한다."""
    return re.sub(r'\s+', ' ', text).strip()

def normalize_digits(text: str) -> str:
    """
    매우 단순화된 숫자 정규화.
    '이십사' -> 24 변환과 같이 복잡한 NLP 기반 수사 정규화는 외부 라이브러리가 필요하므로,
    본 구현에서는 가장 기본적인 전처리(구두점 제거 등)를 메인으로 유지한다.
    실제로 whisper 모델 등은 숫자 전사('24')와 한글 전사('이십사')의 혼용이 잦으므로
    고도화보다는 단순 룰 기반이나 공통화를 사용해야 한다.
    (현재는 단순 플레이스홀더 역할로서, 향후 필요시 kss 등 한국어 정규화기로 교체 가능)
    """
    return text

def normalize_text(text: str) -> str:
    """
    정확도 측정(WER/CER)을 위한 기본 텍스트 정규화를 수행한다.
    - 소문자화 (영어는 소문자로 획일화하여 대소문자 차이 무시, 단 스펠링이 틀리면 에러)
    - 구두점 제거
    - 공백 정규화
    - (주의) 외래어/영어 한글 음차 변환(Redis -> 레디스)은 수행하지 않는다.
    """
    if not text:
        return ""
    
    # 1. 소문자화
    text = text.lower()
    # 2. 구두점 제거
    text = remove_punctuation(text)
    # 3. 추가적인 숫자 정규화 등
    text = normalize_digits(text)
    # 4. 공백 정규화
    text = normalize_whitespace(text)
    
    return text

def extract_digits(text: str) -> str:
    """
    Digit Accuracy Score 계산을 위해 문자열에서 아라비아 숫자만 추출한다.
    """
    return "".join(re.findall(r'\d+', text))

