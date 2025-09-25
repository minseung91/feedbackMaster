"""
Gemini API 및 Anthropic API 토큰 사용량 및 비용 계산 모듈
"""
import threading

class TokenCostCalculator:
    def __init__(self, model_name="gemini-2.5-flash"):
        # 모델별 가격 정보 (100만 토큰당 달러)
        self.pricing = {
            "gemini-2.5-flash": {
                "input": 0.3,
                "output": 2.5,
                "thinking": 2.5,
                "cached": 0.075  # Flash cached input tokens
            },
            "gemini-2.5-pro": {
                # 20만 토큰 미만
                "input_low": 1.25,
                "output_low": 10.0,
                "cached_low": 0.31,
                # 20만 토큰 이상
                "input_high": 2.5,
                "output_high": 15.0,
                "cached_high": 0.625,
                "thinking": 10.0,  # Pro thinking tokens
                "threshold": 200_000  # 20만 토큰 임계값
            },
            # Anthropic Claude 모델들
            "claude-3-5-sonnet-20241022": {
                "input": 3.0,  # $3.00 per 1M input tokens
                "output": 15.0  # $15.00 per 1M output tokens
            },
            "claude-3-5-haiku-20241022": {
                "input": 1.0,  # $1.00 per 1M input tokens
                "output": 5.0   # $5.00 per 1M output tokens
            },
            "claude-3-opus-20240229": {
                "input": 15.0,  # $15.00 per 1M input tokens
                "output": 75.0  # $75.00 per 1M output tokens
            },
            "claude-3-7-sonnet": {
                # 20만 토큰 미만
                "input_low": 3.0,    # $3.00 per 1M tokens
                "output_low": 15.0,  # $15.00 per 1M tokens
                "cache_write_low": 3.75,  # $3.75 per 1M tokens
                "cache_read_low": 0.30,   # $0.30 per 1M tokens
                # 20만 토큰 이상
                "input_high": 6.0,    # $6.00 per 1M tokens
                "output_high": 22.5,  # $22.50 per 1M tokens
                "cache_write_high": 7.50,  # $7.50 per 1M tokens
                "cache_read_high": 0.60,   # $0.60 per 1M tokens
                "threshold": 200_000  # 20만 토큰 임계값
            },
            # Claude Sonnet 4 모델들 (Claude 3.7과 동일한 가격)
            "claude-sonnet-4": {
                # 20만 토큰 미만
                "input_low": 3.0,    # $3.00 per 1M tokens
                "output_low": 15.0,  # $15.00 per 1M tokens
                "cache_write_low": 3.75,  # $3.75 per 1M tokens
                "cache_read_low": 0.30,   # $0.30 per 1M tokens
                # 20만 토큰 이상
                "input_high": 6.0,    # $6.00 per 1M tokens
                "output_high": 22.5,  # $22.50 per 1M tokens
                "cache_write_high": 7.50,  # $7.50 per 1M tokens
                "cache_read_high": 0.60,   # $0.60 per 1M tokens
                "threshold": 200_000  # 20만 토큰 임계값
            }
        }
        
        self.model_name = model_name
        
        # 모델 타입 감지 (Gemini vs Anthropic)
        self.is_anthropic = model_name.startswith('claude')
        
        # Claude 3.7과 Claude Sonnet 4는 복잡한 가격 구조를 가짐
        self.is_claude_3_7 = model_name == 'claude-3-7-sonnet'
        self.is_claude_sonnet_4 = 'claude-sonnet-4' in model_name
        self.has_complex_pricing = self.is_claude_3_7 or self.is_claude_sonnet_4
        
        # 모델 유효성 검사는 속성 설정 후에 수행
        self.validate_model()
        
        # 전체 누적 비용 추적
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_thinking_tokens = 0
        self.total_cached_tokens = 0
        self.total_cache_write_tokens = 0  # Claude 3.7용
        self.total_cost = 0.0
        
        # 스레드 안전성을 위한 락
        self._lock = threading.Lock()
    
    def validate_model(self):
        """지원되는 모델인지 확인"""
        # Claude Sonnet 4 모델들은 모델명에 'claude-sonnet-4'가 포함된 경우 유효
        if self.is_claude_sonnet_4:
            return  # Claude Sonnet 4 모델들은 모두 지원
        
        if self.model_name not in self.pricing:
            supported_models = list(self.pricing.keys()) + ["claude-sonnet-4-* (임의의 Claude Sonnet 4 모델)"]
            raise ValueError(f"지원되지 않는 모델: {self.model_name}. 지원 모델: {supported_models}")
    
    def get_model_pricing(self, input_tokens=0):
        """모델과 토큰 수에 따른 가격 정보 반환"""
        # Claude Sonnet 4 모델의 경우 기본 가격 사용
        if self.is_claude_sonnet_4:
            pricing = self.pricing["claude-sonnet-4"]
        else:
            pricing = self.pricing[self.model_name]
        
        if self.has_complex_pricing:
            # Claude 3.7 Sonnet 및 Claude Sonnet 4 - 복잡한 가격 구조
            model_display = "Claude 3.7" if self.is_claude_3_7 else "Claude Sonnet 4"
            
            if input_tokens >= pricing["threshold"]:
                return {
                    "input_price": pricing["input_high"],
                    "output_price": pricing["output_high"],
                    "thinking_price": 0.0,
                    "cached_price": pricing["cache_read_high"],  # 캐시 읽기 가격
                    "cache_write_price": pricing["cache_write_high"],  # 캐시 쓰기 가격
                    "tier": f"{model_display} High (20만+ 토큰)"
                }
            else:
                return {
                    "input_price": pricing["input_low"],
                    "output_price": pricing["output_low"],
                    "thinking_price": 0.0,
                    "cached_price": pricing["cache_read_low"],
                    "cache_write_price": pricing["cache_write_low"],
                    "tier": f"{model_display} Low (20만 미만 토큰)"
                }
        
        elif self.is_anthropic:
            # 기타 Anthropic Claude 모델들
            return {
                "input_price": pricing["input"],
                "output_price": pricing["output"],
                "thinking_price": 0.0,  # Anthropic은 현재 thinking tokens 없음
                "cached_price": 0.0,   # 기본 Claude 모델들은 캐싱 없음
                "tier": f"Claude {self.model_name.split('-')[2] if len(self.model_name.split('-')) > 2 else 'Unknown'}"
            }
        
        elif self.model_name == "gemini-2.5-flash":
            return {
                "input_price": pricing["input"],
                "output_price": pricing["output"],
                "thinking_price": pricing["thinking"],
                "cached_price": pricing["cached"],
                "tier": "Flash"
            }
        
        elif self.model_name == "gemini-2.5-pro":
            # 입력 토큰 수에 따라 가격 결정
            if input_tokens >= pricing["threshold"]:
                return {
                    "input_price": pricing["input_high"],
                    "output_price": pricing["output_high"],
                    "thinking_price": pricing["thinking"],
                    "cached_price": pricing["cached_high"],
                    "tier": "Pro High (20만+ 토큰)"
                }
            else:
                return {
                    "input_price": pricing["input_low"],
                    "output_price": pricing["output_low"],
                    "thinking_price": pricing["thinking"],
                    "cached_price": pricing["cached_low"],
                    "tier": "Pro Low (20만 미만 토큰)"
                }
        
        return {}
    
    def calculate_batch_cost(self, response):
        """
        API 응답에서 토큰 사용량을 추출하고 비용을 계산 (Gemini/Anthropic 지원)
        
        Args:
            response: API 응답 객체 (Gemini 또는 Anthropic)
            
        Returns:
            dict: 토큰 사용량과 비용 정보
        """
        try:
            if self.is_anthropic:
                # Anthropic API 응답 처리
                usage = getattr(response, 'usage', None)
                if usage:
                    input_tokens = getattr(usage, 'input_tokens', 0)
                    output_tokens = getattr(usage, 'output_tokens', 0)
                    thinking_tokens = 0  # Anthropic은 현재 thinking tokens 없음
                    
                    # Claude 3.7 및 Claude Sonnet 4의 경우 캐싱 토큰 처리
                    if self.has_complex_pricing:
                        cache_creation_tokens = getattr(usage, 'cache_creation_input_tokens', 0)
                        cache_read_tokens = getattr(usage, 'cache_read_input_tokens', 0)
                        cached_tokens = cache_read_tokens  # 읽기 캐시 토큰
                        cache_write_tokens = cache_creation_tokens  # 쓰기 캐시 토큰
                    else:
                        cached_tokens = 0
                        cache_write_tokens = 0
                    
                    total_tokens = input_tokens + output_tokens + cached_tokens + cache_write_tokens
                else:
                    # 메타데이터가 없는 경우 추정
                    input_tokens = self._estimate_tokens_from_text("")  # 입력 텍스트는 별도로 전달받아야 함
                    output_tokens = self._estimate_tokens_from_text(response.content[0].text)
                    thinking_tokens = 0
                    cached_tokens = 0
                    total_tokens = input_tokens + output_tokens
            else:
                # Gemini API 응답 처리
                usage_metadata = getattr(response, 'usage_metadata', None)
                
                if usage_metadata:
                    input_tokens = getattr(usage_metadata, 'prompt_token_count', 0)
                    output_tokens = getattr(usage_metadata, 'candidates_token_count', 0)
                    cached_tokens = getattr(usage_metadata, 'cached_content_token_count', 0)
                    thinking_tokens = getattr(usage_metadata, 'reasoning_tokens', 0)
                    total_tokens = getattr(usage_metadata, 'total_token_count', 
                                         input_tokens + output_tokens + thinking_tokens + cached_tokens)
                else:
                    # 메타데이터가 없는 경우 텍스트 길이로 대략 추정
                    input_tokens = self._estimate_tokens_from_text("")  # 입력 텍스트는 별도로 전달받아야 함
                    output_tokens = self._estimate_tokens_from_text(response.text)
                    thinking_tokens = 0
                    cached_tokens = 0
                    total_tokens = input_tokens + output_tokens
            
            # 모델별 가격 정보 가져오기
            pricing = self.get_model_pricing(input_tokens)
            
            # 비용 계산
            input_cost = (input_tokens / 1_000_000) * pricing["input_price"]
            output_cost = (output_tokens / 1_000_000) * pricing["output_price"]
            thinking_cost = (thinking_tokens / 1_000_000) * pricing["thinking_price"]
            cached_cost = (cached_tokens / 1_000_000) * pricing["cached_price"]
            
            # Claude 3.7 및 Claude Sonnet 4의 경우 캐시 쓰기 비용 추가
            if self.has_complex_pricing and 'cache_write_tokens' in locals():
                cache_write_cost = (cache_write_tokens / 1_000_000) * pricing.get("cache_write_price", 0)
            else:
                cache_write_cost = 0
                cache_write_tokens = 0
            
            batch_cost = input_cost + output_cost + thinking_cost + cached_cost + cache_write_cost
            
            # 누적 통계 업데이트 (스레드 안전)
            with self._lock:
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                self.total_thinking_tokens += thinking_tokens
                self.total_cached_tokens += cached_tokens
                if self.has_complex_pricing and 'cache_write_tokens' in locals():
                    self.total_cache_write_tokens += cache_write_tokens
                self.total_cost += batch_cost
            
            result = {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'thinking_tokens': thinking_tokens,
                'cached_tokens': cached_tokens,
                'total_tokens': total_tokens,
                'input_cost': input_cost,
                'output_cost': output_cost,
                'thinking_cost': thinking_cost,
                'cached_cost': cached_cost,
                'batch_cost': batch_cost,
                'pricing_tier': pricing["tier"],
                'model_name': self.model_name
            }
            
            # Claude 3.7 및 Claude Sonnet 4의 경우 캐시 쓰기 정보 추가
            if self.has_complex_pricing and 'cache_write_tokens' in locals():
                result['cache_write_tokens'] = cache_write_tokens
                result['cache_write_cost'] = cache_write_cost
            
            return result
            
        except Exception as e:
            print(f"토큰 사용량 추출 오류: {e}")
            # 오류 발생시 텍스트 길이로 추정
            estimated_output_tokens = self._estimate_tokens_from_text(response.text)
            pricing = self.get_model_pricing(0)  # 기본 가격으로 추정
            estimated_cost = (estimated_output_tokens / 1_000_000) * pricing["output_price"]
            
            with self._lock:
                self.total_output_tokens += estimated_output_tokens
                self.total_cost += estimated_cost
            
            return {
                'input_tokens': 0,
                'output_tokens': estimated_output_tokens,
                'thinking_tokens': 0,
                'cached_tokens': 0,
                'total_tokens': estimated_output_tokens,
                'input_cost': 0.0,
                'output_cost': estimated_cost,
                'thinking_cost': 0.0,
                'cached_cost': 0.0,
                'batch_cost': estimated_cost,
                'pricing_tier': pricing["tier"],
                'model_name': self.model_name,
                'estimated': True
            }
    
    def _estimate_tokens_from_text(self, text):
        """텍스트 길이로 토큰 수 추정 (1토큰 ≈ 4문자)"""
        if not text:
            return 0
        return len(text) // 4
    
    def get_total_cost_summary(self):
        """전체 누적 비용 요약 반환 (스레드 안전)"""
        with self._lock:
            # 평균 가격 계산 (여러 배치에서 다른 가격대가 적용될 수 있음)
            avg_pricing = self.get_model_pricing(self.total_input_tokens)
            
            summary = {
                'model_name': self.model_name,
                'pricing_tier': avg_pricing["tier"],
                'total_input_tokens': self.total_input_tokens,
                'total_output_tokens': self.total_output_tokens,
                'total_thinking_tokens': self.total_thinking_tokens,
                'total_cached_tokens': self.total_cached_tokens,
                'total_tokens': (self.total_input_tokens + self.total_output_tokens + 
                               self.total_thinking_tokens + self.total_cached_tokens),
                'total_input_cost': (self.total_input_tokens / 1_000_000) * avg_pricing["input_price"],
                'total_output_cost': (self.total_output_tokens / 1_000_000) * avg_pricing["output_price"],
                'total_thinking_cost': (self.total_thinking_tokens / 1_000_000) * avg_pricing["thinking_price"],
                'total_cached_cost': (self.total_cached_tokens / 1_000_000) * avg_pricing["cached_price"],
                'total_cost': self.total_cost
            }
            
            # Claude 3.7 및 Claude Sonnet 4의 경우 캐시 쓰기 정보 추가
            if self.has_complex_pricing:
                summary['total_cache_write_tokens'] = self.total_cache_write_tokens
                summary['total_cache_write_cost'] = (self.total_cache_write_tokens / 1_000_000) * avg_pricing.get("cache_write_price", 0)
                summary['total_tokens'] += self.total_cache_write_tokens
            
            return summary
    
    def print_batch_cost(self, batch_id, cost_info):
        """배치별 비용 정보 출력"""
        estimated_text = " (추정)" if cost_info.get('estimated', False) else ""
        model_info = f" [{cost_info.get('model_name', 'Unknown')} - {cost_info.get('pricing_tier', 'Unknown')}]"
        
        print(f"💰 배치 {batch_id} 토큰 사용량{estimated_text}{model_info}:")
        print(f"   📥 입력: {cost_info['input_tokens']:,} 토큰 (${cost_info['input_cost']:.6f})")
        print(f"   📤 출력: {cost_info['output_tokens']:,} 토큰 (${cost_info['output_cost']:.6f})")
        
        if cost_info.get('thinking_tokens', 0) > 0:
            print(f"   🤔 사고: {cost_info['thinking_tokens']:,} 토큰 (${cost_info['thinking_cost']:.6f})")
        
        if cost_info.get('cached_tokens', 0) > 0:
            print(f"   💾 캐시 읽기: {cost_info['cached_tokens']:,} 토큰 (${cost_info['cached_cost']:.6f})")
        
        if cost_info.get('cache_write_tokens', 0) > 0:
            print(f"   ✏️ 캐시 쓰기: {cost_info['cache_write_tokens']:,} 토큰 (${cost_info['cache_write_cost']:.6f})")
        
        print(f"   💵 배치 총 비용: ${cost_info['batch_cost']:.6f} (₩{cost_info['batch_cost'] * 1400:.2f})")
    
    def print_total_cost_summary(self):
        """전체 비용 요약 출력"""
        summary = self.get_total_cost_summary()
        
        print(f"\n{'='*60}")
        print(f"💰 전체 비용 요약 [{summary['model_name']} - {summary['pricing_tier']}]")
        print(f"{'='*60}")
        print(f"📊 총 토큰 사용량: {summary['total_tokens']:,} 토큰")
        print(f"   📥 입력 토큰: {summary['total_input_tokens']:,} (${summary['total_input_cost']:.6f})")
        print(f"   📤 출력 토큰: {summary['total_output_tokens']:,} (${summary['total_output_cost']:.6f})")
        
        if summary['total_thinking_tokens'] > 0:
            print(f"   🤔 사고 토큰: {summary['total_thinking_tokens']:,} (${summary['total_thinking_cost']:.6f})")
        
        if summary['total_cached_tokens'] > 0:
            print(f"   💾 캐시 읽기 토큰: {summary['total_cached_tokens']:,} (${summary['total_cached_cost']:.6f})")
        
        if summary.get('total_cache_write_tokens', 0) > 0:
            print(f"   ✏️ 캐시 쓰기 토큰: {summary['total_cache_write_tokens']:,} (${summary['total_cache_write_cost']:.6f})")
        
        print(f"💵 총 비용: ${summary['total_cost']:.6f}")
        print(f"💵 총 비용 (원화): ₩{summary['total_cost'] * 1400:.0f} (환율 1,400원 기준)")
        
        # 가격 정보 표시
        if summary['model_name'] in ["gemini-2.5-pro", "claude-3-7-sonnet"] or 'claude-sonnet-4' in summary['model_name']:
            print(f"\n📋 적용된 가격 정보:")
            pricing = self.get_model_pricing(summary['total_input_tokens'])
            print(f"   입력 토큰: ${pricing['input_price']:.2f}/1M")
            print(f"   출력 토큰: ${pricing['output_price']:.2f}/1M")
            
            if pricing.get('thinking_price', 0) > 0:
                print(f"   사고 토큰: ${pricing['thinking_price']:.2f}/1M")
            
            if pricing.get('cached_price', 0) > 0:
                print(f"   캐시 읽기: ${pricing['cached_price']:.3f}/1M")
            
            if pricing.get('cache_write_price', 0) > 0:
                print(f"   캐시 쓰기: ${pricing['cache_write_price']:.2f}/1M")
