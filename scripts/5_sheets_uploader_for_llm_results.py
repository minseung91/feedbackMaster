#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
4_comment_generator.py 결과를 Google Sheets에 업로드하는 모듈
translation_review_llm.csv 파일들을 수집하여 "번역 식사 검수 코멘트 생성 시트"에 업로드
"""

import pandas as pd
import os
import sys
from pathlib import Path
import re
from datetime import datetime
import logging
import gspread
from google.oauth2.service_account import Credentials

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TranslationReviewSheetsUploader:
    """번역 검수 결과를 Google Sheets에 업로드하는 클래스"""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        """
        초기화
        
        Args:
            credentials_path (str): Google API credentials.json 파일 경로
            spreadsheet_id (str): 대상 Google Spreadsheet ID
        """
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.client = self._authenticate()
    
    def _authenticate(self):
        """Google Sheets API 인증"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            credentials = Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=scopes
            )
            return gspread.authorize(credentials)
        except Exception as e:
            logger.error(f"Google Sheets API 인증 실패: {e}")
            raise
        
    def extract_project_uuid(self, file_path: str) -> str:
        """
        파일 경로에서 project_uuid 추출
        
        Args:
            file_path (str): translation_review_llm.csv 파일 경로
            
        Returns:
            str: project_uuid (예: "60af877a-4d7e-465a-875d-37c6f324917e")
        """
        try:
            # UUID 패턴 매칭 (8-4-4-4-12 형식)
            uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
            match = re.search(uuid_pattern, file_path, re.IGNORECASE)
            
            if match:
                return match.group(1)
            else:
                logger.warning(f"UUID를 찾을 수 없습니다: {file_path}")
                return "unknown"
                
        except Exception as e:
            logger.error(f"UUID 추출 실패: {e}")
            return "unknown"
    
    def extract_episode_number(self, file_path: str) -> str:
        """
        파일 경로에서 에피소드 번호 추출
        
        Args:
            file_path (str): translation_review_llm.csv 파일 경로
            
        Returns:
            str: 에피소드 번호 (예: "1", "2", "3")
        """
        try:
            path = Path(file_path)
            # 파일이 있는 디렉토리 이름이 에피소드 번호 (예: "1", "2", "3")
            episode_dir = path.parent.name
            
            # 숫자인지 확인
            if episode_dir.isdigit():
                return episode_dir
            else:
                logger.warning(f"에피소드 번호를 찾을 수 없습니다: {file_path}")
                return "unknown"
                
        except Exception as e:
            logger.error(f"에피소드 번호 추출 실패: {e}")
            return "unknown"
    
    def get_project_name_from_xlsx(self, file_path: str) -> str:
        """
        해당하는 ep_X.xlsx 파일에서 job_name 값을 추출
        
        Args:
            file_path (str): translation_review_llm.csv 파일 경로
            
        Returns:
            str: project_name (job_name 값)
        """
        try:
            path = Path(file_path)
            episode_num = path.parent.name  # "1", "2", "3" 등
            
            # preprocessed 디렉토리로 이동
            preprocessed_dir = path.parent.parent
            
            # 해당 에피소드의 XLSX 파일 경로
            xlsx_file_path = preprocessed_dir / f"ep_{episode_num}.xlsx"
            
            if not xlsx_file_path.exists():
                logger.warning(f"XLSX 파일을 찾을 수 없습니다: {xlsx_file_path}")
                return "unknown"
            
            # XLSX 파일 읽기
            df = pd.read_excel(xlsx_file_path)
            
            # job_name 칼럼에서 첫 번째 값 가져오기
            if 'job_name' in df.columns:
                job_names = df['job_name'].dropna().unique()
                if len(job_names) > 0:
                    project_name = str(job_names[0])
                    logger.info(f"프로젝트명 추출: {project_name} (from {xlsx_file_path.name})")
                    return project_name
                else:
                    logger.warning(f"job_name 값이 없습니다: {xlsx_file_path}")
                    return "unknown"
            else:
                logger.warning(f"job_name 칼럼을 찾을 수 없습니다: {xlsx_file_path}")
                return "unknown"
                
        except Exception as e:
            logger.error(f"프로젝트명 추출 실패 ({file_path}): {e}")
            return "unknown"
    
    def find_all_translation_review_llm_files(self, base_path: str) -> list:
        """
        지정된 경로에서 모든 translation_review_llm.csv 파일을 찾아 반환
        
        Args:
            base_path (str): 검색할 기본 경로
            
        Returns:
            list: translation_review_llm.csv 파일 경로들의 리스트
        """
        csv_files = []
        base_path = Path(base_path)
        
        # glob 패턴을 사용하여 모든 하위 디렉토리에서 translation_review_llm.csv 파일 찾기
        for csv_file in base_path.glob("**/translation_review_llm.csv"):
            if csv_file.is_file():
                csv_files.append(str(csv_file))
        
        # 에피소드 순서대로 정렬 (경로에서 에피소드 번호 추출하여 정렬)
        def get_sort_key(file_path):
            try:
                path = Path(file_path)
                episode_num = int(path.parent.name)
                return episode_num
            except:
                return 999  # 에피소드 번호를 찾을 수 없는 경우 마지막으로
        
        csv_files.sort(key=get_sort_key)
        
        logger.info(f"발견된 translation_review_llm.csv 파일: {len(csv_files)}개")
        for file in csv_files:
            logger.info(f"  - {file}")
        
        return csv_files
    
    def process_single_csv_file(self, csv_file_path: str) -> list:
        """
        단일 translation_review_llm.csv 파일을 처리하여 Google Sheets 업로드용 데이터로 변환
        
        Args:
            csv_file_path (str): 처리할 CSV 파일 경로
            
        Returns:
            list: 업로드용 데이터 리스트
        """
        try:
            # CSV 파일 읽기
            df = pd.read_csv(csv_file_path)
            
            # 필요한 정보 추출
            project_uuid = self.extract_project_uuid(csv_file_path)
            project_name = self.get_project_name_from_xlsx(csv_file_path)
            ep_num = self.extract_episode_number(csv_file_path)
            
            logger.info(f"파일 처리 중: {Path(csv_file_path).name}")
            logger.info(f"  - Project UUID: {project_uuid}")
            logger.info(f"  - Project Name: {project_name}")
            logger.info(f"  - Episode: {ep_num}")
            logger.info(f"  - 데이터 행 수: {len(df)}")
            
            # Google Sheets 업로드용 데이터 변환
            upload_data = []
            
            for _, row in df.iterrows():
                upload_row = {
                    'project_uuid': project_uuid,
                    'project_name': project_name,
                    'ep_num': ep_num,
                    'file_name': row.get('file_name', ''),
                    'text_box_order': row.get('text_box_order', ''),
                    'target': row.get('target', ''),
                    'val': row.get('val', ''),
                    'tag': row.get('tag', ''),
                    'comment': row.get('comment', '')
                }
                upload_data.append(upload_row)
            
            return upload_data
            
        except Exception as e:
            logger.error(f"CSV 파일 처리 실패 ({csv_file_path}): {e}")
            return []
    
    def upload_all_files_to_sheets(self, base_path: str, sheet_name: str = "번역 식사 검수 코멘트 생성 시트") -> bool:
        """
        모든 translation_review_llm.csv 파일을 Google Sheets에 업로드
        
        Args:
            base_path (str): 검색할 기본 경로
            sheet_name (str): 업로드할 시트 이름
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 모든 translation_review_llm.csv 파일 찾기
            csv_files = self.find_all_translation_review_llm_files(base_path)
            
            if not csv_files:
                logger.warning(f"'{base_path}' 경로에서 translation_review_llm.csv 파일을 찾을 수 없습니다.")
                return False
            
            # 모든 데이터를 하나로 합치기
            all_upload_data = []
            
            for csv_file in csv_files:
                file_data = self.process_single_csv_file(csv_file)
                all_upload_data.extend(file_data)
            
            if not all_upload_data:
                logger.warning("업로드할 데이터가 없습니다.")
                return False
            
            logger.info(f"총 {len(all_upload_data)}개의 데이터 행을 업로드합니다.")
            
            # Google Sheets에 업로드
            return self.upload_data_to_sheets(all_upload_data, sheet_name)
            
        except Exception as e:
            logger.error(f"전체 업로드 실패: {e}")
            return False
    
    def upload_data_to_sheets(self, upload_data: list, sheet_name: str) -> bool:
        """
        데이터를 Google Sheets에 업로드
        
        Args:
            upload_data (list): 업로드할 데이터 리스트
            sheet_name (str): 시트 이름
            
        Returns:
            bool: 성공 여부
        """
        try:
            # 스프레드시트 열기
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            # 시트 찾기 또는 생성
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
                logger.info(f"기존 시트 사용: {sheet_name}")
            except:
                # 새 시트 생성 (충분한 행과 열 확보)
                worksheet = spreadsheet.add_worksheet(
                    title=sheet_name, 
                    rows=len(upload_data) + 100,  # 여유 행
                    cols=10  # 9개 칼럼 + 여유
                )
                logger.info(f"새 시트 생성: {sheet_name}")
            
            # 헤더 설정
            headers = ['project_uuid', 'project_name', 'ep_num', 'file_name', 'text_box_order', 'target', 'val', 'tag', 'comment']
            
            # NaN 값을 빈 문자열로 변환하고, 모든 값을 문자열로 변환하는 함수
            def safe_str(value):
                if pd.isna(value) or value is None:
                    return ''
                return str(value)
            
            # 기존 데이터 확인
            existing_data = worksheet.get_all_values()
            
            if not existing_data:
                # 시트가 비어있는 경우: 헤더 + 새 데이터 추가
                print("📋 빈 시트에 헤더와 데이터를 추가합니다.")
                sheet_data = [headers]
                for row_data in upload_data:
                    sheet_row = [
                        safe_str(row_data.get('project_uuid', '')),
                        safe_str(row_data.get('project_name', '')),
                        safe_str(row_data.get('ep_num', '')),
                        safe_str(row_data.get('file_name', '')),
                        safe_str(row_data.get('text_box_order', '')),
                        safe_str(row_data.get('target', '')),
                        safe_str(row_data.get('val', '')),
                        safe_str(row_data.get('tag', '')),
                        safe_str(row_data.get('comment', ''))
                    ]
                    sheet_data.append(sheet_row)
                
                range_name = f"A1:{chr(ord('A') + len(headers) - 1)}{len(sheet_data)}"
                worksheet.update(sheet_data, range_name)
            else:
                # 기존 데이터가 있는 경우: 중복 확인 후 추가
                print(f"📋 기존 데이터 {len(existing_data)-1}개 행 발견. 중복 확인 중...")
                
                # 기존 데이터에서 project_uuid + ep_num + file_name + text_box_order 조합 추출
                existing_combinations = set()
                for row in existing_data[1:]:  # 헤더 제외
                    if len(row) >= 5:
                        combination = f"{row[0]}_{row[2]}_{row[3]}_{row[4]}"  # project_uuid + ep_num + file_name + text_box_order
                        existing_combinations.add(combination)
                
                # 새로 추가할 데이터 필터링
                new_rows = []
                skipped_count = 0
                for row_data in upload_data:
                    project_uuid = safe_str(row_data.get('project_uuid', ''))
                    ep_num = safe_str(row_data.get('ep_num', ''))
                    file_name = safe_str(row_data.get('file_name', ''))
                    text_box_order = safe_str(row_data.get('text_box_order', ''))
                    combination = f"{project_uuid}_{ep_num}_{file_name}_{text_box_order}"
                    
                    if combination not in existing_combinations:
                        new_row = [
                            project_uuid,
                            safe_str(row_data.get('project_name', '')),
                            ep_num,
                            file_name,
                            text_box_order,
                            safe_str(row_data.get('target', '')),
                            safe_str(row_data.get('val', '')),
                            safe_str(row_data.get('tag', '')),
                            safe_str(row_data.get('comment', ''))
                        ]
                        new_rows.append(new_row)
                    else:
                        skipped_count += 1
                
                if new_rows:
                    # 기존 데이터 다음 행부터 추가
                    start_row = len(existing_data) + 1
                    end_row = start_row + len(new_rows) - 1
                    range_name = f"A{start_row}:{chr(ord('A') + len(headers) - 1)}{end_row}"
                    worksheet.update(new_rows, range_name)
                    print(f"📝 {len(new_rows)}개의 새 데이터가 추가되었습니다.")
                    if skipped_count > 0:
                        print(f"⚠️ {skipped_count}개의 중복 데이터가 건너뛰어졌습니다.")
                else:
                    print(f"📋 추가할 새 데이터가 없습니다. ({len(upload_data)}개 모두 중복)")
            
            logger.info(f"✅ 업로드 완료!")
            logger.info(f"  - 시트: {sheet_name}")
            logger.info(f"  - 업로드된 행: {len(upload_data)}행 (헤더 제외)")
            logger.info(f"  - 스프레드시트 URL: https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Google Sheets 업로드 실패: {e}")
            return False


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
        print("❌ 사용법: python3 5_sheets_uploader_for_llm_results.py <project_uuid> <episode_number>")
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
    
    # 설정 (상대경로 사용)
    CREDENTIALS_PATH = "credentials.json"  # 현재 process 디렉토리에 있음
    SPREADSHEET_ID = "1oYi9dxDl3HcPzld3mZlXFXAEK5V0HU22HZLthCqmMgo"  # 사용자 제공 스프레드시트 ID
    SHEET_NAME = "번역 식사 검수 코멘트 생성 시트"
    
    try:
        print("=== Translation Review LLM Results → Google Sheets 업로드 ===")
        print(f"📊 대상 스프레드시트: {SPREADSHEET_ID}")
        print(f"📋 시트 이름: {SHEET_NAME}")
        print(f"📁 검색 경로: {base_path}")
        print()
        
        # 업로더 초기화
        uploader = TranslationReviewSheetsUploader(CREDENTIALS_PATH, SPREADSHEET_ID)
        
        # 해당 에피소드 범위의 translation_review_llm.csv 파일을 Google Sheets에 업로드
        success = uploader.upload_all_files_to_sheets(base_path, SHEET_NAME)
        
        if success:
            print("🎉 모든 파일이 성공적으로 업로드되었습니다!")
            print(f"🔗 확인: https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
        else:
            print("❌ 업로드 중 오류가 발생했습니다.")
            
    except Exception as e:
        print(f"❌ 실행 중 오류 발생: {e}")
        logger.error(f"메인 실행 오류: {e}")


if __name__ == "__main__":
    main()
