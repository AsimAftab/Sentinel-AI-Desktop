"""
Frontend enhancer - adds backend status widget to existing dashboard without modifying source.
"""

import sys
from pathlib import Path
from PyQt5.QtWidgets import QMessageBox
from .status_widget import BackendStatusWidget


class FrontendEnhancer:
    """Enhances the existing frontend with backend integration."""

    def __init__(self, backend_runner):
        self.backend_runner = backend_runner
        self.status_widget = None
        self.main_window = None

    def enhance_frontend(self):
        """
        Inject backend status widget into the frontend dashboard.
        This hooks into the existing code without modifying it.
        """
        # Add frontend to path
        frontend_path = Path(__file__).parent.parent / "Sentinel-AI-Frontend"
        sys.path.insert(0, str(frontend_path))

        # Import frontend modules
        try:
            from ui.views import dashboard  # type: ignore  # noqa: E402 - Dynamic import after sys.path modification

            # Monkey-patch the dashboard initialization to add our status widget
            original_init = dashboard.DashboardPage.__init__

            def enhanced_init(self, *args, **kwargs):
                # Call original init
                original_init(self, *args, **kwargs)

                # Check if this is the new dashboard design (has comm_bus attribute)
                if hasattr(self, 'comm_bus'):
                    # New dashboard already has built-in status support - skip injection
                    print("ℹ️ New dashboard detected - skipping legacy status widget injection")
                    return

                # Add our status widget to the dashboard (legacy dashboards only)
                self.backend_status_widget = BackendStatusWidget(self)

                # Replace Quick Actions section with Voice Assistant widget
                try:
                    from PyQt5.QtWidgets import QFrame, QVBoxLayout

                    # Find the Quick Actions frame
                    quick_actions_frames = self.findChildren(QFrame, "quick_actions")
                    if quick_actions_frames:
                        quick_actions_frame = quick_actions_frames[0]

                        # The dashboard uses QVBoxLayout, we need to find the main content layout
                        # and replace the quick_actions widget at its position
                        def find_and_replace_in_layout(layout, target_widget, replacement_widget):
                            """Recursively search layout and replace widget"""
                            if layout is None:
                                return False

                            # Check if target is in this layout
                            for i in range(layout.count()):
                                item = layout.itemAt(i)
                                if item.widget() == target_widget:
                                    # Found it! Replace at this position
                                    layout.removeWidget(target_widget)
                                    target_widget.setParent(None)
                                    target_widget.deleteLater()
                                    layout.insertWidget(i, replacement_widget)
                                    return True
                                elif item.layout():
                                    # Recursively check sub-layouts
                                    if find_and_replace_in_layout(item.layout(), target_widget, replacement_widget):
                                        return True
                            return False

                        # Start search from the dashboard's main layout
                        placed_successfully = find_and_replace_in_layout(
                            self.layout(),
                            quick_actions_frame,
                            self.backend_status_widget
                        )

                        if not placed_successfully:
                            raise Exception("Could not find Quick Actions in layout hierarchy")

                    else:
                        raise Exception("Could not find Quick Actions frame")

                except Exception as e:
                    print(f"Could not replace Quick Actions, using fallback: {e}")
                    # Fallback: insert at top of dashboard
                    if hasattr(self, 'layout') and self.layout():
                        self.layout().insertWidget(0, self.backend_status_widget)

                # Connect error signal to show message box
                self.backend_status_widget.backend_error_signal.connect(
                    self._show_backend_error
                )

            def _show_backend_error(self, error_msg):
                """Show error message box when backend fails."""
                QMessageBox.critical(
                    self,
                    "Backend Error",
                    f"Voice Assistant encountered an error:\n\n{error_msg}",
                    QMessageBox.Ok
                )

            # Apply patches
            dashboard.DashboardPage.__init__ = enhanced_init
            dashboard.DashboardPage._show_backend_error = _show_backend_error

        except Exception as e:
            print(f"Warning: Could not enhance frontend dashboard: {e}")
            # Frontend will still work without status widget

    def inject_status_widget(self, dashboard_widget):
        """
        Alternative method: Directly inject status widget into a dashboard instance.
        Call this if you have access to the dashboard widget.
        """
        if self.status_widget is None:
            self.status_widget = BackendStatusWidget(dashboard_widget)

        if dashboard_widget.layout():
            dashboard_widget.layout().insertWidget(0, self.status_widget)

            # Connect error signal
            self.status_widget.backend_error_signal.connect(
                lambda msg: self._show_error_dialog(dashboard_widget, msg)
            )

    def _show_error_dialog(self, parent, error_msg):
        """Show error dialog."""
        QMessageBox.critical(
            parent,
            "Backend Error",
            f"Voice Assistant encountered an error:\n\n{error_msg}",
            QMessageBox.Ok
        )
