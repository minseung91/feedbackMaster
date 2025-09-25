#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
종합 번역 리포트 생성기
각 에피소드별 translation_review_llm.csv와 translation_metrics.txt를 수집하여
JSON으로 통합하고 Gemini-2.5-pro를 사용해 종합 리포트를 생성합니다.
"""

import os
import json
import csv
import pandas as pd
from datetime import datetime
from google import genai
from google.genai import types
from typing import Dict, List, Any

class ComprehensiveReportGenerator:
    def __init__(self, base_path: str, previous_feedback_path: str = None):
        """
        리포트 생성기 초기화
        
        Args:
            base_path: preprocessed 디렉토리 경로
            previous_feedback_path: 기존 피드백 파일 경로 (선택사항)
        """
        self.base_path = base_path
        self.previous_feedback_path = previous_feedback_path
        self.has_previous_feedback = previous_feedback_path is not None
        
        # 기존 피드백 여부에 따라 다른 시스템 프롬프트 사용
        if self.has_previous_feedback:
            self.system_prompt = self._get_followup_system_prompt()
        else:
            self.system_prompt = self._get_hardcoded_system_prompt()
        
        # Gemini API 설정 (환경변수에서 API 키를 가져옵니다)
        API_KEY = os.getenv('HACKATHON_GEMINI_API_KEY')
        if not API_KEY:
            raise ValueError("HACKATHON_GEMINI_API_KEY 환경변수를 설정해주세요. ~/.zshrc에 'export HACKATHON_GEMINI_API_KEY=\"your_api_key\"'를 추가하고 'source ~/.zshrc'를 실행하세요.")
        
        self.client = genai.Client(api_key=API_KEY)
        
    def _get_hardcoded_system_prompt(self) -> str:
        """기존 피드백이 없는 경우의 시스템 프롬프트를 파일에서 읽어 반환합니다."""
        prompt_file_path = "../data/prompt/overall_feedback_generation_prompt_default.txt"
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"⚠️ 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
            print("기본 하드코딩된 프롬프트를 사용합니다.")
            return """**역할**: 당신은 번역팀을 총괄하는 전문 번역 품질 관리자(Lead Reviewer)입니다.

**작업 지시**: 다음 JSON 형식의 입력 데이터는 특정 번역 작업자가 작업한 여러 결과물에 대한 검수 기록입니다. 이 데이터를 종합적으로 분석하여, 해당 작업자의 성과를 평가하고 성장을 돕기 위한 **종합 평가 보고서**를 작성하세요.

**입력 데이터 형식**:
1.  **통합 통계 파일**: 프로젝트 전반의 정량적 데이터를 요약한 파일입니다.
2.  **번역 검수 데이터 (JSON 배열)**: 개별 문장에 대한 수정 사항을 상세히 기록한 데이터입니다. 이는 translated_text(번역가의 번역문), edited_text(검수자가 수정한 번역문), tag(수정 태그), comment(각 수정에 대한 검수자 코멘트), episode(각 번역문과 검수문이 어떤 에피소드에 해당하는지)로 구성되어있습니다. 

**분석 및 평가 요구사항**:

1.  **정량적 데이터 요약**:

      * 통합 통계 파일의 내용을 기반으로 **전체 통계, 태그별 빈도 및 비율, 번역 품질 총점 및 등급, 영역별 상세 점수**를 보고서의 '정량 분석' 섹션에 정확히 기재합니다.

2.  **정성적 패턴 분석**:

      * **잘한 점 (Strengths)**: 번역가의 현재 강점을 파악하고 칭찬합니다. 수정이 거의 없었거나, '윤문' 태그만 적용된 사례 등 번역가의 강점이 드러나는 부분을 파악하고 칭찬합니다.
      * **개선점 (Areas for Improvement)**: 현재 작업물에서 나타나는 주요 실수 패턴을 분석합니다. 가장 빈번하게 나타난 태그를 중심으로, 번역가의 주요 실수 패턴을 분석합니다. 예를 들어, 특정 문법 오류가 반복되는지, 용어집 준수율이 낮은지 등을 파악합니다.
      * 분석 시, 반드시 입력 데이터에서 **구체적인 예시(`translated_text` → `edited_text`)와 에피소드 화수를 2-3개 이상 인용**하여 근거를 명확히 제시해야 합니다.

