#!/usr/bin/env python3
"""
preprocessed 디렉토리 내의 모든 translation_review_llm.csv 파일들을 기반으로
통합된 statistics_summary.txt를 생성하는 스크립트
"""

import pandas as pd
import os
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# 태그 표시 순서 정의
TAG_ORDER = [
    "윤문",
    "문법", 
    "오역",
    "오탈자",
    "[가이드 준수] 표기법 준수",
    "[가이드 준수] 설정집 반영",
    "[가이드 준수] 이외 항목 미준수"
]

# 평가 기준 정의
EVALUATION_CRITERIA = {
    "오역": {
        "name_en": "Accuracy of Content",
        "weighted": True,
        "good_score": 6,
        "fair_score": 4,
        "poor_score": 0,
        "tags": ["오역"],
        "good_range": (0, 10),    # 0~10%
        "fair_range": (10, 30),   # 10~30%
        "poor_range": (30, 100)   # 30%~
    },
    "문법": {
        "name_en": "Grammar",
        "weighted": True,
        "good_score": 6,
        "fair_score": 4,
        "poor_score": 0,
        "tags": ["문법"],
        "good_range": (0, 10),
        "fair_range": (10, 30),
        "poor_range": (30, 100)
    },
    "윤문": {
        "name_en": "Polishing",
        "weighted": True,
        "good_score": 6,
        "fair_score": 4,
        "poor_score": 0,
        "tags": ["윤문"],
        "good_range": (0, 10),
        "fair_range": (10, 30),
        "poor_range": (30, 100)
    },
    "오탈자": {
        "name_en": "Typos",
        "weighted": False,
        "good_score": 3,
        "fair_score": 2,
        "poor_score": 1,
        "tags": ["오탈자"],
        "good_range": (0, 10),
        "fair_range": (10, 30),
        "poor_range": (30, 100)
    },
    "가이드 준수": {
        "name_en": "Guideline Adherance",
        "weighted": False,
        "good_score": 3,
        "fair_score": 2,
        "poor_score": 1,
        "tags": ["[가이드 준수] 설정집 반영", "[가이드 준수] 표기법 준수", "[가이드 준수] 이외 항목 미준수"],
        "good_range": (0, 10),
        "fair_range": (10, 30),
        "poor_range": (30, 100)
    }
}

# 등급 기준 정의
GRADE_CRITERIA = {
    "A": {"range": (21, 24), "status": "합격"},
    "B": {"range": (17, 20), "status": "합격"},
    "C": {"range": (11, 16), "status": "불합격"},
    "D": {"range": (2, 10), "status": "불합격"}
}

def find_llm_csv_files(base_path):
    """
    지정된 경로에서 모든 translation_review_llm.csv 파일을 찾아 반환
    
    Args:
        base_path (str): 기본 검색 경로
        
    Returns:
        list: translation_review_llm.csv 파일 경로들
    """
    csv_files = []
    base_path = Path(base_path)
    
    # 하위 디렉토리에서 translation_review_llm.csv 파일 찾기
    for csv_file in base_path.glob("**/translation_review_llm.csv"):
        if csv_file.is_file():
            csv_files.append(str(csv_file))
    
    return sorted(csv_files)

def calculate_total_textboxes_from_xlsx_unified(csv_file_path):
    """
    CSV 파일 경로를 기반으로 해당하는 원본 XLSX 파일에서 전체 텍스트박스 수를 계산
    
    Args:
        csv_file_path (str): translation_review_llm.csv 파일 경로
        
    Returns:
        int: 전체 고유 텍스트박스 수
    """
    try:
        # CSV 파일 경로에서 에피소드 번호 추출
        # 예: .../preprocessed/1/translation_review_llm.csv -> ep_1.xlsx
        csv_path = Path(csv_file_path)
        episode_dir = csv_path.parent.name  # "1", "2", "3" 등
        
        # preprocessed 디렉토리로 이동
        preprocessed_dir = csv_path.parent.parent
        
        # 원본 XLSX 파일 경로 구성
        xlsx_file_path = preprocessed_dir / f"ep_{episode_dir}.xlsx"
        
        if not xlsx_file_path.exists():
            print(f"경고: 원본 XLSX 파일을 찾을 수 없습니다: {xlsx_file_path}")
            return 0
        
        # XLSX 파일 읽기
        df = pd.read_excel(xlsx_file_path)
        
        # file_name과 text_box_order 칼럼이 있는지 확인
        if 'file_name' in df.columns and 'text_box_order' in df.columns:
            # 고유한 텍스트박스 수 계산
            unique_textboxes = df.groupby(['file_name', 'text_box_order']).size()
            total_unique_textboxes = len(unique_textboxes)
        else:
            # 칼럼이 없는 경우 전체 행 수 사용
            total_unique_textboxes = len(df)
        
        return total_unique_textboxes
        
    except Exception as e:
        print(f"오류: XLSX 파일에서 텍스트박스 수 계산 실패 ({csv_file_path}): {e}")
        return 0

