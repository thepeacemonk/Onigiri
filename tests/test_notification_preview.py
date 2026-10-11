import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTIFICATIONS_JS = (ROOT / "web" / "notifications.js").read_text(encoding="utf-8")
SETTINGS_JS = (ROOT / "web" / "settings.js").read_text(encoding="utf-8")
SETTINGS_CSS = (ROOT / "web" / "settings.css").read_text(encoding="utf-8")
SETTINGS_HTML = (ROOT / "web" / "settings.html").read_text(encoding="utf-8")
RENDER_PY = (ROOT / "settings_web" / "render.py").read_text(encoding="utf-8")


class NotificationPreviewTests(unittest.TestCase):
    def test_live_renderer_and_preview_share_element_factory(self):
        self.assertIn('createElement(payload, mode)', NOTIFICATIONS_JS)
        self.assertIn('createNotificationElement(data, "mini")', NOTIFICATIONS_JS)
        self.assertIn('createNotificationElement(data, "classic")', NOTIFICATIONS_JS)
        self.assertIn(
            'notifications.createElement(payload, mini ? "mini" : "classic")',
            SETTINGS_JS,
        )

    def test_settings_embeds_live_notification_runtime(self):
        self.assertIn("/*__ONIGIRI_NOTIFICATIONS_JS__*/", SETTINGS_HTML)
        self.assertIn('read_web_asset("notifications.js")', RENDER_PY)
        self.assertIn('.replace("/*__ONIGIRI_NOTIFICATIONS_JS__*/", notifications_js)', RENDER_PY)

    def test_mochi_preview_uses_live_stage_without_lookalike_css(self):
        self.assertIn('id: "mochi_message"', SETTINGS_JS)
        self.assertIn("paintLiveNotification(stage, vals, isDark, payload)", SETTINGS_JS)
        self.assertNotIn(".osw-mochistage-card", SETTINGS_CSS)
        self.assertNotIn(".osw-mochistage-icon", SETTINGS_CSS)

    def test_preview_mode_does_not_depend_on_reviewer_layout(self):
        self.assertIn(
            'const mini = (vals.g_notification_mode || "classic") === "mini";',
            SETTINGS_JS,
        )
        self.assertNotIn("const hasReviewerHeader", SETTINGS_JS)
        self.assertIn("if (mini) {\n      const headerParts", SETTINGS_JS)

    def test_mini_mount_keeps_live_header_width(self):
        header_rule = SETTINGS_CSS.split(
            "\n.osw-notifstage-header {", 1
        )[1].split("}", 1)[0]
        self.assertIn("width: max-content;", header_rule)


if __name__ == "__main__":
    unittest.main()