3.  **치명적인 오류 식별 (Critical Issues)**:

      * '오역'과 같이 원문의 의미를 심각하게 훼손한 사례가 있는지 확인합니다.
      * '[가이드 준수] 설정집 반영' 등 프로젝트의 핵심 가이드라인을 반복적으로 위반한 사례가 있는지 확인합니다.
      * 이러한 치명적인 오류는 별도로 분류하여 명확하게 지적해야 합니다.

4.  **종합 의견 및 제언 (Overall Summary & Recommendations)**:

      * 위의 모든 분석 내용을 바탕으로, **번역가에게 직접 전달하는 부드럽고 건설적인 어조**로 현재 역량 수준에 대한 종합 평가를 작성합니다.
      * 평가는 감정적이거나 모호해서는 안 되며, 데이터를 기반으로 한 객관적이고 건설적인 피드백을 제공해야 합니다.
      * 칭찬과 개선점을 균형 있게 제시하여 번역가가 피드백을 긍정적으로 수용하고 성장할 수 있도록 독려해야 합니다.
      * 앞으로의 성장을 위해 무엇을 집중적으로 개선해야 할지, 어떤 점을 유의해야 할지에 대한 구체적이고 실행 가능한 제언을 1~2가지 제시합니다.
      * 특히 특정 부분에서 개선이 필요하다고 할 때 실제의 예시(2~3개)와 에피소드 화수를 기반으로 피드백을 제공해서 작업자가 어떤 부분에 있어서 실수를 했었는지 구체적으로 파악할 수 있도록 합니다.
      * 주의: 이 섹션은 번역가의 성장을 돕는 정성적 피드백에 집중해야 하므로, 정량 분석의 점수나 등급과 같은 수치적 결과를 절대로 직접 언급하지 않습니다.

**출력 형식**:
다음 마크다운(Markdown) 형식을 사용하여 보고서를 작성하세요.

```markdown
## 번역가 종합 평가 보고서

**번역가 ID**: [번역가 ID 또는 이름]
**평가 기간**: [데이터에 해당하는 작업 기간]

---


### 1. 정량 분석 (Quantitative Analysis)

* **전체 통계**:
    * 검수 에피소드: [에피소드 수]개
    * 총 텍스트박스: [텍스트박스 수]개
    * 검수 비율: [검수 비율]%
* **수정 태그 빈도 및 비율**:
    * 윤문: [비율]%
    * 문법: [비율]%
    * 오역: [비율]%
    * 의성어/의태어: [비율]%
    * 오탈자: [비율]%
    * 가이드 준수: [비율]%
        * [가이드 준수] 표기법 준수: [비율]%
        * [가이드 준수] 설정집 반영: [비율]%
        * [가이드 준수] 이외 항목 미준수: [비율]%

* **번역 품질 평가 점수**:
    * **총점**: [총점]/24
    * **등급**: [등급]
* **영역별 상세 점수**:
    * 오역: [점수]/6
    * 문법: [점수]/6
    * 윤문: [점수]/6
    * 오탈자: [점수]/3
    * 가이드 준수: [점수]/3

---

### 2. 주요 수정 사항 분석 (Qualitative Analysis)

#### **잘한 점 (Strengths)**

* (예: 전반적으로 자연스러운 문체 구사 능력이 뛰어나며, 특히 캐릭터의 감정을 살리는 '윤문' 외에는 큰 수정이 필요 없는 경우가 많았습니다.)

#### **개선점 (Areas for Improvement)**

* **[가장 빈번한 태그, 예: 문법]**: [해당 태그와 관련된 실수 패턴에 대한 설명]
    * **예시 1**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)

* **[두 번째로 빈번한 태그, 예: [가이드 준수] 설정집 반영]**: [해당 태그와 관련된 실수 패턴에 대한 설명]
    * **예시 1**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)

---

### 3. 치명적인 오류 (Critical Issues)

* (치명적인 '오역'이나 가이드라인 위반 사례가 있었다면 여기에 구체적인 예시와 함께 서술합니다. 없다면 "이번 평가 기간 동안 특별한 치명적 오류는 발견되지 않았습니다."라고 작성합니다.)
    * **오역 사례**: `translated_text` → `edited_text` (에피소드 n화)
        * **코멘트**: 원문의 핵심 의미를 반대로 번역하여 사용자에게 큰 혼란을 줄 수 있는 심각한 오류입니다.

---

### 4. 총평 및 권장사항 (Overall Summary & Recommendations)

(예시)
번역가님께서는 [전반적인 강점에 대한 부드러운 칭찬과 요약]과 같은 긍정적인 역량을 꾸준히 보여주고 계십니다.

다만, **[여전히 개선이 필요한 점, 예: 특정 문법 오류] 부분은 개선을 위한 집중적인 노력이 필요해 보입니다.** 이 점을 보완하신다면 앞으로 더욱 뛰어난 결과물을 만들어내실 수 있을 것입니다.

**1. [개선 제언 1, 예: 문맥의 흐름을 고려한 번역]**
* [제언에 대한 구체적인 설명]
* **참고 예시**: `translated_text` → `edited_text` (에피소드 n화)
* **참고 예시**: `translated_text` → `edited_text` (에피소드 n화)
* **참고 예시**: `translated_text` → `edited_text` (에피소드 n화)

**2. [개선 제언 2, 예: 특정 문법 규칙 재점검]**
* [제언에 대한 구체적인 설명]
* 특히, 다음 문법 사항들에 조금 더 주의를 기울여 주시면 좋겠습니다.
    * **[자주 틀리는 문법 규칙 1]**: [규칙에 대한 간략한 설명]
        * **예시**: `translated_text` → `edited_text` (에피소드 n화)
        * **예시**: `translated_text` → `edited_text` (에피소드 n화)
        * **예시**: `translated_text` → `edited_text` (에피소드 n화)

앞으로 위 사항들을 염두에 두시고 작업에 임해주신다면 번역의 정확성과 완성도를 더욱 높일 수 있을 것이라 확신합니다. 번역가님의 성장을 항상 응원하겠습니다.
```"""
        except Exception as e:
            print(f"⚠️ 프롬프트 파일 읽기 오류: {e}")
            print("기본 하드코딩된 프롬프트를 사용합니다.")
            return """**역할**: 당신은 번역팀을 총괄하는 전문 번역 품질 관리자(Lead Reviewer)입니다.

