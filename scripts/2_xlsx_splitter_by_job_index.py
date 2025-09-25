#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
XLSX 파일을 job_index 컬럼 기준으로 분할하는 스크립트

사용법:
    python3 xlsx_splitter_by_job_index.py
"""

import pandas as pd
import os
import sys
from pathlib import Path


def split_xlsx_by_job_index(input_file_path, output_directory=None):
    """
    XLSX 파일을 job_index 컬럼 기준으로 분할하여 별도 파일로 저장
    
    Args:
        input_file_path (str): 입력 XLSX 파일 경로
        output_directory (str, optional): 출력 디렉토리. 기본값은 입력 파일과 같은 디렉토리
    
    Returns:
        list: 생성된 파일 경로 목록
    """
    try:
        # 입력 파일 읽기
        print(f"📖 파일을 읽는 중: {input_file_path}")
        df = pd.read_excel(input_file_path)
        
        # job_index 컬럼 존재 확인
        if 'job_index' not in df.columns:
            raise ValueError("입력 파일에 'job_index' 컬럼이 없습니다.")
        
        # 출력 디렉토리 설정
        if output_directory is None:
            output_directory = os.path.dirname(input_file_path)
        
        # 출력 디렉토리 생성
        Path(output_directory).mkdir(parents=True, exist_ok=True)
        
        # job_index별 고유값 확인
        unique_job_indices = sorted(df['job_index'].unique())
        print(f"🔍 발견된 job_index 값들: {unique_job_indices}")
        
        created_files = []
        
        # 각 job_index별로 파일 분할
        for job_idx in unique_job_indices:
            # 해당 job_index의 데이터만 필터링
            filtered_df = df[df['job_index'] == job_idx].copy()
            
            # 출력 파일명 생성 (ep_{job_index}.xlsx 형식)
            output_filename = f"ep_{job_idx}.xlsx"
            output_path = os.path.join(output_directory, output_filename)
            
            # Excel 파일로 저장
            filtered_df.to_excel(output_path, index=False, engine='openpyxl')
            created_files.append(output_path)
            
            print(f"✅ 생성됨: {output_filename} ({len(filtered_df)} 행)")
        
        return created_files
        
    except FileNotFoundError:
        print(f"❌ 오류: 입력 파일을 찾을 수 없습니다: {input_file_path}")
        return []
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return []


def find_input_file(project_uuid, episode_number):
    """project_uuid와 episode_number를 기반으로 입력 파일 경로 찾기"""
    # 기본 data 디렉토리 경로
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
    
    # xlsx 파일 찾기 (ep_{episode_number}.xlsx 형태)
    xlsx_filename = f"ep_{episode_number}.xlsx"
    xlsx_path = os.path.join(episode_dir, xlsx_filename)
    
    if os.path.exists(xlsx_path):
        return xlsx_path
    
    # 다른 xlsx 파일들 검색
    for file in os.listdir(episode_dir):
        if file.lower().endswith(('.xlsx', '.xls')):
            xlsx_path = os.path.join(episode_dir, file)
            print(f"📋 발견된 Excel 파일: {xlsx_path}")
            return xlsx_path
    
    print(f"❌ {episode_dir}에서 Excel 파일을 찾을 수 없습니다.")
    return None

def main():
    """메인 함수"""
    print("=" * 60)
    print("📊 XLSX 파일 job_index 기준 분할 도구")
    print("=" * 60)
    
    # 명령행 인자 확인
    if len(sys.argv) != 3:
        print("❌ 사용법: python3 2_xlsx_splitter_by_job_index.py <project_uuid> <episode_number>")
        return
    
    project_uuid = sys.argv[1]
    episode_number = sys.argv[2]
    
    print(f"🔍 프로젝트 UUID: {project_uuid}")
    print(f"🔍 에피소드 번호: {episode_number}")
    
    # 입력 파일 자동 검색
    input_file = find_input_file(project_uuid, episode_number)
    if not input_file:
        return
    
    print(f"📁 입력 파일: {input_file}")
    
    # 입력 파일이 들어있는 디렉토리 파싱
    input_dir = os.path.dirname(input_file)
    
    # 출력 디렉토리 (preprocessed 폴더)
    output_dir = input_dir + "/preprocessed"
    
    print(f"📁 출력 디렉토리: {output_dir}")
    
    # 파일 분할 실행
    created_files = split_xlsx_by_job_index(input_file, output_dir)
    
    if created_files:
        print("\n🎉 분할 완료!")
        print("생성된 파일들:")
        for file_path in created_files:
            print(f"  - {file_path}")
    else:
        print("\n❌ 파일 분할에 실패했습니다.")


if __name__ == "__main__":
    main()
