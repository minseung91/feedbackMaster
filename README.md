# Feedback Master

AWS Hackathon 2025 프로젝트 - Team LMJ

## 프로젝트 소개

코멘트와 피드백을 자동으로 생성하고 관리하는 웹 애플리케이션입니다.

## 주요 기능

### 1. 코멘트/피드백 생성하기
- 프로젝트 URL 입력
- 에피소드 번호 설정 (최대 5개)
- 고객사 가이드 문서 업로드 (Excel, PDF)
- AI 기반 코멘트 및 피드백 자동 생성

### 2. 생성 내용 조회하기
- 생성 코멘트 목록 조회
- 종합 피드백 목록 조회
- 슬랙 피드백 발송 이력 조회
- 구글 스프레드시트 연동

### 3. 옵션 설정하기
- 점수 산정 기준 설정 (파일 업로드 또는 구글 스프레드시트)
- 태그 적용 기준 설정
- 슬랙 메시지 전송 설정
- 슬랙 메시지 양식 커스터마이징
- 피드백 미확인 알림 설정

## 기술 스택

- **Frontend**: React.js
- **Styling**: CSS3
- **Storage**: localStorage
- **Integration**: Google Sheets, Slack

## 설치 및 실행

### 1. 환경 설정

#### API 키 설정 (필수)
```bash
# ~/.zshrc 파일에 Gemini API 키 추가
echo 'export HACKATHON_GEMINI_API_KEY="your_actual_api_key_here"' >> ~/.zshrc
source ~/.zshrc
```

#### Google Sheets API 설정 (선택사항)
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Google Sheets API 활성화
3. 서비스 계정 생성 및 키 다운로드
4. `scripts/credentials.json`에 키 파일 저장

### 2. 프로젝트 설치

```bash
# 저장소 클론
git clone <repository-url>
cd feedbackMaster

# 프론트엔드 의존성 설치
npm install

# 백엔드 의존성 설치
cd server
npm install
cd ..

# Python 의존성 설치 (파이프라인용)
cd scripts
pip install -r requirements.txt
cd ..
```

### 3. 실행

```bash
# 백엔드 서버 실행 (터미널 1)
cd server
npm start

# 프론트엔드 실행 (터미널 2)
PORT=3001 npm start
```

애플리케이션이 `http://localhost:3001`에서 실행됩니다.

## 프로젝트 구조

```
src/
├── components/          # 재사용 가능한 컴포넌트
│   ├── Button.js
│   ├── Input.js
│   ├── FileUpload.js
│   ├── RadioGroup.js
│   ├── Switch.js
│   ├── Textarea.js
│   ├── SettingsSection.js
│   ├── Sidebar.js
│   └── Components.css
├── App.js              # 메인 애플리케이션
├── App.css             # 메인 스타일
└── FM_logo.png         # 로고 이미지
```

## 팀 정보

**Team LMJ** - AWS Hackathon 2025

## 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.