**작업 지시**: 다음 JSON 형식의 입력 데이터는 특정 번역 작업자가 작업한 여러 결과물에 대한 검수 기록입니다. 이 데이터를 종합적으로 분석하여, 해당 작업자의 성과를 평가하고 성장을 돕기 위한 **종합 평가 보고서**를 작성하세요."""
    
    def _get_followup_system_prompt(self) -> str:
        """기존 피드백이 있는 경우의 시스템 프롬프트를 파일에서 읽어 반환합니다."""
        prompt_file_path = "../data/prompt/overall_feedback_generation_prompt_followup.txt"
        try:
            with open(prompt_file_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"⚠️ 프롬프트 파일을 찾을 수 없습니다: {prompt_file_path}")
            print("기본 하드코딩된 프롬프트를 사용합니다.")
            return """**역할**: 당신은 번역팀을 총괄하는 전문 번역 품질 관리자(Lead Reviewer)입니다.

**작업 지시**: 다음 JSON 형식의 입력 데이터는 특정 번역 작업자가 작업한 여러 결과물에 대한 검수 기록입니다. 이 데이터를 종합적으로 분석하여, 해당 작업자의 성과를 평가하고 성장을 돕기 위한 **종합 평가 보고서**를 작성하세요.

**입력 데이터 형식**:
1.  **통합 통계 파일**: 프로젝트 전반의 정량적 데이터를 요약한 파일입니다.
2.  **번역 검수 데이터 (JSON 배열)**: 이번 종합 평가 작성을 위한 번역 검수 데이터입니다. 이는 개별 문장에 대한 수정 사항을 상세히 기록한 데이터입니다. 이는 translated_text(번역가의 번역문), edited_text(검수자가 수정한 번역문), tag(수정 태그), comment(각 수정에 대한 검수자 코멘트), episode(각 번역문과 검수문이 어떤 에피소드에 해당하는지)로 구성되어있습니다.
3.  **이전 작업에 대한 종합 보고서**: 이전에 작업에 대한 종합 보고서입니다. 이전 피드백 대비 성장 분석 시 반드시 현재 평가와 비교 분석해야 합니다.**


**분석 및 평가 요구사항**:

1.  **정량적 데이터 요약**:

      * 통합 통계 파일의 내용을 기반으로 **전체 통계, 태그별 빈도 및 비율, 번역 품질 총점 및 등급, 영역별 상세 점수**를 보고서의 '정량 분석' 섹션에 정확히 기재합니다.

