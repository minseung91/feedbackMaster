import React, { useRef } from 'react';
import Button from './Button';

const FileUpload = ({ 
  accept = '.xlsx,.xls,.csv', 
  onChange, 
  selectedFile, 
  className = '' 
}) => {
  const fileInputRef = useRef(null);

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  return (
    <div className={`file-upload ${className}`}>
      <input
        ref={fileInputRef}
        type="file"
        accept={accept}
        onChange={onChange}
        style={{ display: 'none' }}
      />
      <div className="file-upload-content">
        <Button
          priority="secondary"
          size="middle"
          onClick={handleButtonClick}
        >
          파일 선택
        </Button>
        <span className={selectedFile ? "file-name selected" : "file-name placeholder"}>
          {selectedFile ? selectedFile.name : '선택된 파일이 없습니다. 왼쪽의 [파일 선택] 버튼을 클릭하여 대상을 선택해주세요.'}
        </span>
      </div>
    </div>
  );
};

export default FileUpload;