def extract_tags_from_llm_csv(csv_file_path):
    """
    translation_review_llm.csv 파일에서 태그 정보를 추출
    
    Args:
        csv_file_path (str): CSV 파일 경로
        
    Returns:
        dict: 파일별 태그 통계 정보
    """
    try:
        # CSV 파일 읽기
        df = pd.read_csv(csv_file_path)
        
        if 'tag' not in df.columns:
            print(f"경고: '{csv_file_path}'에서 'tag' 칼럼을 찾을 수 없습니다.")
            return {
                'file_path': csv_file_path,
                'episode': Path(csv_file_path).parent.name,
                'tag_counts': {},
                'total_reviewed_items': 0,
                'total_textboxes': 0
            }
        
        # 태그 정보 추출 및 카운트
        tag_counts = defaultdict(int)
        total_reviewed_items = 0
        
        for _, row in df.iterrows():
            tag_value = row['tag']
            if pd.notna(tag_value) and str(tag_value).strip() != '':
                # 여러 태그가 쉼표로 구분된 경우 처리
                tags = [tag.strip() for tag in str(tag_value).split(',')]
                for tag in tags:
                    if tag:  # 빈 태그가 아닌 경우만
                        tag_counts[tag] += 1
                total_reviewed_items += 1
        
        # 원본 XLSX 파일에서 전체 텍스트박스 수 계산
        total_textboxes = calculate_total_textboxes_from_xlsx_unified(csv_file_path)
        
        return {
            'file_path': csv_file_path,
            'episode': Path(csv_file_path).parent.name,
            'tag_counts': dict(tag_counts),
            'total_reviewed_items': total_reviewed_items,
            'total_textboxes': total_textboxes
        }
        
    except Exception as e:
        print(f"오류: CSV 파일 처리 실패 ({csv_file_path}): {e}")
        return {
            'file_path': csv_file_path,
            'episode': Path(csv_file_path).parent.name,
            'tag_counts': {},
            'total_reviewed_items': 0,
            'total_textboxes': 0
        }

def calculate_category_score(category_name, tag_counts, total_textboxes):
    """
    특정 카테고리의 점수를 계산
    
    Args:
        category_name (str): 평가 카테고리명 ("오역", "문법", "윤문", "오탈자", "가이드 준수")
        tag_counts (dict): 태그별 발생 횟수
        total_textboxes (int): 전체 텍스트박스 수
        
    Returns:
        dict: 카테고리 평가 결과
    """
    if category_name not in EVALUATION_CRITERIA:
        return None
    
    criteria = EVALUATION_CRITERIA[category_name]
    
    # 해당 카테고리의 태그들의 총 발생 횟수 계산
    total_count = 0
    for tag in criteria["tags"]:
        total_count += tag_counts.get(tag, 0)
    
    # 퍼센트 계산
    percentage = (total_count / total_textboxes * 100) if total_textboxes > 0 else 0
    
    # 점수 결정
    if criteria["good_range"][0] <= percentage < criteria["good_range"][1]:
        score = criteria["good_score"]
        grade = "GOOD"
    elif criteria["fair_range"][0] <= percentage < criteria["fair_range"][1]:
        score = criteria["fair_score"]
        grade = "FAIR"
    else:  # poor_range
        score = criteria["poor_score"]
        grade = "POOR"
    
    return {
        "category": category_name,
        "category_en": criteria["name_en"],
        "weighted": criteria["weighted"],
        "total_count": total_count,
        "percentage": percentage,
        "score": score,
        "grade": grade,
        "tags": criteria["tags"]
    }

def calculate_total_score_and_grade(category_scores):
    """
    전체 점수 및 등급 계산
    
    Args:
        category_scores (list): 각 카테고리별 점수 정보 리스트
        
    Returns:
        dict: 전체 점수 및 등급 정보
    """
    total_score = sum(score["score"] for score in category_scores)
    
    # 등급 결정
    grade = "D"  # 기본값
    status = "불합격"
    
    for grade_name, grade_info in GRADE_CRITERIA.items():
        min_score, max_score = grade_info["range"]
        if min_score <= total_score <= max_score:
            grade = grade_name
            status = grade_info["status"]
            break
    
    return {
        "total_score": total_score,
        "max_possible_score": 24,  # 6+6+6+3+3
        "grade": grade,
        "status": status
    }