2.  **정성적 패턴 분석**:

      * **잘한 점 (Strengths)**: 번역가의 현재 강점을 파악하고 칭찬합니다. 수정이 거의 없었거나, '윤문' 태그만 적용된 사례 등 번역가의 강점이 드러나는 부분을 파악하고 칭찬합니다.
      * **개선점 (Areas for Improvement)**: 현재 작업물에서 나타나는 주요 실수 패턴을 분석합니다. 가장 빈번하게 나타난 태그를 중심으로, 번역가의 주요 실수 패턴을 분석합니다. 예를 들어, 특정 문법 오류가 반복되는지, 용어집 준수율이 낮은지 등을 파악합니다.
      * 분석 시, 반드시 입력 데이터에서 **구체적인 예시(`translated_text` → `edited_text`)와 에피소드 화수를 2-3개 이상 인용**하여 근거를 명확히 제시해야 합니다.

3.  **치명적인 오류 식별 (Critical Issues)**:

      * '오역'과 같이 원문의 의미를 심각하게 훼손한 사례가 있는지 확인합니다.
      * '[가이드 준수] 설정집 반영' 등 프로젝트의 핵심 가이드라인을 반복적으로 위반한 사례가 있는지 확인합니다.
      * 이러한 치명적인 오류는 별도로 분류하여 명확하게 지적해야 합니다.

4.  **이전 피드백 대비 성장 분석 (`previous_feedback` 활용)**:

      * 이전 작업에 대한 종합 보고서를 기반으로, 이전에 지적되었던 항목들이 현재 작업에서 개선되었는지 혹은 여전히 문제가 되는지를 분석합니다.
      * **개선된 점**과 **여전히 개선이 필요한 점**을 각각 구체적인 현재 예시와 함께 제시하여 변화를 명확하게 보여줍니다.
      * 수치적으로 이전 작업 대비 오류 유형에서의 비율이 어떤 식으로 변화하였는지도 함께 분석합니다.

5.  **종합 의견 및 제언 (Overall Summary & Recommendations)**:

      * 위의 모든 분석 내용을 바탕으로, **번역가에게 직접 전달하는 부드럽고 건설적인 어조**로 현재 역량 수준에 대한 종합 평가를 작성합니다.
      * 평가는 감정적이거나 모호해서는 안 되며, 데이터를 기반으로 한 객관적이고 건설적인 피드백을 제공해야 합니다.
      * 칭찬과 개선점을 균형 있게 제시하여 번역가가 피드백을 긍정적으로 수용하고 성장할 수 있도록 독려해야 합니다.
      * 앞으로의 성장을 위해 무엇을 집중적으로 개선해야 할지, 어떤 점을 유의해야 할지에 대한 구체적이고 실행 가능한 제언을 1~2가지 제시합니다.
      * 특히 특정 부분에서 개선이 필요하다고 할 때 실제의 예시(2~3개)와 에피소드 화수를 기반으로 피드백을 제공해서 작업자가 어떤 부분에 있어서 실수를 했었는지 구체적으로 파악할 수 있도록 합니다.
      **이전 대비 성장하거나 개선된 부분을 명확히 언급하여 격려**하고, 여전히 개선이 필요한 점은 장기적인 관점에서 조언합니다.
      * 주의: 이 섹션은 번역가의 성장을 돕는 정성적 피드백에 집중해야 하므로, 정량 분석의 점수나 등급과 같은 수치적 결과를 절대로 직접 언급하지 않습니다.

**출력 형식**:
다음 마크다운(Markdown) 형식을 사용하여 보고서를 작성하세요.

