import os
from typing import Set

def load_it_terms() -> dict:
    """
    IT 용어 매핑(Phonetic -> List[English/Phonetic])을 로드한다.
    """
    import json
    base_dir = os.path.dirname(os.path.abspath(__file__))
    resolved_path = os.path.join(base_dir, "data/term_mapping.json")
    
    if os.path.exists(resolved_path):
        with open(resolved_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    Character Error Rate (CER) 계산
    Levenshtein distance를 레퍼런스 길이로 나눈 값
    """
    if not reference:
        return 1.0 if hypothesis else 0.0
    
    ref, hyp = list(reference), list(hypothesis)
    d = _levenshtein(ref, hyp)
    return d / len(ref)


def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Word Error Rate (WER) 계산
    띄어쓰기 기준으로 토큰화하여 Levenshtein distance 계산
    """
    if not reference:
        return 1.0 if hypothesis else 0.0
        
    ref_words = reference.split()
    hyp_words = hypothesis.split()
    
    if not ref_words:
        return 1.0 if hyp_words else 0.0
        
    d = _levenshtein(ref_words, hyp_words)
    return d / len(ref_words)


def _levenshtein(seq1, seq2):
    """
    단순 Levenshtein Distance 구현.
    (seq1, seq2는 리스트 형태 (단어 또는 문자열 내 문자))
    """
    size_x = len(seq1) + 1
    size_y = len(seq2) + 1
    matrix = [[0] * size_y for _ in range(size_x)]
    for x in range(size_x):
        matrix[x][0] = x
    for y in range(size_y):
        matrix[0][y] = y

    for x in range(1, size_x):
        for y in range(1, size_y):
            if seq1[x-1] == seq2[y-1]:
                matrix[x][y] = matrix[x-1][y-1]
            else:
                matrix[x][y] = min(
                    matrix[x-1][y] + 1,     # Deletion
                    matrix[x][y-1] + 1,     # Insertion
                    matrix[x-1][y-1] + 1    # Substitution
                )
    return matrix[-1][-1]


def calculate_foreign_term_accuracy(reference: str, hypothesis: str, mapping: dict) -> float:
    """
    레퍼런스에 있는 용어(영어 또는 한글 발음)가 가설(hypothesis)에서 
    대응하는 형태(영어 또는 한글)로 나타나는지 확인한다.
    """
    ref_clean = reference.replace(" ", "").lower()
    hyp_clean = hypothesis.replace(" ", "").lower()
    
    # 레퍼런스에 존재하는 대응 용어 그룹(Key) 찾기
    found_keys = []
    for key, variants in mapping.items():
        # Key(한글발음)나 변형(영어 등) 중 하나라도 레퍼런스에 있으면 해당 단어를 평가 대상으로 삼음
        check_list = [key] + variants
        if any(v.replace(" ", "").lower() in ref_clean for v in check_list):
            found_keys.append(key)
    
    if not found_keys:
        return None
        
    correct_count = 0
    for key in found_keys:
        # 해당 용어의 모든 수용 가능한 변형 중 하나라도 가설에 포함되어 있으면 정답
        accepted_variants = [key] + mapping[key]
        accepted_clean = [v.replace(" ", "").lower() for v in accepted_variants]
        if any(v in hyp_clean for v in accepted_clean):
            correct_count += 1
            
    return correct_count / len(found_keys)

def calculate_digit_accuracy(ref_digits: str, hyp_digits: str) -> float:
    """
    숫자 추출 문자열 간의 정확도. (Character 단위 매칭)
    """
    if not ref_digits:
        return None
        
    d = _levenshtein(list(ref_digits), list(hyp_digits))
    acc = 1.0 - (d / len(ref_digits))
    return max(0.0, acc)
