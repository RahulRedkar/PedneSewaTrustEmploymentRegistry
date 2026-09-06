"""
Standard Qt Icon helper for Pedne Sewa Trust - Employment Registry.
Provides crisp system vector icons via QStyle.StandardPixmap.
"""

from PySide6.QtWidgets import QApplication, QStyle
from PySide6.QtGui import QIcon


def get_icon(pixmap_enum) -> QIcon:
    """Retrieves standard QStyle system icon."""
    app = QApplication.instance()
    if app:
        return app.style().standardIcon(pixmap_enum)
    return QIcon()


class AppIcons:
    """Semantic icon accessors using standard Qt Pixmaps."""

    @staticmethod
    def dashboard() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileDialogListView)

    @staticmethod
    def add_candidate() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileDialogNewFolder)

    @staticmethod
    def database() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileDialogContentsView)

    @staticmethod
    def reports() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileDialogDetailedView)

    @staticmethod
    def sync() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_BrowserReload)

    @staticmethod
    def backup() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DriveFDIcon)

    @staticmethod
    def settings() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileDialogInfoView)

    @staticmethod
    def save() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DialogSaveButton)

    @staticmethod
    def refresh() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_BrowserReload)

    @staticmethod
    def export_file() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_ArrowDown)

    @staticmethod
    def cancel() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DialogCancelButton)

    @staticmethod
    def view_details() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileDialogDetailedView)

    @staticmethod
    def edit() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_FileIcon)

    @staticmethod
    def delete() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_TrashIcon)

    @staticmethod
    def clear() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DialogResetButton)

    @staticmethod
    def gov_jobs() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_MessageBoxInformation)

    @staticmethod
    def private_jobs() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DesktopIcon)

    @staticmethod
    def recruiters() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DirHomeIcon)

    @staticmethod
    def trash() -> QIcon:
        return AppIcons.delete()

    @staticmethod
    def view() -> QIcon:
        return AppIcons.view_details()

    @staticmethod
    def match() -> QIcon:
        return get_icon(QStyle.StandardPixmap.SP_DialogApplyButton)

