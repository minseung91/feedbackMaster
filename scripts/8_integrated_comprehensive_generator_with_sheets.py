#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
7단계에서 생성된 comprehensive_report.txt 파일을 Google Sheets에 업로드
(중복 생성 방지: 7단계 결과물을 재사용)
"""

import sys
import os
import datetime
from pathlib import Path

# 현재 디렉토리와 상위 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.append(str(current_dir))
sys.path.append(str(parent_dir))

# 기존 모듈들 임포트
import importlib.util
import types

# 7_comprehensive_report_generator.py를 동적으로 import
spec = importlib.util.spec_from_file_location("comprehensive_report_generator", current_dir / "7_comprehensive_report_generator.py")
comprehensive_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comprehensive_module)
ComprehensiveReportGenerator = comprehensive_module.ComprehensiveReportGenerator

import logging
import gspread
from google.oauth2.service_account import Credentials

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class SimpleComprehensiveFeedbackUploader:
    """간단한 종합 피드백 업로더"""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str):
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
    
    def upload_single_report(self, report_file_path: str, sheet_name: str = "종합 검수 피드백") -> bool:
        """단일 리포트 파일을 업로드"""
        try:
            # 파일 읽기
            with open(report_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 프로젝트 정보 추출
            import re
            from pathlib import Path
            
            uuid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
            uuid_match = re.search(uuid_pattern, report_file_path, re.IGNORECASE)
            project_uuid = uuid_match.group(1) if uuid_match else "unknown"
            
            episode_pattern = r'/(\d+-\d+)/'
            episode_match = re.search(episode_pattern, report_file_path)
            episode_range = episode_match.group(1) if episode_match else "unknown"
            
            # 스프레드시트 열기
            spreadsheet = self.client.open_by_key(self.spreadsheet_id)
            
            try:
                worksheet = spreadsheet.worksheet(sheet_name)
            except:
                worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=10)
            
            # 기존 데이터 확인
            existing_data = worksheet.get_all_values()
            
            if not existing_data:
                # 헤더 추가
                headers = ['project_uuid', 'episode_range', 'report_content', 'created_at']
                worksheet.update([headers], 'A1:D1')
                row_to_update = 2
            else:
                row_to_update = len(existing_data) + 1
            
            # 새 데이터 추가
            new_row = [
                project_uuid,
                episode_range, 
                content,
                str(datetime.now())
            ]
            
            range_name = f"A{row_to_update}:D{row_to_update}"
            worksheet.update([new_row], range_name)
            
            print(f"📝 {1}개의 새 데이터가 추가되었습니다.")
            return True
            
        except Exception as e:
            logger.error(f"업로드 실패: {e}")
            return False


class IntegratedComprehensiveGeneratorWithSheets:
    """종합 피드백 생성 + Google Sheets 업로드 통합 클래스"""
    
    def __init__(self, credentials_path: str, spreadsheet_id: str):
        """
        초기화
        
        Args:
            credentials_path (str): Google API credentials.json 파일 경로
            spreadsheet_id (str): 대상 Google Spreadsheet ID
        """
        self.credentials_path = credentials_path
        self.spreadsheet_id = spreadsheet_id
        self.sheets_uploader = SimpleComprehensiveFeedbackUploader(credentials_path, spreadsheet_id)
    
    def generate_and_upload(self, 
                          base_path: str, 
                          previous_feedback_path: str = None,
                          sheet_name: str = "종합 검수 피드백",
                          auto_upload: bool = True) -> dict:
        """
        종합 피드백 생성 + Google Sheets 업로드를 통합 실행
        
        Args:
            base_path (str): 처리할 기본 경로 (preprocessed 디렉토리)
            previous_feedback_path (str): 기존 피드백 파일 경로 (선택사항)
            sheet_name (str): 업로드할 시트 이름
            auto_upload (bool): 자동 업로드 여부
            
        Returns:
            dict: 실행 결과
        """
        try:
            print("=" * 80)
            print("🚀 통합 종합 피드백 생성 + Google Sheets 업로드")
            print("=" * 80)
            print(f"📁 처리 경로: {base_path}")
            print(f"📄 기존 피드백: {previous_feedback_path if previous_feedback_path else '없음'}")
            print(f"📊 스프레드시트: {self.spreadsheet_id}")
            print(f"📋 시트 이름: {sheet_name}")
            print(f"🔄 자동 업로드: {'활성화' if auto_upload else '비활성화'}")
            print()
            
            # 1단계: 종합 피드백 생성 (8_comprehensive_report_generator.py 실행)
            print("1️⃣ 종합 피드백 생성 시작...")
            print("-" * 60)
            
            # ComprehensiveReportGenerator 인스턴스 생성
            generator = ComprehensiveReportGenerator(base_path, previous_feedback_path)
            
            if generator.has_previous_feedback:
                print(f"📄 기존 피드백 파일을 사용합니다: {previous_feedback_path}")
            else:
                print("🆕 새로운 피드백을 생성합니다.")
            
            # 종합 리포트 생성
            output_path = generator.generate_comprehensive_report()
            
            if not output_path or not Path(output_path).exists():
                logger.error("종합 피드백 생성 실패: 파일이 생성되지 않았습니다.")
                return {
                    'success': False,
                    'error': '종합 피드백 생성 실패',
                    'report_generation': False,
                    'sheets_upload': False
                }
            
            print("\n" + "=" * 60)
            print("✅ 종합 피드백 생성 완료!")
            print(f"📄 생성된 파일: {output_path}")
            print("=" * 60)
            
            # 2단계: Google Sheets 업로드 (선택사항)
            sheets_success = False
            
            if auto_upload:
                print(f"\n2️⃣ Google Sheets 업로드 시작...")
                print("-" * 60)
                
                sheets_success = self.sheets_uploader.upload_single_report(
                    report_file_path=output_path,
                    sheet_name=sheet_name
                )
                
                if sheets_success:
                    print("\n" + "=" * 60)
                    print("✅ Google Sheets 업로드 완료!")
                    print(f"🔗 확인: https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}")
                    print("=" * 60)
                else:
                    print("\n" + "=" * 60)
                    print("❌ Google Sheets 업로드 실패")
                    print("=" * 60)
            else:
                print(f"\n2️⃣ Google Sheets 업로드 건너뜀 (auto_upload=False)")
                print("   수동 업로드를 원하시면 다음 명령어를 실행하세요:")
                print(f"   python3 comprehensive_feedback_uploader.py")
            
            # 결과 요약
            result = {
                'success': True,
                'report_generation': True,
                'sheets_upload': sheets_success,
                'output_path': output_path
            }
            
            print(f"\n🎉 전체 프로세스 완료!")
            print(f"   - 피드백 생성: {'✅ 성공' if result['report_generation'] else '❌ 실패'}")
            print(f"   - Sheets 업로드: {'✅ 성공' if result['sheets_upload'] else '❌ 실패' if auto_upload else '⏭️ 건너뜀'}")
            print(f"   - 생성된 파일: {output_path}")
            
            return result
            
        except Exception as e:
            logger.error(f"통합 실행 중 오류 발생: {e}")
            return {
                'success': False,
                'error': str(e),
                'report_generation': False,
                'sheets_upload': False
            }
    
    def upload_existing_report(self, report_file_path: str, sheet_name: str = "종합 검수 피드백") -> dict:
        """
        이미 생성된 단일 comprehensive_report.txt 파일을 Google Sheets에 업로드
        
        Args:
            report_file_path (str): 업로드할 리포트 파일 경로
            sheet_name (str): 업로드할 시트 이름
            
        Returns:
            dict: 실행 결과
        """
        try:
            print("=" * 80)
            print("📤 기존 comprehensive_report.txt 파일 Google Sheets 업로드")
            print("=" * 80)
            print(f"📄 업로드할 파일: {report_file_path}")
            print(f"📊 스프레드시트: {self.spreadsheet_id}")
            print(f"📋 시트 이름: {sheet_name}")
            print()
            
            # Google Sheets에 업로드
            sheets_success = self.sheets_uploader.upload_single_report(
                report_file_path=report_file_path,
                sheet_name=sheet_name
            )
            
            if sheets_success:
                print("\n" + "=" * 60)
                print("✅ Google Sheets 업로드 완료!")
                print(f"🔗 확인: https://docs.google.com/spreadsheets/d/{self.spreadsheet_id}")
                print("=" * 60)
                
                return {
                    'success': True,
                    'sheets_upload': True,
                    'report_file': report_file_path
                }
            else:
                print("\n" + "=" * 60)
                print("❌ Google Sheets 업로드 실패")
                print("=" * 60)
                
                return {
                    'success': False,
                    'sheets_upload': False,
                    'error': 'Google Sheets 업로드 실패'
                }
                
        except Exception as e:
            logger.error(f"업로드 중 오류 발생: {e}")
            return {
                'success': False,
                'sheets_upload': False,
                'error': str(e)
            }

    def upload_existing_reports(self, base_path: str, sheet_name: str = "종합 검수 피드백") -> bool:
        """
        이미 생성된 comprehensive_report.txt 파일들을 Google Sheets에 업로드
        
        Args:
            base_path (str): 검색할 기본 경로
            sheet_name (str): 업로드할 시트 이름
            
        Returns:
            bool: 성공 여부
        """
        print("=" * 80)
        print("📤 기존 comprehensive_report.txt 파일들 Google Sheets 업로드")
        print("=" * 80)
        
        return self.sheets_uploader.upload_all_reports_to_sheets(base_path, sheet_name)


def find_preprocessed_directory(project_uuid, episode_number):
    """project_uuid와 episode_number를 기반으로 preprocessed 디렉토리 경로 찾기"""
    import os
    
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
        print("❌ 사용법: python3 8_integrated_comprehensive_generator_with_sheets.py <project_uuid> <episode_number>")
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
    CREDENTIALS_PATH = "credentials.json"
    SPREADSHEET_ID = "1oYi9dxDl3HcPzld3mZlXFXAEK5V0HU22HZLthCqmMgo"
    
    try:
        # 통합 처리기 초기화
        processor = IntegratedComprehensiveGeneratorWithSheets(CREDENTIALS_PATH, SPREADSHEET_ID)
        
        print("=" * 80)
        print("🎯 통합 종합 리포트 생성 + Google Sheets 업로드")
        print("=" * 80)
        
        # 자동으로 종합 피드백 생성 + Google Sheets 업로드 실행
        print(f"\n🚀 전체 프로세스 실행...")
        print(f"📁 처리 경로: {base_path}")
        
        # 7단계에서 생성된 comprehensive_report.txt 파일 경로
        report_file_path = os.path.join(base_path, "comprehensive_report.txt")
        
        if not os.path.exists(report_file_path):
            print(f"❌ 7단계에서 생성된 리포트 파일을 찾을 수 없습니다: {report_file_path}")
            print("먼저 7단계(7_comprehensive_report_generator.py)를 실행해주세요.")
            return
        
        print(f"📄 기존 리포트 파일 발견: {report_file_path}")
        
        # Google Sheets에 업로드만 실행
        result = processor.upload_existing_report(report_file_path)
        
        if not result['success']:
            print(f"❌ 업로드 실패: {base_path}")
            return
        
        print(f"\n🎉 Google Sheets 업로드가 완료되었습니다!")
        print(f"   - 업로드된 파일: {result['report_file']}")
        print(f"   - 업로드 결과: {'✅ 성공' if result['sheets_upload'] else '❌ 실패'}")
        
    except KeyboardInterrupt:
        print(f"\n⏹️ 사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"\n❌ 실행 중 오류 발생: {e}")
        logger.error(f"메인 실행 오류: {e}")


if __name__ == "__main__":
    main()
