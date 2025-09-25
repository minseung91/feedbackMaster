from google import genai
from google.genai import types
import pandas as pd
import json
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import glob
import os
from pathlib import Path
from token_cost_calculator import TokenCostCalculator

# 환경 변수에서 API 키 가져오기
API_KEY = os.getenv('HACKATHON_GEMINI_API_KEY')
if not API_KEY:
    raise ValueError("HACKATHON_GEMINI_API_KEY 환경변수를 설정해주세요. ~/.zshrc에 'export HACKATHON_GEMINI_API_KEY=\"your_api_key\"'를 추가하고 'source ~/.zshrc'를 실행하세요.")

client = genai.Client(api_key=API_KEY)

def find_translation_review_files(base_path):
    """지정된 경로에서 모든 translation_review.csv 파일을 찾아 반환"""
    csv_files = []
    base_path = Path(base_path)
    
    # glob 패턴을 사용하여 모든 하위 디렉토리에서 translation_review.csv 파일 찾기
    pattern = base_path / "**/translation_review.csv"
    
    for csv_file in base_path.glob("**/translation_review.csv"):
        if csv_file.is_file():
            csv_files.append(str(csv_file))
    
    return sorted(csv_files)

def calculate_total_textboxes_from_xlsx(csv_file_path):
    """
    CSV 파일 경로를 기반으로 해당하는 원본 XLSX 파일에서 전체 텍스트박스 수를 계산
    
    Args:
        csv_file_path (str): translation_review.csv 파일 경로
        
    Returns:
        int: 전체 고유 텍스트박스 수
    """
    try:
        # CSV 파일 경로에서 에피소드 번호 추출
        # 예: .../preprocessed/1/translation_review.csv -> ep_1.xlsx
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
            # 고유한 텍스트박스 수 계산 (3_xlsx_comparison.py 방식과 동일)
            unique_textboxes = df.groupby(['file_name', 'text_box_order']).size()
            total_unique_textboxes = len(unique_textboxes)
        else:
            # 칼럼이 없는 경우 전체 행 수 사용
            total_unique_textboxes = len(df)
        
        print(f"📊 {xlsx_file_path.name}에서 전체 텍스트박스 수: {total_unique_textboxes:,}개")
        return total_unique_textboxes
        
    except Exception as e:
        print(f"오류: XLSX 파일에서 텍스트박스 수 계산 실패 ({csv_file_path}): {e}")
        return 0

def process_single_csv_file(csv_file_path, guideline_path=None, model_name="gemini-2.5-pro", max_workers=10):
    """단일 CSV 파일을 처리하여 LLM 분석 결과를 생성"""
    print(f"\n{'='*60}")
    print(f"파일 처리 시작: {csv_file_path}")
    print(f"{'='*60}")
    
    try:
        # CSV 파일 읽기
        test_data = pd.read_csv(csv_file_path)
        
        print(f"데이터 구조 확인:")
        print(f"전체 행 수: {len(test_data)}")
        print(f"칼럼명: {test_data.columns.tolist()}")
        
        # target과 val 칼럼이 존재하는지 확인
        if 'target' not in test_data.columns or 'val' not in test_data.columns:
            print(f"경고: '{csv_file_path}'에서 'target' 또는 'val' 칼럼을 찾을 수 없습니다.")
            print(f"사용 가능한 칼럼: {test_data.columns.tolist()}")
            return None
        
        # 배치 처리를 위한 데이터 구조 설계
        batch_size = 20
        comparison_data = []
        
        # 배치별로 데이터 분할
        for i in range(0, len(test_data), batch_size):
            batch = test_data[i:i+batch_size]
            batch_dict = {
                'batch_id': i // batch_size + 1,
                'start_index': i,
                'end_index': min(i + batch_size, len(test_data)),
                'data': [],
                'source_file': csv_file_path
            }
            
            for idx, row in batch.iterrows():
                batch_dict['data'].append({
                    'index': idx,
                    'target': row['target'],
                    'val': row['val'],
                    'file_name': row.get('file_name', ''),
                    'text_box_order': row.get('text_box_order', '')
                })
            
            comparison_data.append(batch_dict)
        
        print(f"총 {len(comparison_data)}개의 배치로 분할됨 (각 배치당 최대 {batch_size}개 항목)")
        
        # 모든 배치 처리 실행 (병렬 처리)
        all_results = process_all_batches_for_single_file(comparison_data, csv_file_path, guideline_path, model_name, max_workers)
        
        # 결과를 원본 파일과 같은 디렉토리에 저장
        save_results_to_original_location(all_results, comparison_data, csv_file_path)
        
        return {
            'source_file': csv_file_path,
            'total_batches': len(comparison_data),
            'results': all_results,
            'success': True
        }
        
    except Exception as e:
        print(f"파일 '{csv_file_path}' 처리 중 오류 발생: {e}")
        return {
            'source_file': csv_file_path,
            'error': str(e),
            'success': False
        }

