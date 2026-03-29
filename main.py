import sys
import sqlite3
import os
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem,
                             QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QInputDialog,
                             QMessageBox, QHeaderView, QAbstractItemView, QDialog,
                             QLabel, QLineEdit, QComboBox, QFormLayout, QDialogButtonBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon, QColor, QIntValidator

# --- 0. 语言字典 ---
LANG = {
    'zh': {
        'win_title': "SMT 物料管理系统 V1.0",
        'btn_add': "➕ 整盘新物料入库",
        'btn_use': "➖ 贴片消耗扣减",
        'btn_del': "🗑️ 删除选中物料",
        'btn_ref': "🔄 刷新表格",
        'btn_lang': "🌐 English",
        'headers': ['ID', '类别', '型号/名称', '封装', '详细参数', '厂家', '数量', '存放/上机位置'],
        'add_title': "录入购入编带物料",
        'f_cat': "物料类别:",
        'f_name': "具体名称/型号 (例: 100nF):",
        'f_pkg': "封装 (例: 0805):",
        'f_param': "详细参数 (例: 16V 10%):",
        'f_manu': "生产厂家:",
        'f_qty': "本次购入数量:",
        'f_loc': "存放/上机位置 (例: Feeder-1):",
        'msg_err': "错误",
        'msg_err_fill': "型号、封装和购入数量必须填写！",
        'msg_warn': "提示",
        'msg_warn_sel': "请先在表格中点击选中一行！",
        'msg_del_warn': "⚠️ 警告：此操作不可逆！\n\n您确定要彻底删除物料：\n【{}】吗？",
        'msg_consume': "当前【{}】剩余: {}\n请输入本次贴片消耗的数量:",
        'msg_success': "成功",
        'msg_done': "操作成功！",
        'cats': ["电容", "电阻", "电感", "IC芯片", "连接器", "二极管", "三极管"]
    },
    'en': {
        'win_title': "SMT Inventory Manager V1.0",
        'btn_add': "➕ Add New Reel",
        'btn_use': "➖ Consume Parts",
        'btn_del': "🗑️ Delete Selected",
        'btn_ref': "🔄 Refresh Table",
        'btn_lang': "🌐 中文",
        'headers': ['ID', 'Category', 'Part Name', 'Package', 'Parameters', 'Manufacturer', 'Qty', 'Location'],
        'add_title': "Add New Component Reel",
        'f_cat': "Category:",
        'f_name': "Part Name (e.g. 100nF):",
        'f_pkg': "Package (e.g. 0805):",
        'f_param': "Parameters (e.g. 16V 10%):",
        'f_manu': "Manufacturer:",
        'f_qty': "Quantity Added:",
        'f_loc': "Storage/Feeder Loc:",
        'msg_err': "Error",
        'msg_err_fill': "Part name, package, and quantity are required!",
        'msg_warn': "Warning",
        'msg_warn_sel': "Please select a row in the table first!",
        'msg_del_warn': "⚠️ WARNING: Cannot be undone!\n\nDelete this component forever?\n[{}]",
        'msg_consume': "Current [{}] remaining: {}\nEnter quantity consumed:",
        'msg_success': "Success",
        'msg_done': "Operation successful!",
        'cats': ["Capacitor", "Resistor", "Inductor", "IC", "Connector", "Diode", "Transistor"]
    }
}


