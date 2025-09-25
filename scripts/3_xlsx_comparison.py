#!/usr/bin/env python3
"""
preprocessed 폴더 내 XLSX 파일들을 자동으로 처리하여 
각 파일별로 디렉토리를 생성하고 번역검수/식자번역검수 결과를 분리 저장하는 스크립트
"""

import pandas as pd
import os
import sys
import glob
from pathlib import Path
import difflib
import jiwer
import re
from typing import Tuple, List

def calculate_cer(reference: str, hypothesis: str) -> float:
    """
    Character Error Rate (CER) 계산
    
    Args:
        reference (str): 참조 텍스트 (target)
        hypothesis (str): 비교 텍스트 (val)
        
    Returns:
        float: CER 값 (0.0 ~ 1.0)
    """
    if not reference or not hypothesis:
        return 1.0 if reference != hypothesis else 0.0
    
    # 문자 단위로 분할
    ref_chars = list(str(reference))
    hyp_chars = list(str(hypothesis))
    
    # 편집 거리 계산
    d = [[0 for _ in range(len(hyp_chars) + 1)] for _ in range(len(ref_chars) + 1)]
    
    for i in range(len(ref_chars) + 1):
        d[i][0] = i
    for j in range(len(hyp_chars) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_chars) + 1):
        for j in range(1, len(hyp_chars) + 1):
            if ref_chars[i-1] == hyp_chars[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(d[i-1][j] + 1,      # 삭제
                             d[i][j-1] + 1,       # 삽입
                             d[i-1][j-1] + 1)     # 치환
    
    return d[len(ref_chars)][len(hyp_chars)] / len(ref_chars)

def calculate_wer(reference: str, hypothesis: str) -> float:
    """
    Word Error Rate (WER) 계산
    
    Args:
        reference (str): 참조 텍스트 (target)
        hypothesis (str): 비교 텍스트 (val)
        
    Returns:
        float: WER 값 (0.0 ~ 1.0)
    """
    if not reference or not hypothesis:
        return 1.0 if reference != hypothesis else 0.0
    
    try:
        return jiwer.wer(str(reference), str(hypothesis))
    except:
        # jiwer 실패 시 간단한 단어 기반 계산
        ref_words = str(reference).split()
        hyp_words = str(hypothesis).split()
        
        if len(ref_words) == 0:
            return 0.0 if len(hyp_words) == 0 else 1.0
        
        # 간단한 단어 단위 편집 거리
        d = [[0 for _ in range(len(hyp_words) + 1)] for _ in range(len(ref_words) + 1)]
        
        for i in range(len(ref_words) + 1):
            d[i][0] = i
        for j in range(len(hyp_words) + 1):
            d[0][j] = j
        
        for i in range(1, len(ref_words) + 1):
            for j in range(1, len(hyp_words) + 1):
                if ref_words[i-1] == hyp_words[j-1]:
                    d[i][j] = d[i-1][j-1]
                else:
                    d[i][j] = min(d[i-1][j] + 1,      # 삭제
                                 d[i][j-1] + 1,       # 삽입
                                 d[i-1][j-1] + 1)     # 치환
        
        return d[len(ref_words)][len(hyp_words)] / len(ref_words)


def calculate_translation_metrics(translation_rows: pd.DataFrame, all_df: pd.DataFrame) -> dict:
    """
    번역검수 결과에 대한 전체 메트릭 계산 (전체 고유 텍스트박스 기준)
    
    Args:
        translation_rows (DataFrame): 번역검수 대상 행들
        all_df (DataFrame): 전체 데이터프레임
        
    Returns:
        dict: 계산된 메트릭들
    """
    if 'file_name' not in all_df.columns or 'text_box_order' not in all_df.columns:
        # 칼럼이 없는 경우 기존 방식 사용
        if len(translation_rows) == 0:
            return {
                'total_pairs': 0,
                'unique_textboxes': 0,
                'cell_avg_cer': 0.0,
                'cell_avg_wer': 0.0,
                'overall_cer': 0.0,
                'overall_wer': 0.0,
                'cer_scores': [],
                'wer_scores': []
            }
        unique_rows = translation_rows
        all_target_text = []
        all_val_text = []
        cer_scores = []
        wer_scores = []
        
        for _, row in unique_rows.iterrows():
            target = str(row['target']) if pd.notna(row['target']) else ""
            val = str(row['val']) if pd.notna(row['val']) else ""
            
            cer = calculate_cer(target, val)
            wer = calculate_wer(target, val)
            
            cer_scores.append(cer)
            wer_scores.append(wer)
            all_target_text.append(target)
            all_val_text.append(val)
    else:
        # 전체 고유 텍스트박스 기준으로 계산
        # 1. 전체 고유 텍스트박스 목록 생성
        all_unique_textboxes = all_df.groupby(['file_name', 'text_box_order']).first().reset_index()
        
        # 2. 번역검수 대상 텍스트박스들 (중복 제거)
        if len(translation_rows) > 0:
            translation_unique = translation_rows.groupby(['file_name', 'text_box_order']).first().reset_index()
            # 번역검수 대상 텍스트박스들을 dict로 변환 (빠른 검색을 위해)
            translation_dict = {}
            for _, row in translation_unique.iterrows():
                key = (row['file_name'], row['text_box_order'])
                translation_dict[key] = row
        else:
            translation_dict = {}
        
        cer_scores = []
        wer_scores = []
        all_target_text = []
        all_val_text = []
        
        # 3. 모든 고유 텍스트박스에 대해 CER/WER 계산
        for _, row in all_unique_textboxes.iterrows():
            key = (row['file_name'], row['text_box_order'])
            
            if key in translation_dict:
                # 번역검수 대상인 경우: 수정된 텍스트 사용
                translation_row = translation_dict[key]
                target = str(translation_row['target']) if pd.notna(translation_row['target']) else ""
                val = str(translation_row['val']) if pd.notna(translation_row['val']) else ""
            else:
                # 번역검수 대상이 아닌 경우: target = val (수정되지 않음)
                target = str(row['target']) if pd.notna(row['target']) else ""
                val = target  # 수정되지 않았으므로 동일
            
            # CER/WER 계산
            cer = calculate_cer(target, val)
            wer = calculate_wer(target, val)
            
            cer_scores.append(cer)
            wer_scores.append(wer)
            all_target_text.append(target)
            all_val_text.append(val)
    
    # 전체 텍스트 기준 CER/WER 계산
    combined_target = " ".join(all_target_text)
    combined_val = " ".join(all_val_text)
    
    overall_cer = calculate_cer(combined_target, combined_val)
    overall_wer = calculate_wer(combined_target, combined_val)
    
    return {
        'total_pairs': len(translation_rows),  # 번역검수 대상 원본 행 수
        'unique_textboxes': len(all_target_text),  # 전체 고유 텍스트박스 수
        'modified_textboxes': len([cer for cer in cer_scores if cer > 0]),  # 실제 수정된 텍스트박스 수
        'cell_avg_cer': sum(cer_scores) / len(cer_scores) if cer_scores else 0.0,
        'cell_avg_wer': sum(wer_scores) / len(wer_scores) if wer_scores else 0.0,
        'overall_cer': overall_cer,
        'overall_wer': overall_wer,
        'cer_scores': cer_scores,
        'wer_scores': wer_scores
    }

def merge_feedback_v2_comments(df):
    """
    동일한 target-val 세트에 대해 여러 개의 FEEDBACK_V2 행이 있으면 
    comment를 합쳐서 하나로 통합
    
    Args:
        df (DataFrame): 원본 데이터프레임
        
    Returns:
        DataFrame: FEEDBACK_V2 comment가 통합된 데이터프레임
    """
    # FEEDBACK_V2가 아닌 행들은 그대로 유지
    non_feedback_v2 = df[df['type'] != 'FEEDBACK_V2'].copy()
    
    # FEEDBACK_V2 행들만 추출
    feedback_v2_rows = df[df['type'] == 'FEEDBACK_V2'].copy()
    
    if len(feedback_v2_rows) == 0:
        return df
    
    # target-val 쌍별로 그룹화하여 comment 통합
    merged_feedback_v2 = []
    
    # target-val 쌍별로 그룹화
    grouped = feedback_v2_rows.groupby(['target', 'val'])
    
    for (target, val), group in grouped:
        if len(group) == 1:
            # 단일 행인 경우 그대로 추가
            merged_feedback_v2.append(group.iloc[0])
        else:
            # 여러 행인 경우 comment 통합
            base_row = group.iloc[0].copy()
            
            # comment들을 수집 (비어있지 않은 것만)
            comments = []
            for _, row in group.iterrows():
                comment = row['comment']
                if pd.notna(comment) and str(comment).strip() != '':
                    comments.append(str(comment).strip())
            
            # comment 통합 (구분자: " | ")
            if comments:
                base_row['comment'] = " | ".join(comments)
            
            merged_feedback_v2.append(base_row)
    
    # 통합된 FEEDBACK_V2 데이터프레임 생성
    if merged_feedback_v2:
        merged_feedback_v2_df = pd.DataFrame(merged_feedback_v2)
        # 원래 순서대로 정렬하기 위해 인덱스 기준으로 정렬
        merged_feedback_v2_df = merged_feedback_v2_df.sort_index()
    else:
        merged_feedback_v2_df = pd.DataFrame(columns=df.columns)
    
    # 전체 데이터프레임 재구성
    result_df = pd.concat([non_feedback_v2, merged_feedback_v2_df], ignore_index=True)
    
    return result_df

def filter_empty_target_rows(df):
    """
    target이 비어있는 행들을 따로 분리
    
    Args:
        df (DataFrame): 원본 데이터프레임
        
    Returns:
        tuple: (비교할 데이터프레임, target이 비어있는 데이터프레임)
    """
    # target이 비어있는 행들 (NaN 또는 빈 문자열)
    empty_target_mask = df['target'].isna() | (df['target'] == '') | (df['target'].astype(str).str.strip() == '')
    
    empty_target_rows = df[empty_target_mask].copy()
    valid_target_rows = df[~empty_target_mask].copy()
    
    return valid_target_rows, empty_target_rows

def remove_duplicates_with_feedback_v2(df):
    """
    FEEDBACK_V2 타입과 동일한 target, val 값을 가지지만 
    type, operation, comment가 비어있는 중복 행들을 제거
    
    Args:
        df (DataFrame): 원본 데이터프레임
        
    Returns:
        DataFrame: 중복이 제거된 데이터프레임
    """
    # FEEDBACK_V2 타입인 행들의 target, val 값들을 수집
    feedback_v2_rows = df[df['type'] == 'FEEDBACK_V2']
    feedback_v2_pairs = set()
    
    for _, row in feedback_v2_rows.iterrows():
        target_val = (row['target'], row['val'])
        feedback_v2_pairs.add(target_val)
    
    # 제거할 중복 행들을 찾기
    duplicate_indices = []
    
    for idx, row in df.iterrows():
        # FEEDBACK_V2가 아닌 행들 중에서
        if row['type'] != 'FEEDBACK_V2':
            target_val = (row['target'], row['val'])
            
            # FEEDBACK_V2와 동일한 (target, val) 쌍이고
            if target_val in feedback_v2_pairs:
                # type, operation, comment가 모두 비어있거나 NaN인 경우
                is_empty_type = pd.isna(row['type']) or row['type'] == ''
                is_empty_operation = pd.isna(row['operation']) or row['operation'] == ''
                is_empty_comment = pd.isna(row['comment']) or row['comment'] == ''
                
                if is_empty_type and is_empty_operation and is_empty_comment:
                    duplicate_indices.append(idx)
    
    # 중복 행들 제거
    cleaned_df = df.drop(duplicate_indices).reset_index(drop=True)
    
    return cleaned_df

def get_original_different_rows(df, output_columns):
    """
    FEEDBACK_V2가 통합되지 않은 원본 데이터에서 target과 val이 다른 행들을 찾음
    
    Args:
        df (DataFrame): 원본 데이터프레임 (FEEDBACK_V2 통합 전)
        output_columns (list): 출력할 칼럼들
        
    Returns:
        DataFrame: target과 val이 다른 행들
    """
    # target과 val 칼럼 비교 (exact match)
    # NaN 값도 고려하여 비교
    different_rows = df[df['target'] != df['val']]
    
    # NaN 값이 둘 다 있는 경우는 같은 것으로 처리
    both_nan = df['target'].isna() & df['val'].isna()
    different_rows = df[~both_nan & (df['target'] != df['val'])]
    
    return different_rows

def process_single_file(file_path, output_dir):
    """
    단일 XLSX 파일을 처리하여 번역검수/식자번역검수 결과를 분리 저장
    
    Args:
        file_path (str): 처리할 XLSX 파일 경로
        output_dir (str): 결과를 저장할 디렉토리
    
    Returns:
        dict: 처리 결과 통계
    """
    try:
        print(f"📖 파일 처리 중: {os.path.basename(file_path)}")
        
        # XLSX 파일 읽기
        df = pd.read_excel(file_path)
        
        # 필요한 칼럼들이 존재하는지 확인
        required_columns = ['target', 'val']
        output_columns = ['target', 'val', 'type', 'operation', 'comment', 'tag', 'file_name', 'text_box_order']
        
        missing_required = [col for col in required_columns if col not in df.columns]
        if missing_required:
            print(f"❌ 오류: 필수 칼럼이 없습니다: {missing_required}")
            return None
        
        # 존재하는 칼럼만 사용
        output_columns = [col for col in output_columns if col in df.columns]
        
        # 1단계: FEEDBACK_V2 comment 통합
        df_merged = merge_feedback_v2_comments(df)
        
        # 2단계: target이 비어있는 행들 분리
        df_valid_target, df_empty_target = filter_empty_target_rows(df_merged)
        
        # 3단계: FEEDBACK_V2와 중복되는 빈 행들 제거 (target이 유효한 행들만)
        df_cleaned = remove_duplicates_with_feedback_v2(df_valid_target)
        
        # target과 val 칼럼 비교 (exact match)
        both_nan = df_cleaned['target'].isna() & df_cleaned['val'].isna()
        different_rows = df_cleaned[~both_nan & (df_cleaned['target'] != df_cleaned['val'])]
        
        if len(different_rows) == 0:
            print(f"✅ {os.path.basename(file_path)}: target과 val이 모두 일치합니다.")
            
            # 고유한 텍스트박스 수 계산 (일치하는 경우에도) - 정리된 데이터 기준
            if 'file_name' in df_cleaned.columns and 'text_box_order' in df_cleaned.columns:
                unique_textboxes_count = len(df_cleaned.groupby(['file_name', 'text_box_order']))
            else:
                unique_textboxes_count = len(df_cleaned)
            
            return {
                'file_name': os.path.basename(file_path),
                'total_data_rows': len(df),
                'unique_textboxes': unique_textboxes_count,
                'different_rows': 0,
                'translation_rows': 0,
                'typography_rows': 0
            }
        
        # operation에 따라 분리
        typography_operation = "식자번역검수(웹툰)"
        translation_rows = different_rows[different_rows['operation'] != typography_operation]
        
        # 번역검수 결과 (필터링 없이 모든 변경사항 포함)
        translation_rows_filtered = translation_rows
        print(f"   📊 번역검수 결과: {len(translation_rows_filtered)}행 (모든 변경사항 포함)")
        
        # 번역검수 결과 저장 (FEEDBACK_V2 통합된 버전)
        if len(translation_rows_filtered) > 0:
            translation_file = os.path.join(output_dir, "translation_review.csv")
            translation_rows_filtered[output_columns].to_csv(translation_file, index=False, encoding='utf-8-sig')
            print(f"   📝 번역검수 결과 저장: {len(translation_rows_filtered)}행")
            
            # 번역 품질 메트릭 계산 (전체 고유 텍스트박스 기준)
            metrics = calculate_translation_metrics(translation_rows_filtered, df_cleaned)
            
            # 번역 통계 정보를 텍스트 파일로 저장
            metrics_file = os.path.join(output_dir, "translation_statistics.txt")
            
        # 전체 행 수와 수정 비율 계산
        # file_name과 text_box_order 기준으로 고유한 텍스트박스 수 계산
        # 정리된 데이터(df_cleaned) 기준으로 계산하여 일관성 유지
        if 'file_name' in df_cleaned.columns and 'text_box_order' in df_cleaned.columns:
            unique_textboxes = df_cleaned.groupby(['file_name', 'text_box_order']).size()
            total_unique_textboxes = len(unique_textboxes)
        else:
            # 칼럼이 없는 경우 기존 방식 사용
            total_unique_textboxes = len(df_cleaned)
        
        total_data_rows = len(df)  # 전체 데이터 행 수 (참고용)
        total_different_rows = len(different_rows)
        filtered_translation_rows = len(translation_rows_filtered)  # 번역검수 대상 행 수
        
        # 수정 비율은 고유한 텍스트박스 수 대비로 계산
        modification_ratio = (filtered_translation_rows / total_unique_textboxes * 100) if total_unique_textboxes > 0 else 0
        
        with open(metrics_file, 'w', encoding='utf-8') as f:
            f.write(f"번역 품질 메트릭 - {os.path.basename(file_path)}\n")
            f.write("=" * 50 + "\n\n")
            
            # 검수된 텍스트박스 비율 계산 (번역검수 대상 행 수 / 전체 텍스트박스)
            if filtered_translation_rows > 0:
                reviewed_ratio = (filtered_translation_rows / total_unique_textboxes * 100) if total_unique_textboxes > 0 else 0
                
                f.write("📊 전체 통계:\n")
                f.write(f"  - 전체 실질 텍스트박스 수: {total_unique_textboxes:,}개\n")
                f.write(f"  - 번역검수 대상 행 수: {filtered_translation_rows}개\n")
                f.write(f"  - 수정되지 않은 텍스트박스: {metrics['unique_textboxes'] - metrics['modified_textboxes']}개\n")
                f.write(f"  - 검수된 텍스트박스 비율: {reviewed_ratio:.2f}%\n\n")
                
                f.write("📈 번역 품질 메트릭 (전체 고유 텍스트박스 기준):\n\n")
                f.write(f"전체 텍스트박스 평균:\n")
                f.write(f"  - 평균 CER: {metrics['cell_avg_cer']:.4f} ({metrics['cell_avg_cer']*100:.2f}%)\n")
                f.write(f"  - 평균 WER: {metrics['cell_avg_wer']:.4f} ({metrics['cell_avg_wer']*100:.2f}%)\n\n")
                f.write(f"전체 텍스트 기준:\n")
                f.write(f"  - 전체 CER: {metrics['overall_cer']:.4f} ({metrics['overall_cer']*100:.2f}%)\n")
                f.write(f"  - 전체 WER: {metrics['overall_wer']:.4f} ({metrics['overall_wer']*100:.2f}%)\n")
            else:
                f.write("📊 전체 통계:\n")
                f.write(f"  - 전체 실질 텍스트박스 수: {total_unique_textboxes:,}개\n")
                f.write(f"  - 번역검수 대상 행 수: 0개\n")
                f.write(f"  - 수정되지 않은 텍스트박스: {total_unique_textboxes}개\n")
                f.write(f"  - 검수된 텍스트박스 비율: 0.00%\n\n")
                f.write("📈 번역 품질 메트릭: 해당 없음 (번역검수 대상 없음)\n")
        
        # 식자번역검수 결과 저장 (FEEDBACK_V2 분리된 원본 버전)
        df_valid_target_cleaned = remove_duplicates_with_feedback_v2(df_valid_target)
        original_different_rows = get_original_different_rows(df_valid_target_cleaned, output_columns)
        typography_rows_original = original_different_rows[original_different_rows['operation'] == typography_operation]
        
        if len(typography_rows_original) > 0:
            typography_file = os.path.join(output_dir, "typesetting_review.csv")
            typography_rows_original[output_columns].to_csv(typography_file, index=False, encoding='utf-8-sig')
            print(f"   🎨 식자번역검수 결과 저장: {len(typography_rows_original)}행")
        
        # 고유한 텍스트박스 수 계산 (반환용) - 정리된 데이터 기준으로 일관성 유지
        if 'file_name' in df_cleaned.columns and 'text_box_order' in df_cleaned.columns:
            unique_textboxes_count = len(df_cleaned.groupby(['file_name', 'text_box_order']))
        else:
            unique_textboxes_count = len(df_cleaned)
        
        return {
            'file_name': os.path.basename(file_path),
            'total_data_rows': len(df),
            'unique_textboxes': unique_textboxes_count,
            'different_rows': len(different_rows),
            'translation_rows': len(translation_rows_filtered) if 'translation_rows_filtered' in locals() else len(translation_rows),
            'typography_rows': len(typography_rows_original)
        }
        
    except Exception as e:
        print(f"❌ 오류 발생 ({os.path.basename(file_path)}): {str(e)}")
        return None

def batch_process_xlsx_files(input_directory):
    """
    입력 디렉토리 내의 모든 XLSX 파일을 배치 처리
    
    Args:
        input_directory (str): 입력 디렉토리 경로
    """
    try:
        # 입력 디렉토리 확인
        if not os.path.exists(input_directory):
            print(f"❌ 오류: 입력 디렉토리가 존재하지 않습니다: {input_directory}")
            return
        
        # XLSX 파일 목록 가져오기 (Excel 임시 파일 제외)
        all_xlsx_files = glob.glob(os.path.join(input_directory, "*.xlsx"))
        
        # Excel 임시 파일 필터링 (~$로 시작하는 파일들 제외)
        xlsx_files = [f for f in all_xlsx_files if not os.path.basename(f).startswith('~$')]
        
        if not xlsx_files:
            print(f"❌ 오류: {input_directory}에서 XLSX 파일을 찾을 수 없습니다.")
            return
        
        # 필터링된 임시 파일이 있으면 알림
        filtered_count = len(all_xlsx_files) - len(xlsx_files)
        if filtered_count > 0:
            print(f"📋 Excel 임시 파일 {filtered_count}개 제외됨")
        
        print("=" * 80)
        print("📊 배치 XLSX 파일 비교 도구")
        print("=" * 80)
        print(f"📂 입력 디렉토리: {input_directory}")
        print(f"📋 발견된 파일 수: {len(xlsx_files)}")
        print()
        
        results = []
        
        for xlsx_file in xlsx_files:
            # 파일명에서 "ep_" 뒤의 숫자 부분 추출 (확장자 제외)
            filename = os.path.basename(xlsx_file)
            if filename.startswith("ep_") and filename.endswith(".xlsx"):
                # ep_1.xlsx -> 1
                episode_num = filename[3:-5]  # "ep_"를 제거하고 ".xlsx"도 제거
                
                # 출력 디렉토리 생성
                output_dir = os.path.join(input_directory, episode_num)
                Path(output_dir).mkdir(parents=True, exist_ok=True)
                
                # 파일 처리
                result = process_single_file(xlsx_file, output_dir)
                if result:
                    results.append(result)
            else:
                print(f"⚠️  건너뛰기: {filename} (ep_*.xlsx 형식이 아님)")
        
        # 전체 결과 요약
        if results:
            print("\n" + "=" * 80)
            print("📊 전체 처리 결과 요약")
            print("=" * 80)
            
            total_files = len(results)
            total_unique_textboxes = sum(r['unique_textboxes'] for r in results)
            total_data_rows = sum(r['total_data_rows'] for r in results)
            total_translation_rows = sum(r['translation_rows'] for r in results)
            total_typography_rows = sum(r['typography_rows'] for r in results)
            
            overall_modification_ratio = (total_translation_rows / total_unique_textboxes * 100) if total_unique_textboxes > 0 else 0
            
            print(f"✅ 처리 완료된 파일 수: {total_files}")
            print(f"📊 전체 고유 텍스트박스 수: {total_unique_textboxes:,}개")
            print(f"📋 전체 데이터 행 수: {total_data_rows:,}개 (중복 포함)")
            print(f"📝 전체 번역검수 행 수: {total_translation_rows}")
            print(f"🎨 전체 식자번역검수 행 수: {total_typography_rows}")
            print(f"📈 전체 수정 비율: {overall_modification_ratio:.2f}%")
            print()
            
            print("파일별 상세 결과:")
            for result in results:
                file_modification_ratio = (result['translation_rows'] / result['unique_textboxes'] * 100) if result['unique_textboxes'] > 0 else 0
                print(f"  📄 {result['file_name']}: "
                      f"텍스트박스 {result['unique_textboxes']}개, "
                      f"번역검수 {result['translation_rows']}행 ({file_modification_ratio:.1f}%), "
                      f"식자검수 {result['typography_rows']}행")
        
    except Exception as e:
        print(f"❌ 배치 처리 중 오류 발생: {str(e)}")

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
    # 명령행 인자 확인
    if len(sys.argv) != 3:
        print("❌ 사용법: python3 3_xlsx_comparison.py <project_uuid> <episode_number>")
        return
    
    project_uuid = sys.argv[1]
    episode_number = sys.argv[2]
    
    print(f"🔍 프로젝트 UUID: {project_uuid}")
    print(f"🔍 에피소드 번호: {episode_number}")
    
    # preprocessed 디렉토리 자동 검색
    input_directory = find_preprocessed_directory(project_uuid, episode_number)
    if not input_directory:
        return
    
    print(f"📁 입력 디렉토리: {input_directory}")
    
    batch_process_xlsx_files(input_directory)

if __name__ == "__main__":
    main()