# LLM으로 비교 분석하는 함수 (사용자 지정 JSON 형식)
def analyze_batch_differences(batch_data, guideline_path=None, cost_calculator=None):
    """배치 데이터의 target과 val을 비교하여 수정 사유를 분석 (사용자 지정 JSON 입출력)"""
    
    # 가이드라인 파일 읽기
    guideline_content = "가이드라인 파일이 제공되지 않았습니다."
    if guideline_path and os.path.exists(guideline_path):
        try:
            with open(guideline_path, 'r', encoding='utf-8') as f:
                guideline_content = f.read()
            # print(f"📋 가이드라인 파일 로드됨: {guideline_path}")
        except Exception as e:
            print(f"경고: 가이드라인 파일 읽기 실패 ({guideline_path}): {e}")
            guideline_content = "가이드라인 파일 읽기에 실패했습니다."
    elif guideline_path:
        print(f"경고: 가이드라인 파일을 찾을 수 없습니다: {guideline_path}")
    else:
        print("경고: 가이드라인 파일 경로가 제공되지 않았습니다. 가이드라인 없이 진행합니다.")
    
    # 사용자 지정 JSON 입력 형식으로 구성
    json_input = []
    
    for item in batch_data['data']:
        json_input.append({
            "translated_text": item['target'],
            "edited_text": item['val']
        })
    
    # JSON 입력을 문자열로 변환
    json_input_str = json.dumps(json_input, ensure_ascii=False, indent=2)
    
    # 사용자 제공 프롬프트로 LLM에게 분석 요청 (가이드라인 포함)
    prompt = f"""클라이언트 가이드라인:
{guideline_content}

---

다음 JSON 형식의 입력 데이터에 포함된 각 번역 쌍을 분석해주세요:

{json_input_str}


반드시 다음 형식의 JSON 배열로 응답해주세요:

[
  {{
    "translated_text": "입력받은 번역문 그대로",
    "edited_text": "입력받은 검수본 그대로",
    "tag": ["선택된 태그들"],
    "comment": "구체적인 분석 코멘트"
  }}
]

유효한 JSON 배열 형식으로만 응답해주세요."""
    
    # system instruction 파일 읽기
    system_instruction_path = "../data/prompt/comment_generation_prompt.txt"
    system_instruction_content = ""
    
    if os.path.exists(system_instruction_path):
        try:
            with open(system_instruction_path, 'r', encoding='utf-8') as f:
                system_instruction_content = f.read()
            # print(f"📋 System instruction 파일 로드됨: {system_instruction_path}")
        except Exception as e:
            print(f"경고: System instruction 파일 읽기 실패 ({system_instruction_path}): {e}")
            system_instruction_content = "System instruction 파일을 읽을 수 없습니다. 기본 설정으로 진행합니다."
    else:
        print(f"경고: System instruction 파일을 찾을 수 없습니다: {system_instruction_path}")
        system_instruction_content = "System instruction 파일을 찾을 수 없습니다. 기본 설정으로 진행합니다."
    
    response = client.models.generate_content(
        model="gemini-2.5-pro",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction_content),
        contents=prompt
    )
    
    # 토큰 사용량 및 비용 계산
    cost_info = None
    if cost_calculator:
        cost_info = cost_calculator.calculate_batch_cost(response)
        cost_calculator.print_batch_cost(batch_data['batch_id'], cost_info)
    
    # JSON 응답 파싱 시도
    try:
        # 응답에서 JSON 부분만 추출 (```json 태그 제거)
        response_text = response.text.strip()
        if response_text.startswith('```json'):
            response_text = response_text[7:]
        if response_text.endswith('```'):
            response_text = response_text[:-3]
        
        parsed_response = json.loads(response_text.strip())
        
        # 응답이 배열인지 확인
        if not isinstance(parsed_response, list):
            raise ValueError("응답이 JSON 배열 형식이 아닙니다.")
        
        result = {
            'batch_id': batch_data['batch_id'],
            'input_data': json_input,
            'analysis_result': parsed_response,
            'processed_items': len(batch_data['data']),
            'parsing_success': True
        }
        
        # 비용 정보 추가
        if cost_info:
            result['cost_info'] = cost_info
        
        return result
        
    except (json.JSONDecodeError, ValueError) as e:
        print(f"JSON 파싱 오류: {e}")
        print(f"원본 응답: {response.text}")
        
        result = {
            'batch_id': batch_data['batch_id'],
            'input_data': json_input,
            'analysis_result': {
                'error': 'JSON 파싱 실패',
                'raw_response': response.text
            },
            'processed_items': len(batch_data['data']),
            'parsing_success': False
        }
        
        # 비용 정보 추가 (파싱 실패해도 토큰은 사용됨)
        if cost_info:
            result['cost_info'] = cost_info
        
        return result

