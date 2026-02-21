# 프로젝트 상태 보고서 (Project Status Report)

## 프로젝트 정보
- **프로젝트명**: PDF 여백 편집기 (PDF Margin Editor)
- **위치**: `d:\APP\PDF 편집`
- **주요 기능**: 
  - PDF 파일의 홀수/짝수 페이지별 여백 설정 (자르기 및 늘리기)
  - 실시간 미리보기 (Zoom 지원)
  - 직관적인 GUI (PyQt6 기반)

## 현재 버전: V1.7
- **생성일**: 2026-02-21
- **개발 환경**: Python 3.12, PyQt6, PyMuPDF

## 주요 파일 구성
1. `pdf editor 1.7.py`: 메인 애플리케이션 소스 코드
   - 비압축 전환 시 회전 보정 로직 포함
   - "CropBox not in MediaBox" 저장 에러 해결 (V1.7 유지)
2. `VERSION_HISTORY.md`: 버전별 업데이트 내역
3. `README.md`: 프로젝트 사용 설명서

## 사용 방법
1. 터미널에서 `python "pdf editor 1.2.py"` 실행 또는 `dist/pdf editor 1.2.exe` 실행

## 향후 개선 사항 (To-Do)
- [ ] 이미지 미리보기 시 Padding 영역 시각화 개선
- [ ] 여러 파일 일괄 처리 기능 추가
