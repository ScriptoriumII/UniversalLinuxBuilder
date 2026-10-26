DARK = """
QWidget {
    background: #10151D;
    color: #DCE4EF;
    font-family: "Segoe UI";
    font-size: 12px;
}

QMainWindow {
    background: #10151D;
}

QLabel {
    background: transparent;
}

QLineEdit,
QComboBox,
QTextEdit,
QTableWidget {
    background: #171F2B;
    color: #E5ECF5;
    border: 1px solid #2C394B;
    border-radius: 5px;
    padding: 5px;
    selection-background-color: #28558A;
}

QPushButton {
    background: #253448;
    color: #E5EDF7;
    border: 1px solid #354A62;
    border-radius: 5px;
    padding: 7px 12px;
    min-height: 22px;
}

QPushButton:hover {
    background: #304761;
    border-color: #52789E;
}

QPushButton:disabled {
    color: #66778A;
    background: #1A2330;
}

QTabWidget::pane {
    border: 1px solid #263447;
    border-top: none;
}

QTabBar::tab {
    background: #151D29;
    color: #AAB8CB;
    padding: 10px 17px;
    border-right: 1px solid #263447;
}

QTabBar::tab:selected {
    background: #1D2A3B;
    color: white;
    border-bottom: 2px solid #5B9DE3;
}

QTableWidget {
    alternate-background-color: #1D2939;
    gridline-color: transparent;
}

QHeaderView::section {
    background: #24344A;
    color: #DCE5F1;
    border: none;
    border-right: 1px solid #34455B;
    padding: 7px;
}

QGroupBox {
    border: 1px solid #2B3A4D;
    border-radius: 6px;
    margin-top: 13px;
    padding-top: 12px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 5px;
    color: #9EB8D6;
}

QScrollBar:vertical {
    background: #141D29;
    width: 11px;
}

QScrollBar::handle:vertical {
    background: #3B4E66;
    border-radius: 5px;
}

QTabWidget#sections::pane {
    border: 1px solid #263447;
    border-top: none;
}

QTabWidget#sections QTabBar::tab {
    padding: 8px 14px;
}
"""
