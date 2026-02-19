
import sys
import fitz  # PyMuPDF
import os
import json
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QFileDialog, 
                             QDoubleSpinBox, QGroupBox, QTabWidget, 
                             QScrollArea, QMessageBox, QSplitter, QProgressBar,
                             QInputDialog, QCheckBox)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QPixmap, QImage, QPainter, QAction, QPen

class AutoScrollArea(QScrollArea):
    """Ctrl + 휠 줌 기능을 위한 커스텀 스크롤 영역"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.editor = None  # 부모 에디터 참조

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.editor.zoom_in()
            else:
                self.editor.zoom_out()
        else:
            super().wheelEvent(event)

class PDFEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF 여백 편집기 1.0")
        self.setGeometry(100, 100, 1200, 850)

        # 상태 변수
        self.doc = None
        self.current_page_num = 0
        self.scale_factor = 1.0
        self.compression_level = 0
        self.settings_file = "pdf_editor_settings.json"
        
        # 기본 설정값
        self.settings = {
            'odd': {'left': 0.0, 'right': 0.0, 'top': 0.0, 'bottom': 0.0},
            'even': {'left': 0.0, 'right': 0.0, 'top': 0.0, 'bottom': 0.0}
        }
        
        # 프리셋 데이터 (이름: 설정값)
        self.presets = {}

        self.init_ui()
        self.load_settings() # 자동 불러오기
        print("SYSTEM: PDF Editor Initialized. 1.0 Active.")

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)

        # 스플리터 생성
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # --- 좌측: 미리보기 영역 ---
        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        
        # 상단 툴바 (줌, 페이지 이동)
        toolbar_layout = QHBoxLayout()
        
        self.btn_prev = QPushButton("◀ 이전")
        self.btn_prev.clicked.connect(self.prev_page)
        self.lbl_page = QLabel("0 / 0")
        self.lbl_page.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_next = QPushButton("다음 ▶")
        self.btn_next.clicked.connect(self.next_page)
        
        self.btn_zoom_out = QPushButton("축소 (-)")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        self.lbl_zoom = QLabel("100%")
        self.btn_zoom_in = QPushButton("확대 (+)")
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        toolbar_layout.addWidget(self.btn_prev)
        toolbar_layout.addWidget(self.lbl_page)
        toolbar_layout.addWidget(self.btn_next)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.btn_zoom_out)
        toolbar_layout.addWidget(self.lbl_zoom)
        toolbar_layout.addWidget(self.btn_zoom_in)
        
        preview_layout.addLayout(toolbar_layout)

        # 스크롤 영역
        self.scroll_area = AutoScrollArea()
        self.scroll_area.editor = self
        self.scroll_area.setWidgetResizable(True)
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scroll_area.setWidget(self.image_label)
        preview_layout.addWidget(self.scroll_area)

        # 하단 진행바 (좌측 영역에 배치)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        preview_layout.addWidget(self.progress_bar)

        splitter.addWidget(preview_container)

        # --- 우측: 설정 패널 ---
        settings_panel = QWidget()
        settings_layout = QVBoxLayout(settings_panel)
        settings_panel.setMinimumWidth(340)

        # 파일 열기/저장
        btn_layout = QHBoxLayout()
        btn_open = QPushButton("📂 파일 열기")
        btn_open.clicked.connect(self.open_pdf)
        btn_save = QPushButton("💾 저장 하기")
        btn_save.clicked.connect(self.save_pdf)
        btn_save.setStyleSheet("background-color: #e1f5fe; font-weight: bold;")
        btn_layout.addWidget(btn_open)
        btn_layout.addWidget(btn_save)
        settings_layout.addLayout(btn_layout)

        # 프리셋 관리
        preset_group = QGroupBox("프리셋 설정")
        preset_layout = QHBoxLayout()
        btn_load_preset = QPushButton("불러오기")
        btn_load_preset.clicked.connect(self.load_preset_dialog)
        btn_save_preset = QPushButton("현재값 저장")
        btn_save_preset.clicked.connect(self.save_preset_dialog)
        btn_reset = QPushButton("초기화")
        btn_reset.clicked.connect(self.reset_settings)
        
        preset_layout.addWidget(btn_load_preset)
        preset_layout.addWidget(btn_save_preset)
        preset_layout.addWidget(btn_reset)
        preset_group.setLayout(preset_layout)
        settings_layout.addWidget(preset_group)

        # 압축 옵션
        comp_group = QGroupBox("저장 옵션")
        comp_layout = QVBoxLayout()
        h_comp = QHBoxLayout()
        h_comp.addWidget(QLabel("압축 수준:"))
        
        self.spin_comp = QDoubleSpinBox()
        self.spin_comp.setRange(0, 100)
        self.spin_comp.setSingleStep(10)
        self.spin_comp.setSuffix("%")
        self.spin_comp.setValue(0)
        self.spin_comp.valueChanged.connect(self.update_comp_label)
        h_comp.addWidget(self.spin_comp)
        comp_layout.addLayout(h_comp)
        
        self.lbl_comp_status = QLabel("설명: 원본 품질 유지 (빠름)")
        self.lbl_comp_status.setStyleSheet("color: gray; font-size: 11px;")
        comp_layout.addWidget(self.lbl_comp_status)
        
        # 파일 정보 표시
        self.lbl_file_info = QLabel("원본파일 크기: -")
        self.lbl_file_info.setStyleSheet("font-weight: bold;")
        comp_layout.addWidget(self.lbl_file_info)
        
        comp_group.setLayout(comp_layout)
        settings_layout.addWidget(comp_group)

        # 홀수/짝수 동일 적용 체크박스 (위치 변경됨)
        self.check_sync = QCheckBox("홀수/짝수 동일 적용")
        self.check_sync.setStyleSheet("font-weight: bold; color: #2c3e50; margin: 10px 0px 5px 2px;")
        self.check_sync.stateChanged.connect(self.sync_all_settings)
        settings_layout.addWidget(self.check_sync)

        # 탭 (홀수/짝수)
        self.tabs = QTabWidget()
        self.odd_tab = self.create_page_settings_tab('odd')
        self.even_tab = self.create_page_settings_tab('even')
        self.tabs.addTab(self.odd_tab, "홀수 페이지")
        self.tabs.addTab(self.even_tab, "짝수 페이지")
        settings_layout.addWidget(self.tabs)
        
        self.tabs.currentChanged.connect(self.update_preview)

        # 안내
        info_box = QGroupBox("도움말")
        info_layout = QVBoxLayout()
        info_label = QLabel(
            "1. 양수(+) 입력: 여백 추가\n"
            "2. 음수(-) 입력: 여백 자름\n"
            "3. 압축 설정 시 시간이 좀 걸릴 수 있습니다."
        )
        info_layout.addWidget(info_label)
        info_box.setLayout(info_layout)
        settings_layout.addWidget(info_box)
        settings_layout.addStretch()
        
        splitter.addWidget(settings_panel)
        splitter.setSizes([850, 350])

        # 초기 비활성화
        self.btn_prev.setEnabled(False)
        self.btn_next.setEnabled(False)

    def create_page_settings_tab(self, page_type):
        tab = QWidget()
        layout = QVBoxLayout()
        group = QGroupBox(f"{'홀수' if page_type == 'odd' else '짝수'} 페이지 여백 (mm)")
        grid = QVBoxLayout()

        def create_input(label_text, key):
            h = QHBoxLayout()
            lbl = QLabel(label_text)
            spin = QDoubleSpinBox()
            spin.setRange(-500.0, 500.0)
            spin.setSingleStep(1.0)
            spin.setSuffix(" mm")
            spin.setValue(0.0)
            spin.valueChanged.connect(lambda v: self.update_setting(page_type, key, v))
            h.addWidget(lbl)
            h.addWidget(spin)
            grid.addLayout(h)
            return spin

        self.inputs = getattr(self, 'inputs', {})
        self.inputs[f'{page_type}_top'] = create_input("상단 (Top):", 'top')
        self.inputs[f'{page_type}_bottom'] = create_input("하단 (Bottom):", 'bottom')
        self.inputs[f'{page_type}_left'] = create_input("좌측 (Left):", 'left')
        self.inputs[f'{page_type}_right'] = create_input("우측 (Right):", 'right')

        group.setLayout(grid)
        layout.addWidget(group)
        layout.addStretch()
        tab.setLayout(layout)
        return tab

    def update_setting(self, page_type, key, value):
        self.settings[page_type][key] = value
        
        # 동일 적용 체크되어 있으면 반대편도 업데이트
        if self.check_sync.isChecked():
            other_type = 'even' if page_type == 'odd' else 'odd'
            self.settings[other_type][key] = value
            # UI 입력칸도 업데이트 (재귀 호출 방지를 위해 signals blocked 필요할 수도 있지만, 
            # valueChanged는 값이 다를 때만 발생하므로 직접 set 가능)
            self.inputs[f'{other_type}_{key}'].blockSignals(True)
            self.inputs[f'{other_type}_{key}'].setValue(value)
            self.inputs[f'{other_type}_{key}'].blockSignals(False)
            
        self.update_preview()

    def sync_all_settings(self, state):
        if state == Qt.CheckState.Checked.value:
            # 현재 선택된 탭의 설정을 기준으로 반대편 동기화
            idx = self.tabs.currentIndex()
            src_type = 'odd' if idx == 0 else 'even'
            target_type = 'even' if idx == 0 else 'odd'
            
            for key in ['left', 'right', 'top', 'bottom']:
                val = self.settings[src_type][key]
                self.settings[target_type][key] = val
                self.inputs[f'{target_type}_{key}'].blockSignals(True)
                self.inputs[f'{target_type}_{key}'].setValue(val)
                self.inputs[f'{target_type}_{key}'].blockSignals(False)
            
            self.update_preview()

    def reset_settings(self):
        # 모든 입력값을 0으로 초기화
        for key, spin in self.inputs.items():
            spin.setValue(0.0)
        self.update_preview()
        QMessageBox.information(self, "알림", "모든 설정이 초기화되었습니다.")

    def update_comp_label(self, value):
        if value == 0:
            msg = "설명: 원본 품질 유지 (빠름)"
        else:
            quality = int(100 - value * 0.9)
            msg = f"설명: 이미지 재압축 (품질 {quality}%) - 시간이 소요됨"
        self.lbl_comp_status.setText(msg)

    def zoom_in(self):
        self.scale_factor *= 1.1
        self.update_zoom_label()
        self.update_preview()

    def zoom_out(self):
        self.scale_factor /= 1.1
        self.update_zoom_label()
        self.update_preview()

    def update_zoom_label(self):
        self.lbl_zoom.setText(f"{int(self.scale_factor * 100)}%")

    def open_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, "PDF 열기", "", "PDF Files (*.pdf)")
        if path:
            try:
                self.doc = fitz.open(path)
                self.current_page_num = 0
                
                size_mb = os.path.getsize(path) / (1024 * 1024)
                self.lbl_file_info.setText(f"원본파일 크기: {size_mb:.2f} MB")
                
                print(f"DEBUG: File Opened: {path}, Pages: {len(self.doc)}")
                self.update_ui_state()
                self.update_preview()
            except Exception as e:
                print(f"ERROR: Open Failed: {e}")
                QMessageBox.critical(self, "에러", f"파일 열기 실패: {e}")

    def update_ui_state(self):
        if self.doc:
            total = len(self.doc)
            cur = self.current_page_num + 1
            is_even = (cur % 2 == 0)
            self.lbl_page.setText(f"{cur} / {total} ({'짝수' if is_even else '홀수'})")
            
            self.btn_prev.setEnabled(self.current_page_num > 0)
            self.btn_next.setEnabled(self.current_page_num < total - 1)
            
            self.tabs.setCurrentIndex(1 if is_even else 0)

    def prev_page(self):
        if self.current_page_num > 0:
            self.current_page_num -= 1
            self.update_ui_state()
            self.update_preview()

    def next_page(self):
        if self.doc and self.current_page_num < len(self.doc) - 1:
            self.current_page_num += 1
            self.update_ui_state()
            self.update_preview()

    def update_preview(self):
        if not self.doc:
            return

        try:
            page = self.doc.load_page(self.current_page_num)
            
            # 원본 렌더링
            zoom_matrix = fitz.Matrix(2.0, 2.0)
            pix = page.get_pixmap(matrix=zoom_matrix)
            
            fmt = QImage.Format.Format_RGBA8888 if pix.alpha else QImage.Format.Format_RGB888
            orig_qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            orig_pixmap = QPixmap.fromImage(orig_qimg)
            
            cur = self.current_page_num + 1
            is_even = (cur % 2 == 0)
            setting = self.settings['even'] if is_even else self.settings['odd']

            mm_to_px = (72 / 25.4) * 2.0

            left_px = int(setting['left'] * mm_to_px)
            right_px = int(setting['right'] * mm_to_px)
            top_px = int(setting['top'] * mm_to_px)
            bottom_px = int(setting['bottom'] * mm_to_px)

            orig_w = orig_pixmap.width()
            orig_h = orig_pixmap.height()

            final_w = orig_w + left_px + right_px
            final_h = orig_h + top_px + bottom_px
            final_w = max(10, final_w)
            final_h = max(10, final_h)

            final_pixmap = QPixmap(final_w, final_h)
            final_pixmap.fill(Qt.GlobalColor.white)
            
            painter = QPainter(final_pixmap)
            painter.drawPixmap(left_px, top_px, orig_pixmap)
            
            pen = QPen(Qt.GlobalColor.red)
            pen.setWidth(2)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            painter.drawRect(left_px, top_px, orig_w, orig_h)
            painter.end()

            scaled_w = int(final_w * self.scale_factor * 0.5)
            scaled_h = int(final_h * self.scale_factor * 0.5)
            
            if scaled_w > 0 and scaled_h > 0:
                display_pixmap = final_pixmap.scaled(
                    scaled_w, scaled_h,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(display_pixmap)
            
        except Exception as e:
            print(f"ERROR: Preview Failed: {e}")

    def save_pdf(self):
        if not self.doc:
            return

        path, _ = QFileDialog.getSaveFileName(self, "저장", "", "PDF Files (*.pdf)")
        if not path:
            return

        try:
            print(f"DEBUG: Saving to {path}...")
            # UI 초기화
            self.progress_bar.setValue(0)
            self.btn_next.setEnabled(False) # 저장 중 조작 방지
            
            new_doc = fitz.open()
            
            compression = int(self.spin_comp.value())
            jpg_quality = int(100 - compression * 0.9) 
            do_compress = compression > 0
            
            dpi = max(72, int(150 - compression * 0.5))
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)

            total_pages = len(self.doc)
            
            for i, page in enumerate(self.doc):
                # 진행률 업데이트
                progress = int((i + 1) / total_pages * 100)
                self.progress_bar.setValue(progress)
                QApplication.processEvents()

                cur = i + 1
                is_even = (cur % 2 == 0)
                setting = self.settings['even'] if is_even else self.settings['odd']
                
                mm_to_pt = 72 / 25.4
                left = setting['left'] * mm_to_pt
                right = setting['right'] * mm_to_pt
                top = setting['top'] * mm_to_pt
                bottom = setting['bottom'] * mm_to_pt
                
                src_rect = page.rect
                
                new_width = src_rect.width + left + right
                new_height = src_rect.height + top + bottom
                new_width = max(10, new_width)
                new_height = max(10, new_height)

                new_page = new_doc.new_page(width=new_width, height=new_height)
                target_rect = fitz.Rect(left, top, left + src_rect.width, top + src_rect.height)
                
                if do_compress:
                    pix = page.get_pixmap(matrix=matrix)
                    img_data = pix.tobytes("jpg", jpg_quality=jpg_quality)
                    new_page.insert_image(target_rect, stream=img_data)
                else:
                    new_page.show_pdf_page(target_rect, self.doc, i)
            
            # 저장
            if do_compress:
                new_doc.save(path, garbage=4, deflate=True)
            else:
                new_doc.save(path)
            
            new_doc.close()
            
            # 후처리
            self.progress_bar.setValue(100)
            self.btn_next.setEnabled(True)
            self.update_ui_state() # 버튼 상태 복구

            saved_size = os.path.getsize(path) / (1024 * 1024)
            QMessageBox.information(self, "성공", f"저장이 완료되었습니다.\n저장된 크기: {saved_size:.2f} MB")

        except Exception as e:
            self.btn_next.setEnabled(True)
            print(f"\nERROR: Save Failed: {e}")
            QMessageBox.critical(self, "실패", f"저장 중 오류가 발생했습니다.\n{e}")

    # --- 설정 관리 (JSON) ---
    def load_settings(self):
        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # 최근 값 로드
                    if 'last_settings' in data:
                        last = data['last_settings']
                        for p_type in ['odd', 'even']:
                            for key in ['left', 'right', 'top', 'bottom']:
                                val = last.get(p_type, {}).get(key, 0.0)
                                self.inputs[f'{p_type}_{key}'].setValue(val)
                    
                    # 프리셋 로드
                    if 'presets' in data:
                        self.presets = data['presets']

            except Exception as e:
                print(f"설정 불러오기 실패: {e}")

    def save_settings_to_file(self):
        # 현재 값과 프리셋을 저장
        data = {
            'last_settings': self.settings,
            'presets': self.presets
        }
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"설정 저장 실패: {e}")

    def closeEvent(self, event):
        # 프로그램 종료 시 자동 저장
        self.save_settings_to_file()
        event.accept()

    def save_preset_dialog(self):
        name, ok = QInputDialog.getText(self, "프리셋 저장", "프리셋 이름:")
        if ok and name:
            # 현재 설정값을 깊은 복사로 저장
            import copy
            self.presets[name] = copy.deepcopy(self.settings)
            self.save_settings_to_file()
            QMessageBox.information(self, "완료", f"'{name}' 프리셋이 저장되었습니다.")

    def load_preset_dialog(self):
        if not self.presets:
            QMessageBox.information(self, "알림", "저장된 프리셋이 없습니다.")
            return

        items = list(self.presets.keys())
        name, ok = QInputDialog.getItem(self, "프리셋 불러오기", "프리셋 선택:", items, 0, False)
        if ok and name:
            data = self.presets[name]
            # UI 업데이트 (설정값 반영)
            for p_type in ['odd', 'even']:
                for key in ['left', 'right', 'top', 'bottom']:
                    val = data.get(p_type, {}).get(key, 0.0)
                    self.inputs[f'{p_type}_{key}'].setValue(val)
            QMessageBox.information(self, "완료", f"'{name}' 설정이 적용되었습니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = PDFEditor()
    editor.show()
    sys.exit(app.exec())