# JSON 분석 결과 파싱 및 활용을 위한 유틸리티 함수들
def extract_tags_statistics(all_results):
    """모든 분석 결과에서 태그별 통계 추출 (새로운 JSON 형식 대응)"""
    tag_counts = {}
    
    for result in all_results:
        if not result.get('parsing_success', False):
            continue
            
        analysis_results = result.get('analysis_result', [])
        
        # 새로운 형식: 배열의 각 항목에서 태그 추출
        for item in analysis_results:
            # 태그 통계
            for tag in item.get('tag', []):
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    return {
        'tag_counts': tag_counts
    }

def generate_analysis_report(all_results, total_textboxes=None):
    """전체 분석 결과에 대한 상세 리포트 생성 (새로운 JSON 형식 대응)"""
    if not all_results:
        return "분석 결과가 없습니다."
    
    stats = extract_tags_statistics(all_results)
    total_pairs = sum(result.get('processed_items', 0) for result in all_results)
    successful_batches = sum(1 for result in all_results if result.get('parsing_success', False))
    
    report = f"""
=== 번역 품질 분석 리포트 ===

📊 전체 통계:
- 처리된 총 배치 수: {len(all_results)}
- 성공적으로 분석된 배치: {successful_batches}
- 처리된 총 쌍 수: {total_pairs}"""
    
    if total_textboxes is not None:
        report += f"\n- 전체 실질 텍스트박스 수: {total_textboxes:,}개"
    
    report += "\n\n🏷️ 태그별 발생 빈도:"
    
    # 태그별 통계 출력 (빈도순)
    sorted_tags = sorted(stats['tag_counts'].items(), key=lambda x: x[1], reverse=True)
    for tag, count in sorted_tags:
        if total_textboxes is not None and total_textboxes > 0:
            # 전체 텍스트박스 수 기준으로 퍼센트 계산
            percentage = (count / total_textboxes) * 100
            report += f"\n  - {tag}: {count}회 ({percentage:.1f}%)"
        else:
            # 기존 방식: 처리된 총 쌍 수 기준
            percentage = (count / total_pairs) * 100 if total_pairs > 0 else 0
            report += f"\n  - {tag}: {count}회 ({percentage:.1f}%)"
    
    return report