```markdown
## 번역가 종합 평가 보고서

**번역가 ID**: [번역가 ID 또는 이름]
**평가 기간**: [데이터에 해당하는 작업 기간]

---


### 1. 정량 분석 (Quantitative Analysis)

* **전체 통계**:
    * 검수 에피소드: [에피소드 수]개
    * 총 텍스트박스: [텍스트박스 수]개
    * 검수 비율: [검수 비율]%
* **수정 태그 빈도 및 비율**:
    * 윤문: [비율]%
    * 문법: [비율]%
    * 오역: [비율]%
    * 의성어/의태어: [비율]%
    * 오탈자: [비율]%
    * 가이드 준수: [비율]%
        * [가이드 준수] 표기법 준수: [비율]%
        * [가이드 준수] 설정집 반영: [비율]%
        * [가이드 준수] 이외 항목 미준수: [비율]%

* **번역 품질 평가 점수**:
    * **총점**: [총점]/24
    * **등급**: [등급]
* **영역별 상세 점수**:
    * 오역: [점수]/6
    * 문법: [점수]/6
    * 윤문: [점수]/6
    * 오탈자: [점수]/3
    * 가이드 준수: [점수]/3

---

### 2. 주요 수정 사항 분석 (Qualitative Analysis)

#### **잘한 점 (Strengths)**

* (예: 전반적으로 자연스러운 문체 구사 능력이 뛰어나며, 특히 캐릭터의 감정을 살리는 '윤문' 외에는 큰 수정이 필요 없는 경우가 많았습니다.)

#### **개선점 (Areas for Improvement)**

* **[가장 빈번한 태그, 예: 문법]**: [해당 태그와 관련된 실수 패턴에 대한 설명]
    * **예시 1**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)

* **[두 번째로 빈번한 태그, 예: [가이드 준수] 설정집 반영]**: [해당 태그와 관련된 실수 패턴에 대한 설명]
    * **예시 1**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)
    * **예시 2**: `translated_text` → `edited_text` (에피소드 n화)

---

### 3. 치명적인 오류 (Critical Issues)

* (치명적인 '오역'이나 가이드라인 위반 사례가 있었다면 여기에 구체적인 예시와 함께 서술합니다. 없다면 "이번 평가 기간 동안 특별한 치명적 오류는 발견되지 않았습니다."라고 작성합니다.)
    * **오역 사례**: `translated_text` → `edited_text` (에피소드 n화)
        * **코멘트**: 원문의 핵심 의미를 반대로 번역하여 사용자에게 큰 혼란을 줄 수 있는 심각한 오류입니다.

---

### 4. 이전 피드백 대비 성장 분석 (Analysis of Growth Since Last Review)

이전 보고서에서 제시된 피드백을 바탕으로, 번역가의 성장 및 개선점을 **정량적 데이터와 정성적 예시를 통합하여** 심층적으로 분석합니다.

#### **개선된 점 (Improvements)**
* **어떤 점이 개선되었는지 분석**: 이전 보고서에서 지적된 문제점이 이번 작업에서 어떻게 개선되었는지 구체적으로 분석합니다.
* **수치적 변화 제시**: 관련 오류 태그의 비율 변화를 언급하여 개선점을 데이터로 증명합니다. (예: "지난번 15%에 달했던 '[가이드 준수] 설정집 반영' 오류가 이번에는 3%로 크게 감소했습니다.")
* **작성 가이드**: 만약 이전 피드백 항목이 뚜렷하게 개선되지 않았다면, 기존에 잘하고 있던 점(예: 자연스러운 문장 구사력)을 꾸준히 유지하고 있는 부분을 언급하는 것으로 대체할 수 있습니다.

#### **여전히 개선이 필요한 점 (Areas Still Needing Improvement)**
* **어떤 점이 여전한지 분석**: 지난번에도 지적되었으나 이번 작업에서도 유사하게 반복되는 실수 패턴이나 습관을 분석합니다.
* **수치적 근거 제시**: 해당 실수가 속한 태그의 비율이 여전히 높거나 이전과 비슷하다는 점을 수치로 언급합니다. (예: "지난번과 마찬가지로 '문법' 오류가 전체 수정의 25%를 차지하며, 특히 조사의 어색한 사용이 자주 발견됩니다.")
* **구체적인 실수 예시 인용**: 문제점이 명확히 드러나는 **실수 예시(`translated_text` → `edited_text`)를 에피소드 화수와 함께 2~3개 이상 제시**하여, 번역가가 자신의 패턴을 객관적으로 인지하고 개선 방향을 잡을 수 있도록 돕습니다.

---

### 5. 종합 의견 및 제언 (Overall Summary & Recommendations)

#### **종합 의견**
* **시작**: 이번 평가 기간 동안 보여준 긍정적인 모습과 성장을 먼저 언급하며 대화를 시작합니다. (예: "이번 작업에서도 번역가님 특유의 유려한 문체 덕분에 전반적으로 가독성이 매우 좋았습니다. 특히 지난번 피드백 드렸던 [개선된 점, 예: 설정집 준수] 부분을 신경 써주신 덕분에 캐릭터의 톤앤매너가 한층 안정되었습니다.")
* **전환**: 칭찬을 바탕으로 자연스럽게 개선이 필요한 부분으로 넘어갑니다. '하지만'이나 '다만' 같은 직접적인 부정 접속사보다는, 성장을 위한 제안의 형태로 부드럽게 연결합니다. (예: "이러한 강점을 바탕으로, 다음 단계로 더욱 성장하기 위해 [가장 중요한 개선점 1가지, 예: 조사의 자연스러운 활용]에 조금 더 집중해 보시는 것을 제안합니다.")

#### **성장을 위한 제언 (Actionable Recommendations)**
가장 중요하고 시급한 개선점 순서대로, 아래 형식에 맞춰 구체적인 실행 방안을 제안합니다. '치명적인 오류'가 있었다면 해당 내용을 가장 첫 번째 제언으로 다룹니다.

**1. [제언 1의 제목]**
* **현상 진단**: 현재 나타나는 패턴을 객관적으로 설명합니다.
* **개선 방안**: 구체적이고 실천 가능한 방법을 제시합니다.
* **참고 예시 (해당 패턴이 드러난 사례 2~3개 인용)**
    * `translated_text` → `edited_text` (n화)
    * `translated_text` → `edited_text` (n화)
    * `translated_text` → `edited_text` (n화)

**2. [제언 2의 제목]**
* **현상 진단**: (위와 동일)
* **개선 방안**: (위와 동일)
* **참고 예시 (해당 패턴이 드러난 사례 2~3개 인용)**
    * `translated_text` → `edited_text` (n화)
    * `translated_text` → `edited_text` (n화)
    * `translated_text` → `edited_text` (n화)

**마무리**: 긍정적인 격려와 기대를 담은 메시지로 마무리합니다. (예: "위에 제안 드린 부분들을 염두에 두시면, 번역가님의 강점인 뛰어난 문장력이 더욱 빛을 발할 것이라 확신합니다. 다음 작업에서의 멋진 결과물을 기대하며, 번역가님의 성장을 항상 응원하겠습니다.")
```"""
        except Exception as e:
            print(f"⚠️ 프롬프트 파일 읽기 오류: {e}")
            print("기본 하드코딩된 프롬프트를 사용합니다.")
            return """**역할**: 당신은 번역팀을 총괄하는 전문 번역 품질 관리자(Lead Reviewer)입니다.

