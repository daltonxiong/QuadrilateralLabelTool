import logging
import sqlite3
import time
from pathlib import Path
import sys

import numpy as np
if sys.platform == 'win32':
    import numpy.core._dtype_ctypes #don't remove this line, pyinstaller need this
from PySide2 import QtCore
from PySide2 import QtGui
from PySide2 import QtWidgets
from PySide2.QtCore import QPoint
from PySide2.QtCore import QRect
from PySide2.QtCore import QRectF
from PySide2.QtCore import QSize
from PySide2.QtCore import Qt
from PySide2.QtGui import QColor
from PySide2.QtGui import QFont
from PySide2.QtGui import QIntValidator
from PySide2.QtGui import QKeySequence
from PySide2.QtGui import QMatrix
from PySide2.QtGui import QPainter
from PySide2.QtGui import QPen
from PySide2.QtWidgets import QCheckBox
from PySide2.QtWidgets import QComboBox
from PySide2.QtWidgets import QDesktopWidget
from PySide2.QtWidgets import QFileDialog
from PySide2.QtWidgets import QFrame
from PySide2.QtWidgets import QHBoxLayout
from PySide2.QtWidgets import QLabel
from PySide2.QtWidgets import QLineEdit
from PySide2.QtWidgets import QMessageBox
from PySide2.QtWidgets import QPushButton
from PySide2.QtWidgets import QShortcut
from PySide2.QtWidgets import QVBoxLayout

def order_points(point_list):
    point_list = sorted(point_list, key=lambda x: x[0])
    a1 = sorted([*point_list[:2]], key=lambda x: x[1])
    a2 = sorted([*point_list[2:]], key=lambda x: x[1])
    return np.array([a1[0], a2[0], a2[1], a1[1]], np.int)