def export_structured_results(all_results, comparison_data, output_dir="analysis_results"):
    """구조화된 분석 결과를 여러 형태로 내보내기"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 1. 전체 JSON 결과 저장
    full_results_path = os.path.join(output_dir, f"full_analysis_{timestamp}.json")
    with open(full_results_path, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    
    # 2. 요약 통계 JSON 저장
    stats = extract_tags_statistics(all_results)
    stats_path = os.path.join(output_dir, f"statistics_{timestamp}.json")
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    # 3. 텍스트 리포트 저장
    report = generate_analysis_report(all_results)
    report_path = os.path.join(output_dir, f"report_{timestamp}.txt")
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    # 4. CSV 형태로 각 쌍별 결과 저장 (사용자 지정 칼럼명)
    csv_data = []
    
    # 배치별로 원본 데이터와 분석 결과를 매칭
    for batch in comparison_data:
        batch_id = batch['batch_id']
        original_items = batch['data']
        
        # 해당 배치의 분석 결과 찾기
        batch_analysis = None
        for result in all_results:
            if result['batch_id'] == batch_id:
                batch_analysis = result
                break
        
        if not batch_analysis:
            # 분석 결과가 없는 경우에도 원본 데이터는 보존
            for original_item in original_items:
                csv_row = {
                    'file_name': original_item.get('file_name', ''),
                    'text_box_order': original_item.get('text_box_order', ''),
                    'target': original_item.get('target', ''),
                    'val': original_item.get('val', ''),
                    'tag': '',
                    'comment': '분석 실패'
                }
                csv_data.append(csv_row)
            continue
        
        analysis_results = batch_analysis.get('analysis_result', []) if batch_analysis.get('parsing_success', False) else []
        
        # 원본 데이터와 분석 결과를 순서대로 매칭
        for i, original_item in enumerate(original_items):
            analysis_item = analysis_results[i] if i < len(analysis_results) else {}
            
            csv_row = {
                'file_name': original_item.get('file_name', ''),
                'text_box_order': original_item.get('text_box_order', ''),
                'target': original_item.get('target', ''),
                'val': original_item.get('val', ''),
                'tag': ', '.join(analysis_item.get('tag', [])) if analysis_item else '',
                'comment': analysis_item.get('comment', '') if analysis_item else '분석 결과 없음'
            }
            csv_data.append(csv_row)
    
    if csv_data:
        import pandas as pd
        df = pd.DataFrame(csv_data)
        csv_path = os.path.join(output_dir, f"pair_analysis_{timestamp}.csv")
        df.to_csv(csv_path, index=False, encoding='utf-8-sig')
        
        print(f"분석 결과가 다음 파일들로 저장되었습니다:")
        print(f"  - 전체 결과: {full_results_path}")
        print(f"  - 통계 요약: {stats_path}")
        print(f"  - 텍스트 리포트: {report_path}")
        print(f"  - CSV 결과: {csv_path}")
    
    return {
        'full_results': full_results_path,
        'statistics': stats_path,
        'report': report_path,
        'csv': csv_path if csv_data else None
    }

# 데이터 저장 및 관리를 위한 추가 유틸리티 함수들
def save_individual_batch_result(batch_result, batch_data, output_dir="batch_results"):
    """개별 배치 결과를 파일로 저장"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_id = batch_result['batch_id']
    filename = f"batch_{batch_id}_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    # 저장할 데이터 구성
    save_data = {
        'batch_info': {
            'batch_id': batch_id,
            'timestamp': timestamp,
            'processed_items': batch_result['processed_items'],
            'parsing_success': batch_result.get('parsing_success', False)
        },
        'input_data': batch_result.get('input_data', []),
        'analysis_result': batch_result.get('analysis_result', []),
        'cost_info': batch_result.get('cost_info', {}),
        'original_batch_data': {
            'start_index': batch_data['start_index'],
            'end_index': batch_data['end_index'],
            'data_preview': [
                {
                    'index': item['index'],
                    'file_name': item.get('file_name', ''),
                    'text_box_order': item.get('text_box_order', ''),
                    'target': item['target'][:100] + '...' if len(item['target']) > 100 else item['target'],
                    'val': item['val'][:100] + '...' if len(item['val']) > 100 else item['val']
                }
                for item in batch_data['data'][:3]  # 처음 3개만 미리보기
            ]
        }
    }
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"📁 배치 {batch_id} 결과 저장: {filename}")
    return filepath

def save_cost_summary_to_file(cost_calculator, all_results, output_dir="analysis_results"):
    """토큰 비용 요약을 txt 파일로 저장"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"token_cost_summary_{timestamp}.txt"
    filepath = os.path.join(output_dir, filename)
    
    # 전체 비용 요약 정보 가져오기
    summary = cost_calculator.get_total_cost_summary()
    
    # 배치별 비용 정보 수집
    batch_costs = []
    for result in all_results:
        if 'cost_info' in result:
            batch_costs.append({
                'batch_id': result['batch_id'],
                'cost_info': result['cost_info'],
                'parsing_success': result.get('parsing_success', False)
            })
    
    # txt 파일 내용 생성
    content = f"""토큰 사용량 및 비용 분석 리포트