**작업 지시**: 다음 JSON 형식의 입력 데이터는 특정 번역 작업자가 작업한 여러 결과물에 대한 검수 기록입니다. 이 데이터를 종합적으로 분석하여, 해당 작업자의 성과를 평가하고 성장을 돕기 위한 **종합 평가 보고서**를 작성하세요."""
    
    def _get_episode_directories(self) -> List[str]:
        """에피소드 디렉토리 목록을 정렬하여 반환합니다."""
        directories = []
        for item in os.listdir(self.base_path):
            item_path = os.path.join(self.base_path, item)
            if os.path.isdir(item_path) and item.isdigit():
                directories.append(item)
        
        # 숫자 순으로 정렬
        return sorted(directories, key=int)
    
    def _load_previous_feedback(self) -> str:
        """기존 피드백 파일을 읽어서 반환합니다."""
        if not self.has_previous_feedback or not self.previous_feedback_path:
            return ""
        
        try:
            with open(self.previous_feedback_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"기존 피드백 파일을 찾을 수 없습니다: {self.previous_feedback_path}")
            return ""
        except Exception as e:
            print(f"기존 피드백 파일 읽기 오류: {self.previous_feedback_path}, {str(e)}")
            return ""
    
    def _load_unified_statistics(self) -> str:
        """unified_statistics_summary.txt 파일을 읽어서 반환합니다."""
        unified_stats_path = os.path.join(self.base_path, 'unified_statistics_summary.txt')
        
        try:
            with open(unified_stats_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except FileNotFoundError:
            print(f"통합 통계 파일을 찾을 수 없습니다: {unified_stats_path}")
            return ""
        except Exception as e:
            print(f"통합 통계 파일 읽기 오류: {unified_stats_path}, {str(e)}")
            return ""
    
    def _load_csv_data(self, csv_path: str) -> List[Dict[str, Any]]:
        """CSV 파일을 읽어서 딕셔너리 리스트로 반환합니다."""
        try:
            data = []
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 모든 필드 추출 (translated_text, edited_text, tag, comment)
                    tag = row.get('tag', '').strip()
                    comment = row.get('comment', '').strip()
                    translated_text = row.get('target', '').strip()
                    edited_text = row.get('val', '').strip()
                    
                    # 빈 태그는 제외
                    if tag:
                        data.append({
                            'translated_text': translated_text,
                            'edited_text': edited_text,
                            'tag': tag,
                            'comment': comment
                        })
            return data
        except FileNotFoundError:
            print(f"파일을 찾을 수 없습니다: {csv_path}")
            return []
        except Exception as e:
            print(f"CSV 파일 읽기 오류: {csv_path}, {str(e)}")
            return []
    
    
    def collect_episode_data(self) -> Dict[str, Any]:
        """모든 에피소드의 데이터를 수집하여 JSON 형태로 반환합니다."""
        episode_dirs = self._get_episode_directories()
        collected_data = {
            'metadata': {
                'collection_time': datetime.now().isoformat(),
                'base_path': self.base_path,
                'total_episodes': len(episode_dirs)
            },
            'episodes': {}
        }
        
        all_review_data = []  # 전체 리뷰 데이터를 하나로 통합
        
        for episode in episode_dirs:
            episode_path = os.path.join(self.base_path, episode)
            
            # CSV 파일 경로
            csv_path = os.path.join(episode_path, 'translation_review_llm.csv')
            
            # 데이터 로드 (metrics 제외)
            csv_data = self._load_csv_data(csv_path)
            
            # 에피소드별 데이터 저장
            collected_data['episodes'][f'episode_{episode}'] = {
                'review_data': csv_data,
                'review_count': len(csv_data)
            }
            
            # 전체 데이터에 추가 (에피소드 정보 포함)
            for item in csv_data:
                item_with_episode = item.copy()
                item_with_episode['episode'] = f'episode_{episode}'
                all_review_data.append(item_with_episode)
            
            print(f"에피소드 {episode} 데이터 수집 완료: {len(csv_data)}개 항목")
        
        collected_data['all_review_data'] = all_review_data
        collected_data['total_review_count'] = len(all_review_data)
        
        return collected_data
    
    def _create_user_prompt(self, collected_data: Dict[str, Any]) -> str:
        """사용자 프롬프트를 생성합니다."""
        user_prompt = "다음은 번역가의 작업 결과에 대한 종합 데이터입니다.\n\n"
        
        # 기존 피드백이 있는 경우 포함
        if self.has_previous_feedback:
            previous_feedback = self._load_previous_feedback()
            if previous_feedback:
                user_prompt += "**이전 피드백**\n"
                user_prompt += previous_feedback + "\n\n"
                user_prompt += "---\n\n"
        
        # 통합 통계 정보
        unified_stats = self._load_unified_statistics()
        if unified_stats:
            user_prompt += "**통합 번역 품질 분석 통계**\n"
            user_prompt += unified_stats + "\n\n"
        else:
            # 통합 통계 파일이 없는 경우 기본 통계 사용
            user_prompt += f"**전체 통계**\n"
            user_prompt += f"- 총 에피소드 수: {collected_data['metadata']['total_episodes']}개\n"
            user_prompt += f"- 총 검수 항목 수: {collected_data['total_review_count']}개\n\n"
        
        user_prompt += "**번역 검수 데이터 (JSON 형식)**\n"
        user_prompt += json.dumps(collected_data['all_review_data'], ensure_ascii=False, indent=2)
        
        return user_prompt
    
    def generate_report(self, collected_data: Dict[str, Any]) -> str:
        """Gemini-2.5-pro를 사용하여 종합 리포트를 생성합니다."""
        user_prompt = self._create_user_prompt(collected_data)
        
        try:
            print("Gemini-2.5-pro를 사용하여 리포트 생성 중...")
            
            # 시스템 프롬프트와 사용자 프롬프트를 결합
            full_prompt = f"{self.system_prompt}\n\n{user_prompt}"
            
            response = self.client.models.generate_content(
                model="gemini-2.5-pro",
                config=types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=0
                ),
                contents=user_prompt
            )
            
            return response.text
            
        except Exception as e:
            error_msg = f"리포트 생성 중 오류 발생: {str(e)}"
            print(error_msg)
            return error_msg
    
    def save_report(self, report_content: str, output_path: str = None) -> str:
        """리포트를 텍스트 파일로 저장합니다."""
        if output_path is None:
            output_path = os.path.join(self.base_path, f"comprehensive_report.txt")
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(report_content)
            print(f"리포트가 저장되었습니다: {output_path}")
            return output_path
        except Exception as e:
            error_msg = f"리포트 저장 중 오류 발생: {str(e)}"
            print(error_msg)
            return error_msg
    
    
    def generate_comprehensive_report(self) -> str:
        """전체 프로세스를 실행하여 종합 리포트를 생성합니다."""
        print("=== 종합 번역 리포트 생성 시작 ===")
        
        # 1. 데이터 수집
        print("\n1. 에피소드별 데이터 수집 중...")
        collected_data = self.collect_episode_data()
        
        # 2. AI 리포트 생성
        print("\n2. AI 리포트 생성 중...")
        report = self.generate_report(collected_data)
        
        # 3. 리포트 저장
        print("\n3. 리포트 저장 중...")
        output_path = self.save_report(report)
        
        print(f"\n=== 종합 리포트 생성 완료 ===")
        print(f"📄 AI 리포트: {output_path}")
        
        return output_path


def parse_episode_range(episode_range):
    """에피소드 범위 문자열을 파싱하여 시작과 끝 번호를 반환"""
    try:
        if '-' in episode_range:
            start, end = episode_range.split('-')
            return int(start), int(end)
        else:
            # 단일 에피소드인 경우
            num = int(episode_range)
            return num, num
    except ValueError:
        return None, None

def find_previous_episode_range(project_uuid, current_episode_range):
    """현재 에피소드 범위 이전의 가장 최근 에피소드 범위를 찾기"""
    import os
    
    base_data_dir = "../data"
    project_dir = os.path.join(base_data_dir, project_uuid)
    
    if not os.path.exists(project_dir):
        return None
    
    # 현재 에피소드 범위 파싱
    current_start, current_end = parse_episode_range(current_episode_range)
    if current_start is None:
        return None
    
    # 프로젝트 디렉토리 내의 모든 에피소드 범위 디렉토리 찾기
    episode_ranges = []
    for item in os.listdir(project_dir):
        item_path = os.path.join(project_dir, item)
        if os.path.isdir(item_path):
            start, end = parse_episode_range(item)
            if start is not None and end is not None:
                # 현재 범위보다 이전인 것만 추가
                if end < current_start:
                    episode_ranges.append((item, start, end))
    
    if not episode_ranges:
        return None
    
    # 가장 최근(끝 번호가 가장 큰) 이전 범위 찾기
    episode_ranges.sort(key=lambda x: x[2], reverse=True)  # end 번호로 내림차순 정렬
    previous_range = episode_ranges[0][0]  # 디렉토리 이름 반환
    
    print(f"🔍 이전 에피소드 범위 발견: {previous_range}")
    return previous_range

def find_previous_comprehensive_report(project_uuid, current_episode_range):
    """이전 에피소드 범위의 comprehensive_report.txt 파일 경로 찾기"""
    import os
    
    previous_range = find_previous_episode_range(project_uuid, current_episode_range)
    if not previous_range:
        print("📋 이전 에피소드 범위가 없습니다. 새로운 피드백을 생성합니다.")
        return None
    
    # 이전 범위의 comprehensive_report.txt 경로 구성
    base_data_dir = "../data"
    report_path = os.path.join(base_data_dir, project_uuid, previous_range, "preprocessed", "comprehensive_report.txt")
    
    if os.path.exists(report_path):
        print(f"📄 이전 피드백 파일 발견: {report_path}")
        return report_path
    else:
        print(f"⚠️ 이전 피드백 파일이 없습니다: {report_path}")
        return None

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
        print("❌ 사용법: python3 7_comprehensive_report_generator.py <project_uuid> <episode_number>")
        return 1
    
    project_uuid = sys.argv[1]
    episode_number = sys.argv[2]
    
    print(f"🔍 프로젝트 UUID: {project_uuid}")
    print(f"🔍 에피소드 번호: {episode_number}")
    
    # preprocessed 디렉토리 자동 검색
    base_path = find_preprocessed_directory(project_uuid, episode_number)
    if not base_path:
        return 1
    
    print(f"📁 기본 경로: {base_path}")
    
    # 이전 에피소드 범위의 종합 피드백 파일 자동 검색
    previous_feedback_path = find_previous_comprehensive_report(project_uuid, episode_number)
    
    try:
        # 리포트 생성기 인스턴스 생성
        generator = ComprehensiveReportGenerator(base_path, previous_feedback_path)
        
        if generator.has_previous_feedback:
            print(f"📄 기존 피드백 파일을 사용합니다: {previous_feedback_path}")
        else:
            print("🆕 새로운 피드백을 생성합니다.")
        
        # 종합 리포트 생성
        output_path = generator.generate_comprehensive_report()
        
        print(f"\n✅ 성공적으로 완료되었습니다!")
        print(f"📄 리포트 파일: {output_path}")
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
