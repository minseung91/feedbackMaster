const express = require('express');
const multer = require('multer');
const { spawn, execSync } = require('child_process');
const path = require('path');
const os = require('os');
const cors = require('cors');

// 환경변수 로드 (zshrc에서)
try {
  if (!process.env.HACKATHON_GEMINI_API_KEY) {
    console.log('환경변수 로드 중...');
    const envOutput = execSync('source ~/.zshrc && echo $HACKATHON_GEMINI_API_KEY', { 
      shell: '/bin/zsh',
      encoding: 'utf8' 
    }).trim();
    if (envOutput && envOutput !== '$HACKATHON_GEMINI_API_KEY') {
      process.env.HACKATHON_GEMINI_API_KEY = envOutput;
      console.log('✅ HACKATHON_GEMINI_API_KEY 환경변수 로드 완료');
    }
  }
} catch (error) {
  console.warn('⚠️  환경변수 로드 실패:', error.message);
}

const app = express();
const port = process.env.PORT || 4220;
const SCRIPT_PATH = process.env.SCRIPT_PATH || path.join(__dirname, '..', 'scripts', 'run_pipeline.sh');
const CONDA_ENV = process.env.CONDA_ENV || 'aws-agent'; // conda 환경 이름

// CORS 설정 - 프론트엔드에서 접근할 수 있도록
app.use(cors({
  origin: true,
  credentials: true
}));

app.use(express.json());
app.use(express.urlencoded({ extended: true }));

const upload = multer({ dest: path.join(os.tmpdir(), 'feedbackmaster') });

app.get('/healthz', (_, res) => res.json({ ok: true }));

app.post('/run', upload.single('guideDocument'), (req, res) => {
  console.log('파이프라인 실행 요청 받음:', req.body);
  
  const { projectUrl = '', episodes = '', slackEnabled = 'y', slackTemplate = '' } = req.body;
  const guidePath = req.file ? req.file.path : '';

  if (!projectUrl || !episodes) {
    return res.status(400).json({ error: 'projectUrl and episodes are required' });
  }

  // run_pipeline.sh 에 맞춘 인자 매핑
  const args = ['-u', projectUrl, '-e', episodes];
  
  // 가이드 문서 경로 추가 (없으면 'none' 전달)
  if (guidePath) {
    args.push('-g', guidePath);
  } else {
    args.push('-g', 'none');
  }
  
  // 슬랙 전송 여부 추가
  args.push('-s', slackEnabled === true || slackEnabled === 'true' ? 'y' : 'n');
  
  // 슬랙 템플릿이 있다면 추가
  if (slackTemplate && slackTemplate.trim()) {
    args.push('-t', slackTemplate);
  }

  console.log('실행할 명령어 인자:', args);

  // 실시간 응답을 위한 SSE 헤더 설정
  res.writeHead(200, {
    'Content-Type': 'text/event-stream',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Cache-Control'
  });

  // conda 환경에서 실행 (환경변수 전달)
  const child = spawn('conda', ['run', '-n', CONDA_ENV, '/bin/bash', SCRIPT_PATH, ...args], {
    env: { 
      ...process.env,
      HACKATHON_GEMINI_API_KEY: process.env.HACKATHON_GEMINI_API_KEY
    },
    stdio: ['pipe', 'pipe', 'pipe']
  });

  // 실시간 로그 스트리밍
  child.stdout.on('data', (data) => {
    const message = data.toString();
    console.log('STDOUT:', message);
    res.write(`data: ${JSON.stringify({ type: 'stdout', message })}\n\n`);
  });

  child.stderr.on('data', (data) => {
    const message = data.toString();
    console.log('STDERR:', message);
    res.write(`data: ${JSON.stringify({ type: 'stderr', message })}\n\n`);
  });

  child.on('close', (code) => {
    console.log('파이프라인 실행 완료. Exit code:', code);
    res.write(`data: ${JSON.stringify({ 
      type: 'complete', 
      exitCode: code, 
      success: code === 0,
      message: code === 0 ? '파이프라인이 성공적으로 완료되었습니다.' : '파이프라인 실행 중 오류가 발생했습니다.'
    })}\n\n`);
    res.end();
  });

  child.on('error', (error) => {
    console.error('파이프라인 실행 오류:', error);
    res.write(`data: ${JSON.stringify({ 
      type: 'error', 
      message: `파이프라인 실행 오류: ${error.message}` 
    })}\n\n`);
    res.end();
  });
});

app.listen(port, () => {
  console.log(`[feedbackmaster-backend] http://localhost:${port}`);
});