생성 시간: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M:%S')}
{'='*60}

📊 전체 요약
{'='*60}
총 배치 수: {len(all_results)}
성공한 배치: {sum(1 for r in all_results if r.get('parsing_success', False))}
실패한 배치: {sum(1 for r in all_results if not r.get('parsing_success', False))}

💰 전체 토큰 사용량 및 비용 [{summary.get('model_name', 'Unknown')} - {summary.get('pricing_tier', 'Unknown')}]
{'='*60}
📥 총 입력 토큰: {summary['total_input_tokens']:,} 토큰
📤 총 출력 토큰: {summary['total_output_tokens']:,} 토큰
🤔 총 사고 토큰: {summary['total_thinking_tokens']:,} 토큰
💾 총 캐시 토큰: {summary.get('total_cached_tokens', 0):,} 토큰
📊 총 토큰 수: {summary['total_tokens']:,} 토큰

💵 비용 세부 내역:
   - 입력 토큰 비용: ${summary['total_input_cost']:.6f}
   - 출력 토큰 비용: ${summary['total_output_cost']:.6f}
   - 사고 토큰 비용: ${summary['total_thinking_cost']:.6f}
   - 캐시 토큰 비용: ${summary.get('total_cached_cost', 0):.6f}
   - 총 비용: ${summary['total_cost']:.6f}
   - 총 비용 (원화): ₩{summary['total_cost'] * 1400:.0f} (환율 1,400원 기준)

📈 배치별 상세 비용
{'='*60}
"""
    
    # 배치별 비용 정보 추가
    for batch_cost in batch_costs:
        cost_info = batch_cost['cost_info']
        status = "✅ 성공" if batch_cost['parsing_success'] else "❌ 실패"
        estimated_text = " (추정)" if cost_info.get('estimated', False) else ""
        
        tier_info = f" [{cost_info.get('pricing_tier', 'Unknown')}]"
        content += f"""
배치 {batch_cost['batch_id']} - {status}{estimated_text}{tier_info}
   📥 입력: {cost_info.get('input_tokens', 0):,} 토큰 (${cost_info.get('input_cost', 0):.6f})
   📤 출력: {cost_info.get('output_tokens', 0):,} 토큰 (${cost_info.get('output_cost', 0):.6f})"""
        
        if cost_info.get('thinking_tokens', 0) > 0:
            content += f"\n   🤔 사고: {cost_info.get('thinking_tokens', 0):,} 토큰 (${cost_info.get('thinking_cost', 0):.6f})"
        
        if cost_info.get('cached_tokens', 0) > 0:
            content += f"\n   💾 캐시: {cost_info.get('cached_tokens', 0):,} 토큰 (${cost_info.get('cached_cost', 0):.6f})"
        
        content += f"\n   💵 배치 비용: ${cost_info.get('batch_cost', 0):.6f} (₩{cost_info.get('batch_cost', 0) * 1400:.2f})\n"
    
    # 가격 정보 추가 (모델별 동적 표시)
    model_name = summary.get('model_name', 'Unknown')
    content += f"""
{'='*60}
📋 가격 정보 ({model_name})
{'='*60}"""
    
    if model_name == "gemini-2.5-flash":
        content += f"""
입력 토큰: $0.30 / 1M 토큰
출력 토큰: $2.50 / 1M 토큰  
사고 토큰: $2.50 / 1M 토큰
캐시 토큰: $0.075 / 1M 토큰"""
    elif model_name == "gemini-2.5-pro":
        content += f"""