# --- 1. “添加新物料”弹出窗口 ---
class AddMaterialDialog(QDialog):
    def __init__(self, current_lang, parent=None):
        super().__init__(parent)
        self.lang = current_lang
        self.texts = LANG[self.lang]

        self.setWindowTitle(self.texts['add_title'])
        self.setMinimumWidth(400)
        self.form_layout = QFormLayout()

        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(self.texts['cats'])
        self.form_layout.addRow(self.texts['f_cat'], self.category_input)

        self.name_input = QLineEdit()
        self.form_layout.addRow(self.texts['f_name'], self.name_input)

        self.package_input = QLineEdit()
        self.form_layout.addRow(self.texts['f_pkg'], self.package_input)

        self.param_input = QLineEdit()
        self.form_layout.addRow(self.texts['f_param'], self.param_input)

        self.manu_input = QLineEdit()
        self.form_layout.addRow(self.texts['f_manu'], self.manu_input)

        self.qty_input = QLineEdit()
        self.qty_input.setValidator(QIntValidator(0, 1000000))
        self.form_layout.addRow(self.texts['f_qty'], self.qty_input)

        self.loc_input = QLineEdit()
        self.form_layout.addRow(self.texts['f_loc'], self.loc_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.main_layout = QVBoxLayout()
        self.main_layout.addLayout(self.form_layout)
        self.main_layout.addWidget(self.button_box)
        self.setLayout(self.main_layout)

    def get_data(self):
        return {
            'category': self.category_input.currentText().strip(),
            'part_name': self.name_input.text().strip(),
            'package': self.package_input.text().strip(),
            'parameters': self.param_input.text().strip(),
            'manufacturer': self.manu_input.text().strip() if self.manu_input.text().strip() else "-",
            'quantity': int(self.qty_input.text()) if self.qty_input.text() else 0,
            'location': self.loc_input.text().strip() if self.loc_input.text().strip() else "-"
        }


# --- 2. 主窗口程序 ---
class InventoryManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_lang = 'zh'  # 默认语言为中文
        self.texts = LANG[self.current_lang]

        self.resize(1200, 700)
        self.init_db()
        self.init_ui()
        self.update_ui_texts()  # 初始化界面文字
        self.load_data()

    def init_db(self):
        if getattr(sys, 'frozen', False):
            application_path = os.path.dirname(sys.executable)
        else:
            application_path = os.path.dirname(os.path.abspath(__file__))
        db_path = os.path.join(application_path, 'components.db')

        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT, part_name TEXT, package TEXT,
                parameters TEXT, manufacturer TEXT, quantity INTEGER, location TEXT
            )
        ''')
        self.conn.commit()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 顶部按钮区域
        btn_layout = QHBoxLayout()

        self.btn_add = QPushButton()
        self.btn_add.setMinimumHeight(45)
        self.btn_add.setStyleSheet("background-color: #e1f5fe; font-weight: bold; font-size: 14px;")
        self.btn_add.clicked.connect(self.add_component_smart)

        self.btn_use = QPushButton()
        self.btn_use.setMinimumHeight(45)
        self.btn_use.setStyleSheet("font-size: 14px;")
        self.btn_use.clicked.connect(self.consume_component)

        self.btn_delete = QPushButton()
        self.btn_delete.setMinimumHeight(45)
        self.btn_delete.setStyleSheet("background-color: #ffcdd2; color: #b71c1c; font-weight: bold; font-size: 14px;")
        self.btn_delete.clicked.connect(self.delete_component)

        self.btn_refresh = QPushButton()
        self.btn_refresh.setMinimumHeight(45)
        self.btn_refresh.setStyleSheet("font-size: 14px;")
        self.btn_refresh.clicked.connect(self.load_data)

        # 语言切换按钮 (放最右边)
        self.btn_lang = QPushButton()
        self.btn_lang.setMinimumHeight(45)
        self.btn_lang.setStyleSheet("background-color: #eeeeee; font-weight: bold; font-size: 14px;")
        self.btn_lang.clicked.connect(self.toggle_language)

        btn_layout.addWidget(self.btn_add)
        btn_layout.addWidget(self.btn_use)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addStretch()  # 添加一个弹簧，把语言按钮推到最右侧
        btn_layout.addWidget(self.btn_lang)
        layout.addLayout(btn_layout)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

    # 动态更新所有UI文字
    def update_ui_texts(self):
        self.texts = LANG[self.current_lang]
        self.setWindowTitle(self.texts['win_title'])
        self.btn_add.setText(self.texts['btn_add'])
        self.btn_use.setText(self.texts['btn_use'])
        self.btn_delete.setText(self.texts['btn_del'])
        self.btn_refresh.setText(self.texts['btn_ref'])
        self.btn_lang.setText(self.texts['btn_lang'])
        self.table.setHorizontalHeaderLabels(self.texts['headers'])

    # 切换语言逻辑
    def toggle_language(self):
        self.current_lang = 'en' if self.current_lang == 'zh' else 'zh'
        self.update_ui_texts()

    def load_data(self):
        self.table.setRowCount(0)
        self.cursor.execute("SELECT * FROM inventory ORDER BY category, part_name")
        for row_idx, row_data in enumerate(self.cursor.fetchall()):
            self.table.insertRow(row_idx)
            for col_idx, col_data in enumerate(row_data):
                item = QTableWidgetItem(str(col_data))
                item.setTextAlignment(Qt.AlignCenter)
                if col_idx == 6 and int(col_data) < 100:
                    item.setForeground(QColor('#e64a19'))
                self.table.setItem(row_idx, col_idx, item)

    def add_component_smart(self):
        dialog = AddMaterialDialog(self.current_lang, self)
        if dialog.exec_() == QDialog.Accepted:
            data = dialog.get_data()
            if not data['part_name'] or not data['package'] or data['quantity'] <= 0:
                QMessageBox.warning(self, self.texts['msg_err'], self.texts['msg_err_fill'])
                return

            self.cursor.execute('''SELECT id, quantity, location FROM inventory 
                WHERE category=? AND part_name=? AND package=? AND parameters=? AND manufacturer=?''',
                                (data['category'], data['part_name'], data['package'], data['parameters'],
                                 data['manufacturer']))
            existing = self.cursor.fetchone()

            if existing:
                new_qty = existing[1] + data['quantity']
                new_loc = data['location'] if data['location'] != "-" else existing[2]
                self.cursor.execute("UPDATE inventory SET quantity=?, location=? WHERE id=?",
                                    (new_qty, new_loc, existing[0]))
            else:
                self.cursor.execute('''INSERT INTO inventory (category, part_name, package, parameters, manufacturer, quantity, location)
                    VALUES (?, ?, ?, ?, ?, ?, ?)''', (
                data['category'], data['part_name'], data['package'], data['parameters'], data['manufacturer'],
                data['quantity'], data['location']))
            self.conn.commit()
            QMessageBox.information(self, self.texts['msg_success'], self.texts['msg_done'])
            self.load_data()

    def consume_component(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, self.texts['msg_warn'], self.texts['msg_warn_sel'])
            return
        row = selected[0].row()
        item_id, part_name, current_qty = self.table.item(row, 0).text(), self.table.item(row, 2).text(), int(
            self.table.item(row, 6).text())

        msg = self.texts['msg_consume'].format(part_name, current_qty)
        use_qty, ok = QInputDialog.getInt(self, self.texts['win_title'], msg, value=0, min=0, max=current_qty)
        if ok and use_qty > 0:
            self.cursor.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (current_qty - use_qty, item_id))
            self.conn.commit()
            self.load_data()

    def delete_component(self):
        selected = self.table.selectedItems()
        if not selected:
            QMessageBox.warning(self, self.texts['msg_warn'], self.texts['msg_warn_sel'])
            return
        row = selected[0].row()
        item_id = self.table.item(row, 0).text()
        full_name = f"{self.table.item(row, 2).text()} ({self.table.item(row, 4).text()})"

        msg = self.texts['msg_del_warn'].format(full_name)
        reply = QMessageBox.question(self, self.texts['msg_warn'], msg, QMessageBox.Yes | QMessageBox.No,
                                     QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
            self.conn.commit()
            self.load_data()


if __name__ == "__main__":
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    if os.path.exists("icon.ico"): app.setWindowIcon(QIcon("icon.ico"))
    window = InventoryManager()
    window.show()
    sys.exit(app.exec_())