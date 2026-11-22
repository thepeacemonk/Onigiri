"""Complete copy bundled with the manager, including in untranslated beta."""
from pathlib import Path
from .service import read_json

KEYS = ("title", "installed", "choose", "intro", "automatic", "updates_help", "switch", "close", "confirm", "confirm_body", "preparing", "ready", "restart", "cancel", "failed", "cancelled", "settings_desc", "manage")
COPY = {
    "en": (
        "Versions & Updates", "Installed version: {version}", "Choose a version",
        "Switch between Bento, Sake Nigiri and legacy. Your personal files are preserved and a full backup is kept. Features introduced in newer versions may be unavailable in older versions.",
        "Automatic updates", "Allow Anki’s automatic update prompts for Onigiri. You can still update manually. Switching versions turns this off; you can turn it back on here.",
        "Switch version…", "Close", "Switch to {version}?", "Onigiri will download the selected release and install it when Anki closes. Automatic updates will be turned off. Restart Anki to use the selected version.",
        "Downloading and verifying the release…", "{version} is ready. Restart Anki to apply it. Automatic updates are off.",
        "Close Anki to apply", "Cancel version switch", "Could not switch versions. {error}", "Version switch cancelled. The installed version is unchanged.",
        "Choose an older release or turn automatic updates on or off.", "Manage versions…"),
    "pt-BR": (
        "Versões e Atualizações", "Versão instalada: {version}", "Escolha uma versão",
        "Alterne entre Bento, Sake Nigiri e legacy. Seus arquivos pessoais são preservados e um backup completo é mantido. Recursos de versões mais novas podem não estar disponíveis nas versões antigas.",
        "Atualizações automáticas", "Permita os avisos automáticos de atualização do Anki para o Onigiri. Você ainda pode atualizar manualmente. Trocar de versão desativa esta opção; você pode reativá-la aqui.",
        "Trocar de versão…", "Fechar", "Trocar para {version}?", "O Onigiri baixará a versão escolhida e a instalará quando o Anki fechar. As atualizações automáticas serão desativadas. Reinicie o Anki para usar a versão escolhida.",
        "Baixando e verificando a versão…", "{version} está pronta. Reinicie o Anki para aplicá-la. As atualizações automáticas estão desativadas.",
        "Fechar o Anki para aplicar", "Cancelar troca de versão", "Não foi possível trocar de versão. {error}", "Troca de versão cancelada. A versão instalada não mudou.",
        "Escolha uma versão anterior ou ative e desative as atualizações automáticas.", "Gerenciar versões…"),
    "es-ES": (
        "Versiones y Actualizaciones", "Versión instalada: {version}", "Elige una versión",
        "Cambia entre Bento, Sake Nigiri y legacy. Se conservan tus archivos personales y una copia de seguridad completa. Las funciones de versiones nuevas pueden no estar disponibles en versiones anteriores.",
        "Actualizaciones automáticas", "Permite los avisos automáticos de actualización de Anki para Onigiri. Puedes seguir actualizando manualmente. Cambiar de versión desactiva esta opción; puedes reactivarla aquí.",
        "Cambiar de versión…", "Cerrar", "¿Cambiar a {version}?", "Onigiri descargará la versión elegida y la instalará cuando Anki se cierre. Se desactivarán las actualizaciones automáticas. Reinicia Anki para usar la versión elegida.",
        "Descargando y verificando la versión…", "{version} está lista. Reinicia Anki para aplicarla. Las actualizaciones automáticas están desactivadas.",
        "Cerrar Anki para aplicar", "Cancelar cambio de versión", "No se pudo cambiar de versión. {error}", "Cambio de versión cancelado. La versión instalada no ha cambiado.",
        "Elige una versión anterior o activa y desactiva las actualizaciones automáticas.", "Gestionar versiones…"),
    "fr-FR": (
        "Versions et Mises à jour", "Version installée : {version}", "Choisir une version",
        "Passez de Bento à Sake Nigiri ou à Legacy. Vos fichiers personnels sont conservés et une sauvegarde complète est gardée. Les fonctions récentes peuvent être indisponibles dans les anciennes versions.",
        "Mises à jour automatiques", "Autoriser les notifications de mise à jour automatiques d’Anki pour Onigiri. Les mises à jour manuelles restent possibles. Changer de version désactive cette option ; vous pouvez la réactiver ici.",
        "Changer de version…", "Fermer", "Passer à {version} ?", "Onigiri téléchargera la version choisie et l’installera à la fermeture d’Anki. Les mises à jour automatiques seront désactivées. Redémarrez Anki pour utiliser la version choisie.",
        "Téléchargement et vérification de la version…", "{version} est prête. Redémarrez Anki pour l’appliquer. Les mises à jour automatiques sont désactivées.",
        "Fermer Anki pour appliquer", "Annuler le changement de version", "Impossible de changer de version. {error}", "Changement de version annulé. La version installée est inchangée.",
        "Choisissez une ancienne version ou activez et désactivez les mises à jour automatiques.", "Gérer les versions…"),
    "de-DE": (
        "Versionen und Updates", "Installierte Version: {version}", "Version auswählen",
        "Wechseln Sie zwischen Bento, Sake Nigiri und Legacy. Ihre persönlichen Dateien und eine vollständige Sicherung bleiben erhalten. Neuere Funktionen sind in älteren Versionen möglicherweise nicht verfügbar.",
        "Automatische Updates", "Automatische Update-Hinweise von Anki für Onigiri erlauben. Manuelle Updates bleiben möglich. Ein Versionswechsel schaltet diese Option aus; Sie können sie hier wieder aktivieren.",
        "Version wechseln…", "Schließen", "Zu {version} wechseln?", "Onigiri lädt die gewählte Version herunter und installiert sie beim Beenden von Anki. Automatische Updates werden ausgeschaltet. Starten Sie Anki neu, um die gewählte Version zu verwenden.",
        "Version wird heruntergeladen und überprüft…", "{version} ist bereit. Starten Sie Anki neu, um sie anzuwenden. Automatische Updates sind ausgeschaltet.",
        "Anki zum Anwenden schließen", "Versionswechsel abbrechen", "Versionswechsel fehlgeschlagen. {error}", "Versionswechsel abgebrochen. Die installierte Version bleibt unverändert.",
        "Eine ältere Version wählen oder automatische Updates ein- und ausschalten.", "Versionen verwalten…"),
    "zh-CN": (
        "版本与更新", "已安装版本：{version}", "选择版本",
        "在 Bento、Sake Nigiri 和 legacy 之间切换。您的个人文件会被保留，并保存完整备份。新版本的功能可能无法在旧版本中使用。",
        "自动更新", "允许 Anki 显示 Onigiri 的自动更新提示。您仍可手动更新。切换版本会关闭此选项，您可在此重新开启。",
        "切换版本…", "关闭", "切换到 {version}？", "Onigiri 将下载所选版本，并在 Anki 关闭时安装。自动更新将关闭。请重启 Anki 以使用所选版本。",
        "正在下载并验证版本…", "{version} 已准备就绪。请重启 Anki 以应用。自动更新已关闭。",
        "关闭 Anki 以应用", "取消版本切换", "无法切换版本。{error}", "已取消版本切换。已安装的版本未改变。",
        "选择旧版本，或开启和关闭自动更新。", "管理版本…"),
    "ja-JP": (
        "バージョンと更新", "インストール済み：{version}", "バージョンを選択",
        "Bento、Sake Nigiri、legacy を切り替えられます。個人ファイルは保持され、完全なバックアップが保存されます。新しい機能は旧バージョンでは利用できない場合があります。",
        "自動更新", "Anki による Onigiri の自動更新通知を許可します。手動更新は引き続き可能です。バージョンを切り替えるとオフになりますが、ここで再度オンにできます。",
        "バージョンを切り替える…", "閉じる", "{version} に切り替えますか？", "選択したバージョンをダウンロードし、Anki の終了時にインストールします。自動更新はオフになります。選択したバージョンを使うには Anki を再起動してください。",
        "バージョンをダウンロードして検証中…", "{version} の準備ができました。適用するには Anki を再起動してください。自動更新はオフです。",
        "適用するため Anki を終了", "バージョンの切り替えを取り消す", "切り替えできませんでした。{error}", "切り替えを取り消しました。インストール済みのバージョンは変わりません。",
        "旧バージョンを選択するか、自動更新をオンまたはオフにします。", "バージョンを管理…"),
    "ko-KR": (
        "버전 및 업데이트", "설치된 버전: {version}", "버전 선택",
        "Bento, Sake Nigiri, legacy 사이를 전환합니다. 개인 파일이 보존되며 전체 백업이 저장됩니다. 새 버전의 기능은 이전 버전에서 사용할 수 없을 수 있습니다.",
        "자동 업데이트", "Anki의 Onigiri 자동 업데이트 알림을 허용합니다. 수동 업데이트는 계속 가능합니다. 버전을 전환하면 이 옵션이 꺼지며 여기에서 다시 켤 수 있습니다.",
        "버전 전환…", "닫기", "{version}(으)로 전환할까요?", "Onigiri가 선택한 버전을 다운로드하고 Anki를 종료할 때 설치합니다. 자동 업데이트가 꺼집니다. 선택한 버전을 사용하려면 Anki를 다시 시작하세요.",
        "버전을 다운로드하고 확인하는 중…", "{version} 준비가 완료되었습니다. 적용하려면 Anki를 다시 시작하세요. 자동 업데이트가 꺼져 있습니다.",
        "적용하려면 Anki 종료", "버전 전환 취소", "버전을 전환할 수 없습니다. {error}", "버전 전환이 취소되었습니다. 설치된 버전은 변경되지 않았습니다.",
        "이전 버전을 선택하거나 자동 업데이트를 켜고 끕니다.", "버전 관리…"),
}
LANGUAGES = {"English (Default)": "en", "Português (Brasil)": "pt-BR", "Español (España)": "es-ES", "Français": "fr-FR", "Deutsch": "de-DE", "简体中文": "zh-CN", "日本語": "ja-JP", "한국어": "ko-KR"}
MENU_LABELS = {
    "en": "Select version", "pt-BR": "Selecionar versão",
    "es-ES": "Seleccionar versión", "fr-FR": "Choisir une version",
    "de-DE": "Version auswählen", "zh-CN": "选择版本",
    "ja-JP": "バージョンを選択", "ko-KR": "버전 선택",
}
LATEST_LABELS = {
    "en": "latest", "pt-BR": "mais recente", "es-ES": "más reciente",
    "fr-FR": "dernière", "de-DE": "aktuellste", "zh-CN": "最新",
    "ja-JP": "最新", "ko-KR": "최신",
}
UPDATE_KEYS = ("updates_on", "updates_on_detail", "updates_off", "updates_off_detail",
               "updates_unknown", "updates_unknown_detail", "updates_failed")