입력 토큰 (20만 미만): $1.25 / 1M 토큰
입력 토큰 (20만 이상): $2.50 / 1M 토큰
출력 토큰 (20만 미만): $10.0 / 1M 토큰
출력 토큰 (20만 이상): $15.0 / 1M 토큰
사고 토큰: $10.0 / 1M 토큰
캐시 토큰 (20만 미만): $0.31 / 1M 토큰
캐시 토큰 (20만 이상): $0.625 / 1M 토큰
임계값: 200,000 토큰"""
    
    
    content += "\n"
    
    # 파일에 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"💰 토큰 비용 요약 저장: {filename}")
    return filepath

def save_batch_results(results, output_dir="analysis_results"):
    """배치 분석 결과를 JSON 파일로 저장"""
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"batch_analysis_{timestamp}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=4)
    
    print(f"분석 결과가 저장되었습니다: {filepath}")
    return filepath

def process_batch_with_cost_tracking(batch, guideline_path, cost_calculator, save_individual_batches=True):
    """단일 배치를 처리하고 비용을 추적하는 래퍼 함수"""
    try:
        result = analyze_batch_differences(batch, guideline_path, cost_calculator)
        
        # 파싱 성공 여부 표시
        status = "✅ 성공" if result.get('parsing_success', False) else "❌ JSON 파싱 실패"
        print(f"배치 {batch['batch_id']} 처리 완료 - {status}")
        
        # 개별 배치 결과 저장
        if save_individual_batches:
            save_individual_batch_result(result, batch)
        
        return result
        
    except Exception as e:
        print(f"배치 {batch['batch_id']} 처리 중 오류 발생: {e}")
        return None

def process_all_batches_for_single_file(comparison_data, source_file_path, guideline_path=None, model_name="gemini-2.5-pro", max_workers=10):
    """단일 파일의 모든 배치를 병렬로 처리"""
    all_results = []
    cost_calculator = TokenCostCalculator(model_name=model_name)
    
    # 스레드 안전성을 위한 락
    cost_lock = threading.Lock()
    
    print(f"총 {len(comparison_data)}개 배치를 {max_workers}개 워커로 병렬 처리 시작...")
    
    # ThreadPoolExecutor를 사용한 병렬 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 각 배치에 대해 작업 제출 (개별 배치 저장 비활성화)
        future_to_batch = {
            executor.submit(process_batch_with_cost_tracking, batch, guideline_path, cost_calculator, False): batch 
            for batch in comparison_data
        }
        
        # 완료된 작업들을 수집
        completed_count = 0
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            completed_count += 1
            
            try:
                result = future.result()
                if result is not None:
                    with cost_lock:  # 스레드 안전성을 위한 락
                        all_results.append(result)
                
                print(f"진행률: {completed_count}/{len(comparison_data)} 배치 완료")
                
            except Exception as e:
                print(f"배치 {batch['batch_id']} 결과 수집 중 오류: {e}")
    
    # 배치 ID 순서대로 정렬
    all_results.sort(key=lambda x: x.get('batch_id', 0))
    
    print(f"파일 '{Path(source_file_path).name}' 병렬 처리 완료! 총 {len(all_results)}개 배치 처리됨")
    
    # 전체 비용 요약 출력
    cost_calculator.print_total_cost_summary()
    
    return all_results

def process_all_batches(comparison_data, save_results=True, use_structured_export=True, save_individual_batches=True, model_name="gemini-2.5-pro", max_workers=10):
    """모든 배치를 병렬로 처리하고 결과를 저장 (기존 함수 유지)"""
    all_results = []
    cost_calculator = TokenCostCalculator(model_name=model_name)
    
    # 스레드 안전성을 위한 락
    cost_lock = threading.Lock()
    
    print(f"\n총 {len(comparison_data)}개 배치를 {max_workers}개 워커로 병렬 처리 시작...")
    
    # ThreadPoolExecutor를 사용한 병렬 처리
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 각 배치에 대해 작업 제출
        future_to_batch = {
            executor.submit(process_batch_with_cost_tracking, batch, cost_calculator, save_individual_batches): batch 
            for batch in comparison_data
        }
        
        # 완료된 작업들을 수집
        completed_count = 0
        for future in as_completed(future_to_batch):
            batch = future_to_batch[future]
            completed_count += 1
            
            try:
                result = future.result()
                if result is not None:
                    with cost_lock:  # 스레드 안전성을 위한 락
                        all_results.append(result)
                
                print(f"진행률: {completed_count}/{len(comparison_data)} 배치 완료")
                
            except Exception as e:
                print(f"배치 {batch['batch_id']} 결과 수집 중 오류: {e}")
    
    # 배치 ID 순서대로 정렬
    all_results.sort(key=lambda x: x.get('batch_id', 0))
    
    print(f"\n병렬 처리 완료! 총 {len(all_results)}개 배치 처리됨")
    
    # 전체 비용 요약 출력
    cost_calculator.print_total_cost_summary()
    
    # 토큰 비용 정보를 txt 파일로 저장
    if save_results:
        save_cost_summary_to_file(cost_calculator, all_results)
    
    if save_results and all_results:
        if use_structured_export:
            # 새로운 구조화된 내보내기 사용 (comparison_data 전달)
            export_structured_results(all_results, comparison_data)
            
            # 요약 리포트 출력
            print(generate_analysis_report(all_results))
        else:
            # 기존 방식으로 저장
            save_batch_results(all_results)
    
    return all_results

def save_results_to_original_location(all_results, comparison_data, source_file_path):
    """분석 결과를 원본 파일과 같은 디렉토리에 translation_review_llm.csv로 저장"""
    if not all_results:
        print(f"저장할 결과가 없습니다: {source_file_path}")
        return None
    
    # 원본 파일의 디렉토리 경로
    source_dir = Path(source_file_path).parent
    output_csv_path = source_dir / "translation_review_llm.csv"
    
    # CSV 형태로 각 쌍별 결과 저장
    csv_data = []
    
    # 배치별로 원본 데이터와 분석 결과를 매칭
    for batch in comparison_data:
        batch_id = batch['batch_id']
        original_items = batch['data']
        
        # 해당 배치의 분석 결과 찾기
        batch_analysis = None
        for result in all_results:
            if result['batch_id'] == batch_id:
                batch_analysis = result
                break
        
        if not batch_analysis:
            # 분석 결과가 없는 경우에도 원본 데이터는 보존
            for original_item in original_items:
                csv_row = {
                    'file_name': original_item.get('file_name', ''),
                    'text_box_order': original_item.get('text_box_order', ''),
                    'target': original_item.get('target', ''),
                    'val': original_item.get('val', ''),
                    'tag': '',
                    'comment': '분석 실패'
                }
                csv_data.append(csv_row)
            continue
        
        analysis_results = batch_analysis.get('analysis_result', []) if batch_analysis.get('parsing_success', False) else []
        
        # 원본 데이터와 분석 결과를 순서대로 매칭
        for i, original_item in enumerate(original_items):
            analysis_item = analysis_results[i] if i < len(analysis_results) else {}
            
            csv_row = {
                'file_name': original_item.get('file_name', ''),
                'text_box_order': original_item.get('text_box_order', ''),
                'target': original_item.get('target', ''),
                'val': original_item.get('val', ''),
                'tag': ', '.join(analysis_item.get('tag', [])) if analysis_item else '',
                'comment': analysis_item.get('comment', '') if analysis_item else '분석 결과 없음'
            }
            csv_data.append(csv_row)
    
    if csv_data:
        # CSV 파일 저장
        df = pd.DataFrame(csv_data)
        df.to_csv(output_csv_path, index=False, encoding='utf-8-sig')
        
        print(f"✅ 분석 결과 저장 완료:")
        print(f"   - CSV: {output_csv_path}")
        print(f"   - 총 {len(csv_data)}개 항목 저장")
        
        return {
            'csv_path': str(output_csv_path)
        }
    
    return None

def process_multiple_csv_files(base_path, guideline_path=None, model_name="gemini-2.5-pro", max_workers=10):
    """여러 translation_review.csv 파일을 병렬로 처리"""
    print(f"\n{'='*80}")
    print(f"다중 파일 처리 시작")
    print(f"기본 경로: {base_path}")
    if guideline_path:
        print(f"가이드라인 파일: {guideline_path}")
    print(f"{'='*80}")
    
    # 모든 translation_review.csv 파일 찾기
    csv_files = find_translation_review_files(base_path)
    
    if not csv_files:
        print(f"'{base_path}' 경로에서 translation_review.csv 파일을 찾을 수 없습니다.")
        return []
    
    print(f"발견된 파일 목록:")
    for i, csv_file in enumerate(csv_files, 1):
        print(f"  {i}. {csv_file}")
    
    # 각 파일을 병렬로 처리
    all_file_results = []
    
    print(f"\n총 {len(csv_files)}개 파일을 병렬로 처리합니다...")
    
    with ThreadPoolExecutor(max_workers=min(len(csv_files), max_workers)) as executor:
        # 각 파일에 대해 작업 제출
        future_to_file = {
            executor.submit(process_single_csv_file, csv_file, guideline_path, model_name, max_workers): csv_file 
            for csv_file in csv_files
        }
        
        # 완료된 작업들을 수집
        completed_count = 0
        for future in as_completed(future_to_file):
            csv_file = future_to_file[future]
            completed_count += 1
            
            try:
                result = future.result()
                if result is not None:
                    all_file_results.append(result)
                
                print(f"\n파일 처리 진행률: {completed_count}/{len(csv_files)} 완료")
                
            except Exception as e:
                print(f"파일 '{csv_file}' 처리 중 오류: {e}")
                all_file_results.append({
                    'source_file': csv_file,
                    'error': str(e),
                    'success': False
                })
    
    # 전체 결과 요약
    print(f"\n{'='*80}")
    print(f"다중 파일 처리 완료!")
    print(f"{'='*80}")
    
    successful_files = [r for r in all_file_results if r.get('success', False)]
    failed_files = [r for r in all_file_results if not r.get('success', False)]
    
    print(f"성공한 파일: {len(successful_files)}개")
    print(f"실패한 파일: {len(failed_files)}개")
    
    if successful_files:
        print(f"\n성공한 파일들:")
        for result in successful_files:
            file_name = Path(result['source_file']).name
            print(f"  ✅ {file_name} - {result['total_batches']}개 배치 처리됨")
    
    if failed_files:
        print(f"\n실패한 파일들:")
        for result in failed_files:
            file_name = Path(result['source_file']).name
            print(f"  ❌ {file_name} - 오류: {result.get('error', '알 수 없는 오류')}")
    
    return all_file_results

def get_summary_statistics(all_results):
    """전체 분석 결과에 대한 요약 통계"""
    if not all_results:
        return "분석 결과가 없습니다."
    
    total_batches = len(all_results)
    total_items = sum(result['processed_items'] for result in all_results)
    
    summary = f"""