def generate_scoring_report(unified_tag_counts, total_textboxes):
    """
    점수 평가 리포트 생성
    
    Args:
        unified_tag_counts (dict): 통합 태그 발생 횟수
        total_textboxes (int): 전체 텍스트박스 수
        
    Returns:
        str: 점수 평가 리포트 텍스트
    """
    category_scores = []
    
    # 각 카테고리별 점수 계산
    for category_name in EVALUATION_CRITERIA.keys():
        score_info = calculate_category_score(category_name, unified_tag_counts, total_textboxes)
        if score_info:
            category_scores.append(score_info)
    
    # 전체 점수 및 등급 계산
    total_info = calculate_total_score_and_grade(category_scores)
    
    # 리포트 생성
    report = f"""
📊 번역 품질 평가 점수
{'='*80}

🏆 전체 결과:
- 총점: {total_info['total_score']}/{total_info['max_possible_score']}점
- 등급: {total_info['grade']} ({total_info['status']})

📋 영역별 상세 점수:
"""
    
    for score_info in category_scores:
        weighted_mark = " (가중치)" if score_info["weighted"] else ""
        report += f"""
▶ {score_info['category']} ({score_info['category_en']}){weighted_mark}
  - 발생 횟수: {score_info['total_count']}회
  - 발생 비율: {score_info['percentage']:.1f}%
  - 평가: {score_info['grade']}
  - 점수: {score_info['score']}점
  - 포함 태그: {', '.join(score_info['tags'])}"""
    
    report += f"""

📈 등급 기준:
- A등급 (합격): 21~24점
- B등급 (합격): 17~20점  
- C등급 (불합격): 11~16점
- D등급 (불합격): 2~10점

💡 평가 기준:
- GOOD: 0~10% 발생 시
- FAIR: 10~30% 발생 시  
- POOR: 30% 이상 발생 시
"""
    
    return report

def generate_individual_statistics_report(stat, output_path):
    """
    개별 에피소드의 통계 리포트 생성
    
    Args:
        stat (dict): 에피소드별 통계 정보
        output_path (str): 출력 파일 경로
    """
    timestamp = datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')
    episode = stat['episode']
    textboxes = stat['total_textboxes']
    reviewed = stat['total_reviewed_items']
    review_ratio = (reviewed / textboxes * 100) if textboxes > 0 else 0
    
    report = f"""번역 품질 분석 리포트 - 에피소드 {episode}
생성 시간: {timestamp}
{'='*50}

📊 전체 통계:
- 전체 실질 텍스트박스 수: {textboxes:,}개
- 검수된 항목 수: {reviewed}개
- 검수 비율: {review_ratio:.2f}%

🏷️ 태그별 발생 빈도 (전체 텍스트박스 기준):
"""
    
    # 정의된 순서대로 태그 표시 (없는 경우 0회로 표시)
    for tag in TAG_ORDER:
        count = stat['tag_counts'].get(tag, 0)
        tag_percentage = (count / textboxes * 100) if textboxes > 0 else 0
        report += f"  - {tag}: {count}회 ({tag_percentage:.1f}%)\n"
    
    # 파일에 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 에피소드 {episode} 통계 리포트 생성: {output_path}")

def generate_unified_statistics_report(file_statistics, output_path):
    """
    모든 파일의 통계를 통합하여 전체 리포트 생성 (전체 통계 부분만)
    
    Args:
        file_statistics (list): 각 파일별 통계 정보 리스트
        output_path (str): 출력 파일 경로
    """
    if not file_statistics:
        print("생성할 통계 데이터가 없습니다.")
        return
    
    # 전체 통계 계산
    total_files = len(file_statistics)
    total_textboxes = sum(stat['total_textboxes'] for stat in file_statistics)
    total_reviewed_items = sum(stat['total_reviewed_items'] for stat in file_statistics)
    
    # 전체 태그 통계 통합
    unified_tag_counts = defaultdict(int)
    for stat in file_statistics:
        for tag, count in stat['tag_counts'].items():
            unified_tag_counts[tag] += count
    
    # 리포트 생성 (전체 통계 부분만)
    timestamp = datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')
    
    report = f"""통합 번역 품질 분석 리포트
생성 시간: {timestamp}
{'='*80}

📊 전체 통계:
- 분석된 에피소드 수: {total_files}개
- 전체 실질 텍스트박스 수: {total_textboxes:,}개
- 검수된 항목 수: {total_reviewed_items}개
- 검수 비율: {(total_reviewed_items / total_textboxes * 100) if total_textboxes > 0 else 0:.2f}%

🏷️ 태그별 발생 빈도 (전체 텍스트박스 기준):
"""
    
    # 정의된 순서대로 태그 표시 (없는 경우 0회로 표시)
    for tag in TAG_ORDER:
        count = unified_tag_counts.get(tag, 0)
        percentage = (count / total_textboxes) * 100 if total_textboxes > 0 else 0
        report += f"  - {tag}: {count}회 ({percentage:.1f}%)\n"
    
    # 점수 평가 리포트 추가
    scoring_report = generate_scoring_report(unified_tag_counts, total_textboxes)
    report += scoring_report
    
    # 파일에 저장
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 통합 통계 리포트가 생성되었습니다: {output_path}")
    print(f"   - 분석된 에피소드: {total_files}개")
    print(f"   - 전체 텍스트박스: {total_textboxes:,}개")
    print(f"   - 검수된 항목: {total_reviewed_items}개")