class LabelData:
    def __init__(self, lable_data_path):
        self.conn = sqlite3.connect(lable_data_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute(r'''
        CREATE TABLE IF NOT EXISTS label (
            img_name text PRIMARY KEY,
            valid INTEGER NOT NULL,
            x1 INTEGER NOT NULL,
            y1 INTEGER NOT NULL,
            x2 INTEGER NOT NULL,
            y2 INTEGER NOT NULL,
            x3 INTEGER NOT NULL,
            y3 INTEGER NOT NULL,
            x4 INTEGER NOT NULL,
            y4 INTEGER NOT NULL,
            tsp INTEGER NOT NULL
        );
    ''')

    def get_label(self, img_name, name_list):
        db_key_list = ['valid',
                       'point_list']

        key_list = []
        for name in name_list:
            if name not in db_key_list:
                raise ValueError(f'数据库中没有这个字段<{name}>')

            if name == 'point_list':
                key_list.extend(['x1', 'y1', 'x2', 'y2', 'x3', 'y3', 'x4', 'y4'])
            else:
                key_list.append(name)

        label_result = self.cursor.execute(f'''
        SELECT {','.join(key_list)}
        FROM label
        WHERE img_name = ?
        ''', (img_name,)).fetchone()

        if label_result is None:
            return None

        idx = 0
        value_list = []
        for name in name_list:
            if name == 'point_list':
                value_list.append(
                    np.array(label_result[idx:idx+8], dtype=np.int).reshape(4, 2))
                idx += 8
            else:
                value_list.append(label_result[idx])
                idx += 1

        return value_list

    def set_label(self, img_name, **kwargs):
        valid = kwargs.get('valid', None)
        point_list = kwargs.get('point_list', None)

        key_list = []
        value_list = []
        if valid is not None:
            key_list.append('valid')
            value_list.append(valid)

        if point_list is not None:
            key_list.extend(['x1', 'y1', 'x2', 'y2', 'x3', 'y3', 'x4', 'y4'])
            value_list.extend(point_list.flatten().tolist())

        if not len(key_list):
            return

        if len(key_list) < 9:
            set_list = [f'{x}=?' for x in key_list]
            self.cursor.execute(f'''
            UPDATE label
            SET {','.join(set_list)}, tsp=?
            WHERE img_name=?
            ''', (*value_list, int(time.time()), img_name))
        else:
            self.cursor.execute(f'''
            INSERT INTO 
            label (img_name,{','.join([x for x in key_list])},tsp)
            VALUES (?,{','.join(['?' for x in key_list])},?);
            ''', (img_name, *value_list, int(time.time())))
        self.conn.commit()

    def get_label_all(self, img_name):
        label_result = self.cursor.execute(r'''
        SELECT valid,x1,y1,x2,y2,x3,y3,x4,y4
        FROM label
        WHERE img_name = ?
        ''', (img_name,)).fetchone()
        if label_result:
            valid = label_result[0]
            point_list = np.array(label_result[1:9], dtype=np.int).reshape(4, 2)
            return valid, point_list
        else:
            return None

    def __del__(self):
        self.conn.close()

class DragButton(QtWidgets.QToolButton):
    def __init__(self, parent=None):
        super(DragButton, self).__init__(parent)
        self.setStyleSheet('''
            background-color: red;
        ''')

        self.setFixedSize(10, 10)
        self.border_size = self.parent().size()

    def mousePressEvent(self, event):
        self.setStyleSheet('''
            background-color: yellow;
        ''')
        self.__mousePressPos = None
        self.__mouseMovePos = None
        if event.button() == QtCore.Qt.LeftButton:
            self.__mousePressPos = event.globalPos()
            self.__mouseMovePos = event.globalPos()
        super(DragButton, self).mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() == QtCore.Qt.LeftButton:
            currPos = self.mapToGlobal(self.pos())
            globalPos = event.globalPos()
            diff = globalPos - self.__mouseMovePos
            newPos = self.mapFromGlobal(currPos + diff)

            center_point = [newPos.x() + self.width() / 2,
                            newPos.y() + self.height() / 2]
            if center_point[0] > self.border_size.width()-10:
                center_point[0] = self.border_size.width()-10
            if center_point[0] < 10:
                center_point[0] = 10

            if center_point[1] > self.border_size.height()-10:
                center_point[1] = self.border_size.height()-10
            if center_point[1] < 10:
                center_point[1] = 10

            self.move(QPoint(
                center_point[0] - self.width() / 2,
                center_point[1] - self.height() / 2
            ))
            self.__mouseMovePos = globalPos
            self.parent().update_img_value()

        super(DragButton, self).mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self.setStyleSheet('''
            background-color: red;
        ''')
        if self.__mousePressPos is not None:
            moved = event.globalPos() - self.__mousePressPos
            if moved.manhattanLength() > 3:
                event.ignore()
                return
        super(DragButton, self).mouseReleaseEvent(event)

    def resizeEvent(self, event):
        self.setMask(QtGui.QRegion(self.rect(), QtGui.QRegion.Ellipse))
        QtWidgets.QToolButton.resizeEvent(self, event)

class ImageLabel(QLabel):
    def __init__(self, parent=None):
        super(ImageLabel, self).__init__(parent)

        self.btn_point1 = DragButton(self)
        self.btn_point2 = DragButton(self)
        self.btn_point3 = DragButton(self)
        self.btn_point4 = DragButton(self)

        self.btn_point1.setVisible(False)
        self.btn_point2.setVisible(False)
        self.btn_point3.setVisible(False)
        self.btn_point4.setVisible(False)

        self.scaled_img = None
        self.scaled_img_valid = 1
        self.scaled_ratio = None
        self.img_rect = None

        self.img_extra_border_size = (50, 50)

    def set_new_image(self, img, valid, point_list):
        self.scaled_img = None
        self.scaled_img_valid = valid
        self.scaled_ratio = None
        self.img_rect = None

        if img:
            scaled_size = QSize(
                self.size().width()-self.img_extra_border_size[1]*2,
                self.size().height()-self.img_extra_border_size[0]*2
            )
            self.scaled_img = img.scaled(scaled_size, Qt.KeepAspectRatio)

            self.btn_point1.border_size = self.size()
            self.btn_point2.border_size = self.size()
            self.btn_point3.border_size = self.size()
            self.btn_point4.border_size = self.size()

            self.scaled_ratio = self.scaled_img.width() / img.width()
            self.img_rect = QRect(
                self.img_extra_border_size[0],
                self.img_extra_border_size[1],
                self.scaled_img.width(),
                self.scaled_img.height()
            )

            point_list = point_list.astype(np.float)
            point_list *= self.scaled_ratio
            point_list = point_list.astype(np.int)

            point_list -= self.btn_point1.width() // 2
            point_list[:, 0] += self.img_extra_border_size[1]
            point_list[:, 1] += self.img_extra_border_size[0]
            for p in point_list:
                if p[0] < 10:
                    p[0] = 10
                elif p[0] > self.size().width()-10:
                    p[0] = self.size().width()-10

                if p[1] < 10:
                    p[1] = 10
                elif p[1] > self.size().height()-10:
                    p[1] = self.size().height()-10

            self.btn_point1.move(QPoint(point_list[0, 0], point_list[0, 1]))
            self.btn_point2.move(QPoint(point_list[1, 0], point_list[1, 1]))
            self.btn_point3.move(QPoint(point_list[2, 0], point_list[2, 1]))
            self.btn_point4.move(QPoint(point_list[3, 0], point_list[3, 1]))

            self.btn_point1.setVisible(True)
            self.btn_point2.setVisible(True)
            self.btn_point3.setVisible(True)
            self.btn_point4.setVisible(True)

        if not self.scaled_img or not self.scaled_img_valid:
            self.btn_point1.setVisible(False)
            self.btn_point2.setVisible(False)
            self.btn_point3.setVisible(False)
            self.btn_point4.setVisible(False)

        self.repaint()

    def update_img_value(self):
        if not self.scaled_img:
            return None

        pos1 = self.btn_point1.pos()
        pos2 = self.btn_point2.pos()
        pos3 = self.btn_point3.pos()
        pos4 = self.btn_point4.pos()

        point_list = np.array([(pos1.x(), pos1.y()),
                               (pos2.x(), pos2.y()),
                               (pos3.x(), pos3.y()),
                               (pos4.x(), pos4.y())])
        point_list[:, 0] -= self.img_extra_border_size[1]
        point_list[:, 1] -= self.img_extra_border_size[0]
        point_list += self.btn_point1.width() // 2
        point_list = point_list.astype(np.float)
        point_list /= self.scaled_ratio
        point_list = point_list.astype(np.int)
        point_list += 1

        self.parent().update_img_point_list(point_list)
        self.repaint()

    def paintEvent(self, event):
        pos1 = self.btn_point1.pos()
        pos2 = self.btn_point2.pos()
        pos3 = self.btn_point3.pos()
        pos4 = self.btn_point4.pos()

        point_list = np.array([
            (pos1.x(), pos1.y()),
            (pos2.x(), pos2.y()),
            (pos3.x(), pos3.y()),
            (pos4.x(), pos4.y())
        ]) + self.btn_point4.width() / 2
        point_list = order_points(point_list)

        painter = QPainter()
        painter.begin(self)
        painter.setPen(Qt.NoPen)
        painter.fillRect(self.rect(), QColor(190, 190, 190, 255))

        if self.scaled_img:
            painter.drawPixmap(self.img_rect, self.scaled_img)

            if self.scaled_img_valid != 0:
                painter.setPen(QPen(Qt.green, 1))
                painter.drawLine(
                    point_list[0, 0],
                    point_list[0, 1],
                    point_list[1, 0],
                    point_list[1, 1]
                )
                painter.drawLine(
                    point_list[1, 0],
                    point_list[1, 1],
                    point_list[2, 0],
                    point_list[2, 1]
                )
                painter.drawLine(
                    point_list[2, 0],
                    point_list[2, 1],
                    point_list[3, 0],
                    point_list[3, 1]
                )
                painter.drawLine(
                    point_list[3, 0],
                    point_list[3, 1],
                    point_list[0, 0],
                    point_list[0, 1]
                )
            else:
                painter.setFont(QFont('宋体', 100, QFont.Black, True))
                painter.setPen(QPen(Qt.red))
                painter.drawText(
                    QRectF(0.0, 0.0, self.scaled_img.width(), self.scaled_img.height()),
                    Qt.AlignCenter | Qt.AlignTop,
                    "已作废"
                )

        painter.end()

class MainWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        QtWidgets.QWidget.__init__(self, parent)

        self.setWindowTitle('四边形物体标注工具')
        self.setFixedSize(1024, 800)
        self.move_to_center()

        self.label_img = ImageLabel(self)
        self.label_img.setAlignment(Qt.AlignCenter)
        self.label_img.setText('没有选择任何图片')
        self.label_img.setFixedHeight(700)

        self.btn_open_dir = QPushButton(self)
        self.btn_open_dir.setText('选择目录...')
        self.btn_open_dir.clicked.connect(self.select_diectory)

        self.btn_valid_img = QPushButton(self)
        self.btn_valid_img.setText('作废')
        self.btn_valid_img.clicked.connect(self.on_valid_img)

        self.btn_prev_img = QPushButton(self)
        self.btn_prev_img.setText('上一张')
        self.btn_prev_img.clicked.connect(self.on_prev_img)
        self.connect(QShortcut(QKeySequence(QtCore.Qt.Key_Left), self), QtCore.SIGNAL('activated()'), self.btn_prev_img.click)

        self.btn_next_img = QPushButton(self)
        self.btn_next_img.setText('下一张')
        self.btn_next_img.clicked.connect(self.on_next_img)
        self.connect(QShortcut(QKeySequence(Qt.Key_Right), self), QtCore.SIGNAL('activated()'), self.btn_next_img.click)

        self.label_status = QLabel(self)
        self.label_status.setFont(QFont('宋体', 22))
        self.label_status.setAlignment(Qt.AlignLeft)
        self.label_status.setText('请选择需要标注的目录')

        layout_root = QVBoxLayout(self)
        layout_row1 = QHBoxLayout(self)
        layout_row2 = QVBoxLayout(self)
        layout_row2_row1 = QHBoxLayout(self)
        layout_row2_row2 = QHBoxLayout(self)

        layout_row1.addWidget(self.label_img)
        layout_row2_row1.addWidget(self.label_status)
        layout_row2_row2.addWidget(self.btn_open_dir)
        layout_row2_row2.addWidget(self.btn_valid_img)
        layout_row2_row2.addWidget(self.btn_prev_img)
        layout_row2_row2.addWidget(self.btn_next_img)

        layout_row2.addLayout(layout_row2_row1)
        layout_row2.addLayout(layout_row2_row2)

        layout_root.addLayout(layout_row1)
        layout_root.addLayout(layout_row2)

        self.setLayout(layout_root)

        self.directory = None
        self.all_img_file = []
        self.all_img_file_index = 0
        self.db_label_data = None

        self.update_btn_status()

    def move_to_center(self):
        screen = QDesktopWidget().screenGeometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) / 2, (screen.height() - size.height()) / 2)

    def update_btn_status(self):
        try:
            self.btn_valid_img.setEnabled(False)
            self.btn_prev_img.setEnabled(False)
            self.btn_next_img.setEnabled(False)

            if not self.all_img_file:
                self.label_status.setText('请选择需要标注的目录')
            else:
                img_name = self.all_img_file[self.all_img_file_index]

                valid, = self.db_label_data.get_label(img_name, ['valid'])
                if valid:
                    self.btn_valid_img.setText('作废')
                else:
                    self.btn_valid_img.setText('取消作废')

                if self.all_img_file_index == 0:
                    self.btn_prev_img.setEnabled(False)
                else:
                    self.btn_prev_img.setEnabled(True)

                if self.all_img_file_index == len(self.all_img_file) - 1:
                    self.btn_next_img.setEnabled(False)
                else:
                    self.btn_next_img.setEnabled(True)

                self.btn_valid_img.setEnabled(True)
                self.label_status.setText(f'{self.all_img_file_index+1}/{len(self.all_img_file)} {img_name}')
        except:
            logging.exception('update_btn_status exception')

    def select_diectory(self):
        try:
            self.all_img_file = []
            self.all_img_file_index = 0
            self.db_label_data = None
            self.label_img.set_new_image(None, 0, None)

            self.directory = QFileDialog.getExistingDirectory(self, '选择目录')
            self.setWindowTitle(f'四边形物体标注工具: {self.directory}')

            self.get_all_img_file()
            if len(self.all_img_file) <= 0:
                QMessageBox.information(self, '<提示>', f'{self.directory}\n目录下没有找到图片文件', QMessageBox.Ok)
                return

            self.read_label_file()
            self.show_img()
        finally:
            self.update_btn_status()

    def get_all_img_file(self):
        self.all_img_file_index = 0
        self.all_img_file = sorted([str(x.name) for x in Path(self.directory).iterdir() if x.is_file() and x.suffix.upper() in ['.JPG', '.JPEG', '.BMP', '.PNG']])

    def read_label_file(self):
        label_file = Path(self.directory).joinpath('label.sqllite3')
        self.db_label_data = LabelData(str(label_file))

    def on_next_img(self):
        try:
            self.all_img_file_index += 1
            self.show_img()
        finally:
            self.update_btn_status()

    def on_prev_img(self):
        try:
            self.all_img_file_index -= 1
            self.show_img()
        finally:
            self.update_btn_status()

    def on_valid_img(self):
        try:
            img_name = self.all_img_file[self.all_img_file_index]
            if self.btn_valid_img.text() == '作废':
                self.db_label_data.set_label(img_name, valid=0)
            else:
                self.db_label_data.set_label(img_name, valid=1)
            self.show_img()
        finally:
            self.update_btn_status()

    def show_img(self):
        img_name = self.all_img_file[self.all_img_file_index]
        img_path = Path(self.directory).joinpath(img_name)
        db_value = self.db_label_data.get_label(img_name, ['valid', 'point_list'])
        img = QtGui.QPixmap(str(img_path))

        if db_value is None:
            valid = 1
            point_list = np.array([(50, 50),
                                   (img.width() - 50, 50),
                                   (img.width() - 50, img.height() - 50),
                                   (50, img.height() - 50)
                                   ])

            self.db_label_data.set_label(img_name,
                                         valid=1,
                                         point_list=point_list)
        else:
            valid, point_list = db_value

        self.label_img.set_new_image(img, valid, point_list)

    def update_img_point_list(self, point_list):
        if self.all_img_file:
            img_name = self.all_img_file[self.all_img_file_index]
            self.db_label_data.set_label(img_name, point_list=point_list)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    widget = MainWindow()
    widget.show()
    sys.exit(app.exec_())
