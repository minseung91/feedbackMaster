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

  const handleGenerate = () => {
    // 필수값 검증
    if (!projectUrl.trim()) {
      alert('입력되지 않은 필수 항목이 있습니다. 확인 후 다시 시도해주세요.');
      return;
    }
    
    const validEpisodes = episodes.filter(ep => ep.trim() !== '');
    if (validEpisodes.length === 0) {
      alert('입력되지 않은 필수 항목이 있습니다. 확인 후 다시 시도해주세요.');
      return;
    }
    
    // 확인 대화상자
    if (window.confirm('입력된 내용으로 코멘트 및 피드백을 생성하시겠습니까?')) {
      setIsLoading(true);
      
      const data = {
        projectUrl,
        episodes: validEpisodes,
        guideDocument
      };
      console.log('AI Agent에 전달할 데이터:', data);
      
      // 5초 후 로딩 종료 및 토스트 표시
      setTimeout(() => {
        setIsLoading(false);
        setShowToast(true);
        
        // 3초 후 토스트 숨김
        setTimeout(() => {
          setShowToast(false);
        }, 3000);
      }, 5000);
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

              <SettingsSection title="에피소드 번호 (최대 5개)" required={true}>
                {episodes.map((episode, index) => (
                  <div key={index} className="episode-input">
                    <Input
                      type="text"
                      value={episode}
                      onChange={(e) => updateEpisode(index, e.target.value)}
                      placeholder={`에피소드 ${index + 1}`}
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
              </SettingsSection>

              <SettingsSection title="고객사 가이드 문서">
                <FileUpload
                  accept=".xlsx,.xls,.pdf"
                  onChange={(e) => setGuideDocument(e.target.files[0])}
                  selectedFile={guideDocument}
                />
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
                  onClick={() => window.open('https://google.com', '_blank')}
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
                  onClick={() => window.open('https://google.com', '_blank')}
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
                  onClick={() => window.open('https://google.com', '_blank')}
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