def process_unified_statistics(base_path):
    """
    지정된 경로의 모든 translation_review_llm.csv 파일을 처리하여 통합 통계 생성
    
    Args:
        base_path (str): 기본 검색 경로
    """
    print(f"\n{'='*80}")
    print(f"통합 통계 생성 시작")
    print(f"기본 경로: {base_path}")
    print(f"{'='*80}")
    
    # 모든 translation_review_llm.csv 파일 찾기
    llm_csv_files = find_llm_csv_files(base_path)
    
    if not llm_csv_files:
        print(f"'{base_path}' 경로에서 translation_review_llm.csv 파일을 찾을 수 없습니다.")
        return
    
    print(f"발견된 파일 목록:")
    for i, csv_file in enumerate(llm_csv_files, 1):
        episode_name = Path(csv_file).parent.name
        print(f"  {i}. 에피소드 {episode_name}: {csv_file}")
    
    # 각 파일에서 통계 추출 및 개별 리포트 생성
    file_statistics = []
    
    print(f"\n📊 파일별 통계 추출 및 개별 리포트 생성 중...")
    for csv_file in llm_csv_files:
        csv_path = Path(csv_file)
        episode_name = csv_path.parent.name
        print(f"처리 중: 에피소드 {episode_name}")
        
        # 통계 추출
        stat = extract_tags_from_llm_csv(csv_file)
        file_statistics.append(stat)
        
        # 개별 에피소드 statistics_summary.txt 생성
        individual_output_path = csv_path.parent / "statistics_summary.txt"
        generate_individual_statistics_report(stat, individual_output_path)
    
    # 통합 리포트 생성 (전체 통계 부분만)
    output_path = Path(base_path) / "unified_statistics_summary.txt"
    generate_unified_statistics_report(file_statistics, output_path)

def find_preprocessed_directory(project_uuid, episode_number):
    """project_uuid와 episode_number를 기반으로 preprocessed 디렉토리 경로 찾기"""
    # 기본 data 디렉토리 경로 (상대경로)
    base_data_dir = "../data"
    project_dir = os.path.join(base_data_dir, project_uuid)
    
    if not os.path.exists(project_dir):
        print(f"❌ 프로젝트 디렉토리를 찾을 수 없습니다: {project_dir}")
        return None
    
    # episode_number 디렉토리 찾기
    episode_dir = os.path.join(project_dir, episode_number)
    if not os.path.exists(episode_dir):
        print(f"❌ 에피소드 디렉토리를 찾을 수 없습니다: {episode_dir}")
        return None
    
    # preprocessed 디렉토리 찾기
    preprocessed_dir = os.path.join(episode_dir, "preprocessed")
    if not os.path.exists(preprocessed_dir):
        print(f"❌ preprocessed 디렉토리를 찾을 수 없습니다: {preprocessed_dir}")
        return None
    
    return preprocessed_dir

def main():
    """메인 함수"""
    import sys
    
    # 명령행 인자 확인
    if len(sys.argv) != 3:
        print("❌ 사용법: python3 5_generate_unified_statistics.py <project_uuid> <episode_number>")
        return
    
    project_uuid = sys.argv[1]
    episode_number = sys.argv[2]
    
    print(f"🔍 프로젝트 UUID: {project_uuid}")
    print(f"🔍 에피소드 번호: {episode_number}")
    
    # preprocessed 디렉토리 자동 검색
    base_path = find_preprocessed_directory(project_uuid, episode_number)
    if not base_path:
        return
    
    print(f"📁 기본 경로: {base_path}")
    
    # 통합 통계 처리 실행
    process_unified_statistics(base_path)

if __name__ == "__main__":
    main()
