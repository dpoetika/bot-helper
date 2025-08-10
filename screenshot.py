from PySide6.QtWidgets import QApplication, QWidget, QRubberBand
from PySide6.QtCore import Qt, QRect, QPoint, QSize, QEventLoop, Signal
from PySide6.QtGui import QGuiApplication, QPainter, QColor
import pyautogui

class SelectionOverlay(QWidget):
    finished = Signal()
    def __init__(self) -> None:
        super().__init__()
        # Tüm ekranları kaplayan şeffaf, üstte kalan bir pencere oluştur
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        QApplication.setOverrideCursor(Qt.CrossCursor)

        # Tüm sanal masaüstünü kapla (çoklu monitör desteği)
        virtual_geom = QGuiApplication.primaryScreen().virtualGeometry()
        self.setGeometry(virtual_geom)

        self.origin_local: QPoint | None = None
        self.origin_global: QPoint | None = None
        self.rubber_band = QRubberBand(QRubberBand.Rectangle, self)
        # Belirgin görünüm için kenarlık ve yarı saydam dolgu
        self.rubber_band.setStyleSheet(
            "border: 2px solid #00aaff; background-color: rgba(0, 170, 255, 60);"
        )

        self.result: list[int] | None = None

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            # Qt6: pos() deprecated → position() / globalPosition()
            self.origin_local = event.position().toPoint()
            self.origin_global = event.globalPosition().toPoint()
            self.rubber_band.setGeometry(QRect(self.origin_local, QSize()))
            self.rubber_band.show()
            self.grabMouse()

    def mouseMoveEvent(self, event) -> None:
        if self.origin_local is None:
            return
        current_local = event.position().toPoint()
        rect = QRect(self.origin_local, current_local).normalized()
        self.rubber_band.setGeometry(rect)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self.origin_local is not None and self.origin_global is not None:
            # Global koordinatları Qt6 API ile al
            start_global = self.origin_global
            end_global = event.globalPosition().toPoint()
            self.result = [
                start_global.x(),
                start_global.y(),
                end_global.x(),
                end_global.y(),
            ]
            self.rubber_band.hide()
            QApplication.restoreOverrideCursor()
            self.releaseMouse()
            self.hide()
            self.finished.emit()

    def keyPressEvent(self, event) -> None:
        # ESC ile iptal
        if event.key() == Qt.Key_Escape:
            self.result = None
            QApplication.restoreOverrideCursor()
            self.hide()
            self.finished.emit()

    def paintEvent(self, event) -> None:
        # Arka planı hafif karartarak overlay'in görünür olduğundan emin ol
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 60))


def select_region() -> list[int] | None:
    # Var olan bir QApplication varsa onu kullan, yoksa oluştur
    app = QApplication.instance() or QApplication([])
    overlay = SelectionOverlay()
    overlay.showFullScreen()
    overlay.raise_()
    overlay.activateWindow()

    # Lokal event loop ile yalnızca bu seçim tamamlanana kadar bekle
    loop = QEventLoop()
    overlay.finished.connect(loop.quit)
    loop.exec()

    # Eğer seçim iptal edildiyse None döndür
    if not overlay.result:
        return None

    x1, y1, x2, y2 = overlay.result
    left = min(x1, x2)
    top = min(y1, y2)
    width = abs(x2 - x1)
    height = abs(y2 - y1)

    # Genişlik/ yükseklik 0 ise en az 1 piksel yap
    width = max(1, width)
    height = max(1, height)

    return [left, top, width, height]


if __name__ == "__main__":
    region = select_region()
    if region:
        pyautogui.screenshot(region=tuple(region)).save("screenshot.png")
        print(region)
    else:
        print(None)