=== 분석 요약 통계 ===
- 처리된 총 배치 수: {total_batches}
- 처리된 총 항목 수: {total_items}
- 배치당 평균 항목 수: {total_items/total_batches:.1f}
"""
    return summary

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
    if len(sys.argv) != 4:
        print("❌ 사용법: python3 4_comment_generator.py <project_uuid> <episode_number> <guideline_path>")
        print("   guideline_path가 빈 값이면 'none'으로 입력하세요")
        return
    
    project_uuid = sys.argv[1]
    episode_number = sys.argv[2]
    guideline_path = sys.argv[3] if sys.argv[3] != 'none' and sys.argv[3] != '' else None
    
    print(f"🔍 프로젝트 UUID: {project_uuid}")
    print(f"🔍 에피소드 번호: {episode_number}")
    print(f"📋 가이드라인 파일: {guideline_path if guideline_path else '없음'}")
    
    # preprocessed 디렉토리 자동 검색
    base_path = find_preprocessed_directory(project_uuid, episode_number)
    if not base_path:
        return
    
    print(f"📁 기본 경로: {base_path}")
    
    print("\n" + "="*50)
    print("다중 파일 병렬 처리 시스템:")
    print("="*50)

    # 다중 파일 처리 실행
    all_file_results = process_multiple_csv_files(
        base_path=base_path,
        guideline_path=guideline_path,
        model_name="gemini-2.5-pro",
        max_workers=5  # 파일 수준 병렬성 (각 파일 내에서도 배치 병렬 처리됨)
    )
    
    # 전체 처리 결과 요약
    if all_file_results:
        print(f"\n{'='*80}")
        print(f"전체 처리 완료 요약")
        print(f"{'='*80}")
        
        successful_files = [r for r in all_file_results if r.get('success', False)]
        total_batches = sum(r.get('total_batches', 0) for r in successful_files)
        
        print(f"✅ 처리 완료된 파일: {len(successful_files)}개")
        print(f"📊 총 처리된 배치: {total_batches}개")
        
        # 각 파일별 결과 저장 위치 표시
        print(f"\n📁 결과 파일 저장 위치:")
        for result in successful_files:
            source_path = Path(result['source_file'])
            csv_path = source_path.parent / "translation_review_llm.csv"
            print(f"  - {source_path.name} → {csv_path}")
        
        print(f"\n🎉 모든 파일 처리가 완료되었습니다!")
        print(f"각 원본 파일과 같은 디렉토리에 'translation_review_llm.csv' 파일이 생성되었습니다.")

if __name__ == "__main__":
    main()