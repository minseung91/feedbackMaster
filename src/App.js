import React, { useState } from 'react';
import './App.css';
import './components/Components.css';
import Sidebar from './components/Sidebar';
import Input from './components/Input';
import Button from './components/Button';
import SettingsSection from './components/SettingsSection';
import RadioGroup from './components/RadioGroup';
import FileUpload from './components/FileUpload';
import Switch from './components/Switch';
import Textarea from './components/Textarea';
import FMLogo from './FM_logo.png';

function App() {
  const [activeMenu, setActiveMenu] = useState('comment');
  const [projectUrl, setProjectUrl] = useState('');
  const [episodes, setEpisodes] = useState(['']);
  const [guideDocument, setGuideDocument] = useState(null);
  const [hasGuideDocument, setHasGuideDocument] = useState(true); // 가이드 문서 유무 선택
  const [isLoading, setIsLoading] = useState(false);
  const [showToast, setShowToast] = useState(false);
  
  // 저장된 설정값 불러오기
  const loadSavedSettings = () => {
    const saved = localStorage.getItem('appSettings');
    if (saved) {
      return JSON.parse(saved);
    }
    return {
      scoringMethod: 'file',
      scoringSheetUrl: '',
      tagMethod: 'file', 
      tagSheetUrl: '',
      slackEnabled: true,
      slackTemplate: '프로젝트 피드백이 완료되었습니다.\n\n점수: {score}점\n태그: {tags}\n\n상세 내용을 확인해주세요.',
      unreadAlertCount: 3
    };
  };
  
  const savedSettings = loadSavedSettings();
  
  // 옵션 설정 상태
  const [scoringMethod, setScoringMethod] = useState(savedSettings.scoringMethod);
  const [scoringFile, setScoringFile] = useState(null);
  const [scoringSheetUrl, setScoringSheetUrl] = useState(savedSettings.scoringSheetUrl);
  
  const [tagMethod, setTagMethod] = useState(savedSettings.tagMethod);
  const [tagFile, setTagFile] = useState(null);
  const [tagSheetUrl, setTagSheetUrl] = useState(savedSettings.tagSheetUrl);
  
  const [slackEnabled, setSlackEnabled] = useState(savedSettings.slackEnabled);
  const [slackTemplate, setSlackTemplate] = useState(savedSettings.slackTemplate);
  const [unreadAlertCount, setUnreadAlertCount] = useState(savedSettings.unreadAlertCount || 3);
  
  // 저장된 값으로 복원
  const resetCommentForm = () => {
    setProjectUrl('');
    setEpisodes(['']);
    setGuideDocument(null);
  };
  
  const resetSettingsForm = () => {
    const saved = loadSavedSettings();
    setScoringMethod(saved.scoringMethod);
    setScoringFile(null);
    setScoringSheetUrl(saved.scoringSheetUrl);
    setTagMethod(saved.tagMethod);
    setTagFile(null);
    setTagSheetUrl(saved.tagSheetUrl);
    setSlackEnabled(saved.slackEnabled);
    setSlackTemplate(saved.slackTemplate);
    setUnreadAlertCount(saved.unreadAlertCount || 3);
  };
  
  // 메뉴 변경 시 저장된 값으로 복원
  const handleMenuClick = (menuKey) => {
    if (menuKey === 'comment') {
      resetCommentForm();
    } else if (menuKey === 'settings') {
      resetSettingsForm();
    }
    setActiveMenu(menuKey);
  };
  
  const handleSaveSettings = () => {
    const settings = {
      scoringMethod,
      scoringSheetUrl,
      tagMethod,
      tagSheetUrl,
      slackEnabled,
      slackTemplate,
      unreadAlertCount
    };
    localStorage.setItem('appSettings', JSON.stringify(settings));
    console.log('저장된 설정:', settings);
    alert('설정이 저장되었습니다.');
  };

  const addEpisode = () => {
    if (episodes.length < 5) {
      setEpisodes([...episodes, '']);
    }
  };

  const removeEpisode = (index) => {
    if (episodes.length > 1) {
      setEpisodes(episodes.filter((_, i) => i !== index));
    }
  };

  const updateEpisode = (index, value) => {
    const newEpisodes = [...episodes];
    newEpisodes[index] = value;
    setEpisodes(newEpisodes);
  };

  // 에피소드 번호를 범위로 변환하는 함수
  const convertEpisodesToRange = (episodes) => {
    // 빈 값 제거 및 숫자로 변환
    const validNumbers = episodes
      .map(ep => parseInt((ep || '').trim()))
      .filter(num => !isNaN(num) && num > 0)
      .sort((a, b) => a - b);
    
    if (validNumbers.length === 0) return '';
    
    // 연속된 숫자들을 범위로 그룹화
    const ranges = [];
    let start = validNumbers[0];
    let end = validNumbers[0];
    
    for (let i = 1; i < validNumbers.length; i++) {
      if (validNumbers[i] === end + 1) {
        // 연속된 숫자
        end = validNumbers[i];
      } else {
        // 연속이 끊김, 현재 범위를 저장하고 새 범위 시작
        ranges.push(start === end ? `${start}` : `${start}-${end}`);
        start = end = validNumbers[i];
      }
    }
    
    // 마지막 범위 추가
    ranges.push(start === end ? `${start}` : `${start}-${end}`);
    
    return ranges.join(',');
  };

  const handleGenerate = async () => {
    // 필수값 검증
    if (!projectUrl.trim()) {
      alert('입력되지 않은 필수 항목이 있습니다. 확인 후 다시 시도해주세요.');
      return;
    }
    
    // 에피소드를 범위로 변환
    const episodesStr = convertEpisodesToRange(episodes);
    if (!episodesStr) {
      alert('입력되지 않은 필수 항목이 있습니다. 확인 후 다시 시도해주세요. (Episodes)');
      return;
    }
    
    // 확인 대화상자
    if (window.confirm('입력된 내용으로 코멘트 및 피드백을 생성하시겠습니까?')) {
      setIsLoading(true);
      
      try {
        // FormData 생성 (파일 업로드를 위해)
        const formData = new FormData();
        formData.append('projectUrl', projectUrl);
        formData.append('episodes', episodesStr);
        formData.append('slackEnabled', slackEnabled);
        formData.append('slackTemplate', slackTemplate);
        
        if (hasGuideDocument && guideDocument) {
          formData.append('guideDocument', guideDocument);
        }
        
        console.log('파이프라인 실행 요청 데이터:', {
          projectUrl,
          episodes: episodesStr,
          slackEnabled,
          slackTemplate,
          hasGuideDocument: hasGuideDocument && !!guideDocument
        });
        
        // EventSource를 사용하여 실시간 로그 수신
        const response = await fetch('http://localhost:4220/run', {
          method: 'POST',
          body: formData
        });
        
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        // 응답이 Server-Sent Events인 경우
        if (response.headers.get('content-type')?.includes('text/event-stream')) {
          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(6));
                  console.log('파이프라인 로그:', data);
                  
                  if (data.type === 'complete') {
                    setIsLoading(false);
                    if (data.success) {
                      setShowToast(true);
                      setTimeout(() => setShowToast(false), 3000);
                    } else {
                      alert('파이프라인 실행 중 오류가 발생했습니다. 콘솔을 확인해주세요.');
                    }
                  } else if (data.type === 'error') {
                    setIsLoading(false);
                    alert('파이프라인 실행 중 오류가 발생했습니다: ' + data.message);
                  }
                } catch (e) {
                  console.log('파싱 오류:', e, line);
                }
              }
            }
          }
        } else {
          // 일반 JSON 응답인 경우
          const result = await response.json();
          setIsLoading(false);
          
          if (result.success) {
            setShowToast(true);
            setTimeout(() => setShowToast(false), 3000);
          } else {
            alert('파이프라인 실행 실패: ' + (result.message || '알 수 없는 오류'));
          }
        }
        
      } catch (error) {
        console.error('파이프라인 실행 오류:', error);
        setIsLoading(false);
        alert('파이프라인 실행 중 오류가 발생했습니다: ' + error.message);
      }
    }
  };

  return (
    <div className="app">
      <Sidebar
        logoSrc={FMLogo}
        menuItems={[
          { key: 'comment', label: '코멘트/피드백 생성하기' },
          { key: 'view', label: '생성 내용 조회하기' },
          { key: 'settings', label: '옵션 설정하기' }
        ]}
        activeMenu={activeMenu}
        onMenuClick={handleMenuClick}
      />

      <div className="content">
        {isLoading && (
          <div className="loading-overlay">
            <div className="loading-spinner">
              <div className="spinner"></div>
              <p>코멘트/피드백을 생성 중입니다...</p>
            </div>
          </div>
        )}
        
        {showToast && (
          <div className="toast">
            코멘트/피드백 생성이 완료되었습니다.
          </div>
        )}
        
        {activeMenu === 'comment' && (
          <>
            <div className="content-header">
              <h2>코멘트/피드백 생성하기</h2>
            </div>
            
            <div className="content-body">
              <SettingsSection title="프로젝트 URL" required={true}>
                <Input
                  type="url"
                  value={projectUrl}
                  onChange={(e) => setProjectUrl(e.target.value)}
                  placeholder="프로젝트 URL을 입력하세요"
                />
              </SettingsSection>

              <SettingsSection title="에피소드 번호 (개별 입력, 최대 5개)" required={true}>
                <p className="input-description">
                  각 필드에 에피소드 번호를 개별로 입력하세요. (예: 1, 2, 3) 자동으로 연속된 번호는 범위로 변환됩니다. (1-3)
                </p>
                {episodes.map((episode, index) => (
                  <div key={index} className="episode-input">
                    <Input
                      type="number"
                      min="1"
                      value={episode}
                      onChange={(e) => updateEpisode(index, e.target.value)}
                      placeholder={`에피소드 ${index + 1} (숫자만)`}
                      className="episode-input-field"
                    />
                    {episodes.length > 1 && (
                      <Button 
                        priority="secondary"
                        size="middle"
                        onClick={() => removeEpisode(index)}
                      >
                        삭제
                      </Button>
                    )}
                  </div>
                ))}
                
                {episodes.length < 5 && (
                  <Button 
                    priority="secondary"
                    size="middle"
                    onClick={addEpisode}
                  >
                    에피소드 추가
                  </Button>
                )}
                
                {/* 미리보기 */}
                {episodes.some(ep => ep.trim()) && (
                  <div className="episode-preview">
                    <small>
                      <strong>변환 결과:</strong> {convertEpisodesToRange(episodes) || '유효한 에피소드를 입력하세요'}
                    </small>
                  </div>
                )}
              </SettingsSection>

              <SettingsSection title="고객사 가이드 문서">
                <RadioGroup
                  name="guideDocumentOption"
                  options={[
                    { value: 'true', label: '가이드 문서 있음' },
                    { value: 'false', label: '가이드 문서 없음' }
                  ]}
                  value={hasGuideDocument ? 'true' : 'false'}
                  onChange={(e) => setHasGuideDocument(e.target.value === 'true')}
                />
                
                {hasGuideDocument && (
                  <div style={{ marginTop: '12px' }}>
                    <FileUpload
                      accept=".xlsx,.xls,.pdf"
                      onChange={(e) => setGuideDocument(e.target.files[0])}
                      selectedFile={guideDocument}
                    />
                  </div>
                )}
              </SettingsSection>
            </div>
            
            <div className="content-footer">
              <Button 
                priority="primary"
                size="large"
                onClick={handleGenerate}
              >
                생성하기
              </Button>
            </div>
          </>
        )}

        {activeMenu === 'view' && (
          <>
            <div className="content-header">
              <h2>생성 내용 조회하기</h2>
            </div>
            
            <div className="content-body">
              <SettingsSection title="생성 코멘트 목록">
                <p className="sheet-description">
                  생성된 코멘트 내용을 확인하려면 아래 버튼을 클릭하여 구글 스프레드시트로 이동하세요.
                </p>
                <Button
                  priority="primary"
                  size="middle"
                  onClick={() => window.open('https://docs.google.com/spreadsheets/d/1oYi9dxDl3HcPzld3mZlXFXAEK5V0HU22HZLthCqmMgo/edit?gid=0#gid=0', '_blank')}
                >
                  생성 코멘트 목록 열기
                </Button>
              </SettingsSection>

              <SettingsSection title="종합 피드백 목록">
                <p className="sheet-description">
                  종합된 피드백 내용을 확인하려면 아래 버튼을 클릭하여 구글 스프레드시트로 이동하세요.
                </p>
                <Button
                  priority="primary"
                  size="middle"
                  onClick={() => window.open('https://docs.google.com/spreadsheets/d/1oYi9dxDl3HcPzld3mZlXFXAEK5V0HU22HZLthCqmMgo/edit?gid=273059995#gid=273059995', '_blank')}
                >
                  종합 피드백 목록 열기
                </Button>
              </SettingsSection>

              <SettingsSection title="슬랙 피드백 발송 이력">
                <p className="sheet-description">
                  슬랙으로 발송된 피드백 이력을 확인하려면 아래 버튼을 클릭하여 구글 스프레드시트로 이동하세요.
                </p>
                <Button
                  priority="primary"
                  size="middle"
                  onClick={() => window.open('https://docs.google.com/spreadsheets/d/1oYi9dxDl3HcPzld3mZlXFXAEK5V0HU22HZLthCqmMgo/edit?gid=1275925141#gid=1275925141', '_blank')}
                >
                  슬랙 피드백 발송 이력 열기
                </Button>
              </SettingsSection>
            </div>
          </>
        )}

        {activeMenu === 'settings' && (
          <>
            <div className="content-header">
              <h2>옵션 설정하기</h2>
            </div>
            
            <div className="content-body">
              <SettingsSection title="점수 산정 기준">
                <RadioGroup
                  name="scoringMethod"
                  options={[
                    { value: 'file', label: '파일 업로드' },
                    { value: 'sheet', label: '구글 스프레드시트 URL' }
                  ]}
                  value={scoringMethod}
                  onChange={(e) => setScoringMethod(e.target.value)}
                />
                {scoringMethod === 'file' ? (
                  <FileUpload
                    onChange={(e) => setScoringFile(e.target.files[0])}
                    selectedFile={scoringFile}
                  />
                ) : (
                  <input
                    type="url"
                    placeholder="구글 스프레드시트 URL을 입력하세요"
                    value={scoringSheetUrl}
                    onChange={(e) => setScoringSheetUrl(e.target.value)}
                    className="url-input"
                  />
                )}
              </SettingsSection>

              <SettingsSection title="태그 적용 기준">
                <RadioGroup
                  name="tagMethod"
                  options={[
                    { value: 'file', label: '파일 업로드' },
                    { value: 'sheet', label: '구글 스프레드시트 URL' }
                  ]}
                  value={tagMethod}
                  onChange={(e) => setTagMethod(e.target.value)}
                />
                {tagMethod === 'file' ? (
                  <FileUpload
                    onChange={(e) => setTagFile(e.target.files[0])}
                    selectedFile={tagFile}
                  />
                ) : (
                  <input
                    type="url"
                    placeholder="구글 스프레드시트 URL을 입력하세요"
                    value={tagSheetUrl}
                    onChange={(e) => setTagSheetUrl(e.target.value)}
                    className="url-input"
                  />
                )}
              </SettingsSection>

              <SettingsSection title="슬랙 메세지 전송 여부">
                <Switch
                  checked={slackEnabled}
                  onChange={(e) => setSlackEnabled(e.target.checked)}
                  label={slackEnabled ? 'ON' : 'OFF'}
                />
              </SettingsSection>

              <SettingsSection title="슬랙 메세지 양식">
                <Textarea
                  value={slackTemplate}
                  onChange={(e) => setSlackTemplate(e.target.value)}
                  placeholder="슬랙 메세지 양식을 입력하세요"
                  rows={6}
                  className="slack-template"
                  helpText="사용 가능한 변수: {score}, {tags}, {project_name}"
                />
              </SettingsSection>

              <SettingsSection title="피드백 미확인 알림">
                <p className="setting-description">
                  특정 작업자가 하나의 프로젝트에서 발송된 피드백 슬랙 메세지를 설정된 횟수 이상 미확인 상태일 때 프로젝트 관리자에게 알림 메세지를 발송하는 기능입니다. 미확인 알림을 위한 횟수를 설정하여 피드백을 확인하지 않는 작업자를 관리하세요.
                </p>
                <div className="unread-alert-input">
                  <input
                    type="number"
                    min="1"
                    value={unreadAlertCount}
                    onChange={(e) => setUnreadAlertCount(parseInt(e.target.value) || 1)}
                    className="number-input"
                  />
                  <span className="input-suffix">회 이상 미확인</span>
                </div>
              </SettingsSection>
            </div>
            
            <div className="content-footer">
              <Button 
                priority="primary"
                size="large"
                onClick={handleSaveSettings}
              >
                옵션 저장하기
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