UPDATE_MESSAGES = {
    "en": (
        "Automatic updates are on",
        "You’ll receive automatic update prompts when a new Onigiri release is available. Switching versions turns this off. You can also update manually.",
        "Automatic updates are off",
        "You won’t receive automatic update prompts for Onigiri. Your version stays installed until you update or switch manually.",
        "Update preference could not be confirmed",
        "Reopen this panel to check your saved update preference.",
        "Could not save the update preference. {error}"),
    "pt-BR": (
        "Atualizações automáticas ativadas",
        "Você receberá avisos automáticos quando houver uma nova versão do Onigiri. Trocar de versão desativa esta opção. Você também pode atualizar manualmente.",
        "Atualizações automáticas desativadas",
        "Você não receberá avisos automáticos de atualização do Onigiri. Sua versão será mantida até você atualizar ou trocar manualmente.",
        "Não foi possível confirmar a preferência de atualização",
        "Reabra este painel para verificar sua preferência de atualização salva.",
        "Não foi possível salvar a preferência de atualização. {error}"),
    "es-ES": (
        "Actualizaciones automáticas activadas",
        "Recibirás avisos automáticos cuando haya una nueva versión de Onigiri. Cambiar de versión desactiva esta opción. También puedes actualizar manualmente.",
        "Actualizaciones automáticas desactivadas",
        "No recibirás avisos automáticos de actualización de Onigiri. Tu versión se mantendrá hasta que actualices o cambies manualmente.",
        "No se pudo confirmar la preferencia de actualización",
        "Vuelve a abrir este panel para comprobar tu preferencia de actualización guardada.",
        "No se pudo guardar la preferencia de actualización. {error}"),
    "fr-FR": (
        "Mises à jour automatiques activées",
        "Vous recevrez des notifications automatiques lorsqu’une nouvelle version d’Onigiri sera disponible. Changer de version désactive cette option. Vous pouvez aussi mettre à jour manuellement.",
        "Mises à jour automatiques désactivées",
        "Vous ne recevrez pas de notifications automatiques de mise à jour d’Onigiri. Votre version restera installée jusqu’à une mise à jour ou un changement manuel.",
        "La préférence de mise à jour n’a pas pu être confirmée",
        "Rouvrez ce panneau pour vérifier votre préférence de mise à jour enregistrée.",
        "Impossible d’enregistrer la préférence de mise à jour. {error}"),
    "de-DE": (
        "Automatische Updates sind eingeschaltet",
        "Sie erhalten automatische Update-Hinweise, sobald eine neue Onigiri-Version verfügbar ist. Ein Versionswechsel schaltet diese Option aus. Manuelle Updates bleiben möglich.",
        "Automatische Updates sind ausgeschaltet",
        "Sie erhalten keine automatischen Update-Hinweise für Onigiri. Ihre Version bleibt installiert, bis Sie manuell aktualisieren oder die Version wechseln.",
        "Die Update-Einstellung konnte nicht bestätigt werden",
        "Öffnen Sie diesen Dialog erneut, um Ihre gespeicherte Update-Einstellung zu prüfen.",
        "Die Update-Einstellung konnte nicht gespeichert werden. {error}"),
    "zh-CN": (
        "自动更新已开启",
        "有新版 Onigiri 可用时，您会收到自动更新提示。切换版本会关闭此选项。您也可以手动更新。",
        "自动更新已关闭",
        "您不会收到 Onigiri 的自动更新提示。当前版本会保持不变，直到您手动更新或切换版本。",
        "无法确认更新偏好",
        "请重新打开此面板，查看已保存的更新偏好。",
        "无法保存更新偏好。{error}"),
    "ja-JP": (
        "自動更新はオンです",
        "Onigiri の新しいバージョンが利用可能になると、自動更新通知が届きます。バージョンを切り替えるとオフになります。手動更新も可能です。",
        "自動更新はオフです",
        "Onigiri の自動更新通知は届きません。手動で更新または切り替えるまで、現在のバージョンが維持されます。",
        "更新設定を確認できませんでした",
        "この画面を開き直して、保存された更新設定を確認してください。",
        "更新設定を保存できませんでした。{error}"),
    "ko-KR": (
        "자동 업데이트가 켜져 있습니다",
        "새 Onigiri 버전이 있으면 자동 업데이트 알림을 받습니다. 버전을 전환하면 이 옵션이 꺼집니다. 수동 업데이트도 가능합니다.",
        "자동 업데이트가 꺼져 있습니다",
        "Onigiri의 자동 업데이트 알림을 받지 않습니다. 직접 업데이트하거나 버전을 전환할 때까지 현재 버전이 유지됩니다.",
        "업데이트 설정을 확인할 수 없습니다",
        "이 화면을 다시 열어 저장된 업데이트 설정을 확인하세요.",
        "업데이트 설정을 저장할 수 없습니다. {error}"),
}


def language(root):
    try:
        from aqt import mw
        # Saved settings are authoritative; the profile is a legacy mirror.
        settings = Path(root) / "user_files" / ("settings_" + mw.pm.name + ".json")
        try:
            selected = read_json(settings).get("language")
        except (OSError, ValueError):
            selected = None
        if selected in COPY:
            return selected
        if selected in LANGUAGES:
            return LANGUAGES[selected]
        selected = mw.pm.profile.get("onigiri_language", "en")
        return selected if selected in COPY else LANGUAGES.get(selected, "en")
    except Exception:
        return "en"


def translate(key, root):
    if key == "menu_label":
        return MENU_LABELS[language(root)]
    if key == "latest":
        return LATEST_LABELS[language(root)]
    if key in UPDATE_KEYS:
        return dict(zip(UPDATE_KEYS, UPDATE_MESSAGES[language(root)]))[key]
    return dict(zip(KEYS, COPY[language(root)]))[key]
