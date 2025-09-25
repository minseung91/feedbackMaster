#!/bin/bash

# Process 파이프라인 실행 스크립트
# 순서대로 Python 파일들을 실행합니다.

set -e  # 에러 발생 시 스크립트 중단

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 현재 디렉토리를 process 폴더로 변경
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}🚀 Process Pipeline 시작${NC}"
echo -e "${BLUE}================================${NC}"

# 1. 프로젝트 변수 설정 (CLI 인자/환경변수/기본값 순)
echo -e "\n${YELLOW}📋 1단계: 프로젝트 옵션 설정 (인자/환경변수 지원)${NC}"

print_usage() {
  cat <<'USAGE'
사용법: run_pipeline.sh -u <PROJECT_URL> -e <EPISODE_RANGE> [-g <GUIDE_PATH>] [-s y|n] [-t <SLACK_TEMPLATE>] [-p <PROJECT_UUID>]
예시: ./run_pipeline.sh -u "https://...id=60af877a-4d7e-465a-875d-37c6f324917e" -e "4-6" -g "/path/guide.md" -s y
USAGE
}

# # (기존 동작과 동일하게 보이도록) 기본값
# DEFAULT_PROJECT_URL="https://admin.totus.pro/en/workProgressManagementDetail/?id=60af877a-4d7e-465a-875d-37c6f324917e"
# DEFAULT_EPISODE_NUMBER="1-3"
# DEFAULT_GUIDE_PATH="/Users/p-152/Desktop/Project/Ongoing/aws-agent-practice/data/client_guideline/ONO_guidline.md"
# DEFAULT_SLACK_SEND="y"
# DEFAULT_SLACK_TEMPLATE=""

# 환경변수 → 기본값 순
# API 키 환경변수 불러오기
if [ -z "$HACKATHON_GEMINI_API_KEY" ]; then
    # ~/.zshrc에서 환경변수 불러오기
    source ~/.zshrc 2>/dev/null || true
fi

# API 키가 여전히 없으면 경고
if [ -z "$HACKATHON_GEMINI_API_KEY" ]; then
    echo -e "${RED}⚠️  경고: HACKATHON_GEMINI_API_KEY 환경변수가 설정되지 않았습니다.${NC}"
    echo -e "${RED}   ~/.zshrc에 'export HACKATHON_GEMINI_API_KEY=\"your_api_key\"'를 추가하고${NC}"
    echo -e "${RED}   'source ~/.zshrc'를 실행해주세요.${NC}"
fi

# 환경변수를 export하여 하위 프로세스에서도 사용 가능하도록 설정
export HACKATHON_GEMINI_API_KEY
PROJECT_URL="${PROJECT_URL:-$DEFAULT_PROJECT_URL}"
EPISODE_NUMBER="${EPISODE_NUMBER:-$DEFAULT_EPISODE_NUMBER}"
GUIDE_PATH="${GUIDE_PATH:-$DEFAULT_GUIDE_PATH}"
SLACK_SEND="${SLACK_SEND:-$DEFAULT_SLACK_SEND}"
SLACK_TEMPLATE="${SLACK_TEMPLATE:-$DEFAULT_SLACK_TEMPLATE}"
PROJECT_UUID="${PROJECT_UUID:-}"

# CLI 인자 파싱
while getopts ":u:e:g:s:t:p:h" opt; do
  case "$opt" in
    u) PROJECT_URL="$OPTARG" ;;
    e) EPISODE_NUMBER="$OPTARG" ;;
    g) GUIDE_PATH="$OPTARG" ;;
    s) SLACK_SEND="$OPTARG" ;;
    t) SLACK_TEMPLATE="$OPTARG" ;;
    p) PROJECT_UUID="$OPTARG" ;;
    h) print_usage; exit 0 ;;
    \?) echo -e "${RED}알 수 없는 옵션: -$OPTARG${NC}"; print_usage; exit 2 ;;
    :)  echo -e "${RED}옵션 -$OPTARG 에 값이 필요합니다.${NC}"; print_usage; exit 2 ;;
  esac
done
shift $((OPTIND - 1))

# PROJECT_UUID 자동 추출(없으면 URL에서 id=UUID 패턴 탐지)
if [[ -z "$PROJECT_UUID" ]]; then
  if [[ "$PROJECT_URL" =~ id=([0-9a-fA-F-]{36}) ]]; then
    PROJECT_UUID="${BASH_REMATCH[1]}"
  else
    echo -e "${YELLOW}경고: URL에서 PROJECT_UUID를 찾지 못했습니다. -p 로 직접 제공하세요.${NC}"
  fi
fi

# GUIDE_PATH 존재 체크(없으면 경고만)
if [[ -n "$GUIDE_PATH" && ! -f "$GUIDE_PATH" ]]; then
  echo -e "${YELLOW}경고: GUIDE_PATH 파일이 존재하지 않습니다: $GUIDE_PATH${NC}"
fi

echo -e "\n${BLUE}🔧 설정된 변수들:${NC}"
echo -e "${BLUE}  PROJECT_URL: ${PROJECT_URL}${NC}"
echo -e "${BLUE}  PROJECT_UUID: ${PROJECT_UUID:-'(미설정)'}${NC}"
echo -e "${BLUE}  EPISODE_NUMBER: ${EPISODE_NUMBER}${NC}"
echo -e "${BLUE}  GUIDE_PATH: ${GUIDE_PATH:-'(없음)'}${NC}"
echo -e "${BLUE}  SLACK_SEND: ${SLACK_SEND}${NC}"
echo -e "${BLUE}  SLACK_TEMPLATE: ${SLACK_TEMPLATE:-'(없음)'}${NC}"

echo -e "${GREEN}✅ 1단계 완료${NC}"

# 2. XLSX 분할 실행
echo -e "\n${YELLOW}📊 2단계: XLSX 파일 분할${NC}"
echo -e "${YELLOW}파일: 2_xlsx_splitter_by_job_index.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER${NC}"

python3 2_xlsx_splitter_by_job_index.py "$PROJECT_UUID" "$EPISODE_NUMBER"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 2단계 완료${NC}"
else
    echo -e "${RED}❌ 2단계 실패${NC}"
    exit 1
fi

# 3. XLSX 비교 실행
echo -e "\n${YELLOW}📈 3단계: XLSX 파일 비교${NC}"
echo -e "${YELLOW}파일: 3_xlsx_comparison.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER${NC}"

python3 3_xlsx_comparison.py "$PROJECT_UUID" "$EPISODE_NUMBER"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 3단계 완료${NC}"
else
    echo -e "${RED}❌ 3단계 실패${NC}"
    exit 1
fi

# 4. 코멘트 생성 실행
echo -e "\n${YELLOW}💬 4단계: 코멘트 생성${NC}"
echo -e "${YELLOW}파일: 4_comment_generator.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER ${GUIDE_PATH:-'none'}${NC}"

# GUIDE_PATH가 비어있으면 'none'으로 전달
GUIDE_PARAM=${GUIDE_PATH:-'none'}
python3 4_comment_generator.py "$PROJECT_UUID" "$EPISODE_NUMBER" "$GUIDE_PARAM"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 4단계 완료${NC}"
else
    echo -e "${RED}❌ 4단계 실패${NC}"
    exit 1
fi

# 5. Google Sheets 업로드 실행
echo -e "\n${YELLOW}📤 5단계: Google Sheets 업로드${NC}"
echo -e "${YELLOW}파일: 5_sheets_uploader_for_llm_results.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER${NC}"

python3 5_sheets_uploader_for_llm_results.py "$PROJECT_UUID" "$EPISODE_NUMBER"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 5단계 완료${NC}"
else
    echo -e "${RED}❌ 5단계 실패${NC}"
    exit 1
fi

# 6. 통합 통계 생성 실행
echo -e "\n${YELLOW}📊 6단계: 통합 통계 생성${NC}"
echo -e "${YELLOW}파일: 6_generate_unified_statistics.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER${NC}"

python3 6_generate_unified_statistics.py "$PROJECT_UUID" "$EPISODE_NUMBER"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 6단계 완료${NC}"
else
    echo -e "${RED}❌ 6단계 실패${NC}"
    exit 1
fi

# 7. 종합 리포트 생성 실행
echo -e "\n${YELLOW}📄 7단계: 종합 리포트 생성${NC}"
echo -e "${YELLOW}파일: 7_comprehensive_report_generator.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER${NC}"

python3 7_comprehensive_report_generator.py "$PROJECT_UUID" "$EPISODE_NUMBER"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 7단계 완료${NC}"
else
    echo -e "${RED}❌ 7단계 실패${NC}"
    exit 1
fi

# 8. 통합 종합 리포트 생성 + Google Sheets 업로드 실행
echo -e "\n${YELLOW}📄 8단계: 통합 종합 리포트 생성 + Google Sheets 업로드${NC}"
echo -e "${YELLOW}파일: 8_integrated_comprehensive_generator_with_sheets.py${NC}"
echo -e "${YELLOW}전달 파라미터: $PROJECT_UUID $EPISODE_NUMBER${NC}"

python3 8_integrated_comprehensive_generator_with_sheets.py "$PROJECT_UUID" "$EPISODE_NUMBER"

# 실행 성공 확인
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 8단계 완료${NC}"
else
    echo -e "${RED}❌ 8단계 실패${NC}"
    exit 1
fi


echo -e "\n${GREEN}================================${NC}"
echo -e "${GREEN}🎉 모든 파이프라인 단계 완료!${NC}"
echo -e "${GREEN}================================${NC}"
