from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTextEdit, QGroupBox, QGridLayout, QMessageBox
)
from aqt import mw
from .onigimon import manager, ITEMS, FOOD_ITEM_KEYS, HYGIENE_ITEM_KEYS
import json
from dataclasses import asdict
from datetime import date

class OnigimonSandboxDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Onigimon Sandbox (Debug)")
        self.resize(600, 600)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.setup_ui()
        self.refresh_bridge_status()

    def setup_ui(self):
        # 1. Ankimon Bridge Status
        bridge_group = QGroupBox("Ankimon Bridge Status")
        bridge_layout = QVBoxLayout()
        
        self.bridge_status_label = QLabel("Status: Checking...")
        bridge_layout.addWidget(self.bridge_status_label)
        
        self.bridge_log = QTextEdit()
        self.bridge_log.setReadOnly(True)
        self.bridge_log.setFixedHeight(120)
        bridge_layout.addWidget(self.bridge_log)

        refresh_bridge_btn = QPushButton("Refresh Bridge Data")
        refresh_bridge_btn.clicked.connect(self.refresh_bridge_status)
        bridge_layout.addWidget(refresh_bridge_btn)
        
        btn_ankimon_hp = QPushButton("Simulate Ankimon: Heal +10 HP")
        btn_ankimon_hp.clicked.connect(lambda: self.update_ankimon("hp", 10))
        bridge_layout.addWidget(btn_ankimon_hp)
        
        btn_ankimon_atk = QPushButton("Simulate Ankimon: +1 Attack")
        btn_ankimon_atk.clicked.connect(lambda: self.update_ankimon("attack", 1))
        bridge_layout.addWidget(btn_ankimon_atk)
        
        bridge_group.setLayout(bridge_layout)
        self.layout.addWidget(bridge_group)

        # 2. Companion Stats Manipulation
        stats_group = QGroupBox("Active Companion Stats")
        stats_layout = QGridLayout()

        btn_hunger_0 = QPushButton("Set Hunger = 0")
        btn_hunger_0.clicked.connect(lambda: self.set_stat("hunger", 0))
        btn_hunger_100 = QPushButton("Set Hunger = 100")
        btn_hunger_100.clicked.connect(lambda: self.set_stat("hunger", 100))
        
        btn_happy_0 = QPushButton("Set Happiness = 0")
        btn_happy_0.clicked.connect(lambda: self.set_stat("happiness", 0))
        btn_happy_100 = QPushButton("Set Happiness = 100")
        btn_happy_100.clicked.connect(lambda: self.set_stat("happiness", 100))
        
        btn_energy_0 = QPushButton("Set Energy = 0")
        btn_energy_0.clicked.connect(lambda: self.set_stat("energy", 0))
        btn_energy_100 = QPushButton("Set Energy = 100")
        btn_energy_100.clicked.connect(lambda: self.set_stat("energy", 100))

        btn_hygiene_0 = QPushButton("Set Hygiene = 0")
        btn_hygiene_0.clicked.connect(lambda: self.set_stat("cleanliness", 0))
        btn_hygiene_100 = QPushButton("Set Hygiene = 100")
        btn_hygiene_100.clicked.connect(lambda: self.set_stat("cleanliness", 100))

        stats_layout.addWidget(btn_hunger_0, 0, 0)
        stats_layout.addWidget(btn_hunger_100, 0, 1)
        stats_layout.addWidget(btn_happy_0, 1, 0)
        stats_layout.addWidget(btn_happy_100, 1, 1)
        stats_layout.addWidget(btn_energy_0, 2, 0)
        stats_layout.addWidget(btn_energy_100, 2, 1)
        stats_layout.addWidget(btn_hygiene_0, 3, 0)
        stats_layout.addWidget(btn_hygiene_100, 3, 1)

        stats_group.setLayout(stats_layout)
        self.layout.addWidget(stats_group)

        # 3. Item Cheats
        items_group = QGroupBox("Inventory")
        items_layout = QVBoxLayout()
        
        btn_add_items = QPushButton("Add 10 of All Items")
        btn_add_items.clicked.connect(self.add_items)
        items_layout.addWidget(btn_add_items)
        
        btn_clear_items = QPushButton("Clear Inventory")
        btn_clear_items.clicked.connect(self.clear_items)
        items_layout.addWidget(btn_clear_items)
        
        items_group.setLayout(items_layout)
        self.layout.addWidget(items_group)

        # 4. Gameplay Progression
        game_group = QGroupBox("Gameplay Progression")
        game_layout = QVBoxLayout()

        btn_sim_reviews = QPushButton("Simulate 10 Reviews (Grants 1 Play)")
        btn_sim_reviews.clicked.connect(self.simulate_reviews)
        game_layout.addWidget(btn_sim_reviews)

        btn_reset_gift = QPushButton("Reset Daily Gift Timer")
        btn_reset_gift.clicked.connect(self.reset_gift_timer)
        game_layout.addWidget(btn_reset_gift)

        btn_reset_study_day = QPushButton("Clear Last Study Day (Streak Test)")
        btn_reset_study_day.clicked.connect(self.reset_study_day)
        game_layout.addWidget(btn_reset_study_day)
        
        game_group.setLayout(game_layout)
        self.layout.addWidget(game_group)

        # 5. Quick Action Tests
        test_group = QGroupBox("Test Actions")
        test_layout = QGridLayout()

        btn_test_gift = QPushButton("Test Daily Gift (Show Popup)")
        btn_test_gift.clicked.connect(self.test_daily_gift)
        btn_test_play = QPushButton("Test Play")
        btn_test_play.clicked.connect(self.test_play)
        btn_test_train = QPushButton("Test Training")
        btn_test_train.clicked.connect(self.test_train)
        btn_test_hygiene = QPushButton("Test Hygiene (Clean)")
        btn_test_hygiene.clicked.connect(self.test_hygiene)
        btn_test_hunger = QPushButton("Test Hunger (Feed)")
        btn_test_hunger.clicked.connect(self.test_hunger)

        test_layout.addWidget(btn_test_gift, 0, 0, 1, 2)
        test_layout.addWidget(btn_test_play, 1, 0)
        test_layout.addWidget(btn_test_train, 1, 1)
        test_layout.addWidget(btn_test_hygiene, 2, 0)
        test_layout.addWidget(btn_test_hunger, 2, 1)

        test_group.setLayout(test_layout)
        self.layout.addWidget(test_group)

        self.layout.addStretch()

    def refresh_bridge_status(self):
        status = manager.status()
        self.bridge_status_label.setText(f"Status: {status}")
        
        if status == "ready" or status == "no_collection":
            try:
                collection = manager.bridge.get_collection()
                formatted = json.dumps(collection, indent=2, ensure_ascii=False)
                self.bridge_log.setPlainText(f"Found {len(collection)} Pokémon in Ankimon Bridge:\n{formatted}")
            except Exception as e:
                self.bridge_log.setPlainText(f"Error fetching collection: {str(e)}")
        elif status == "missing":
            self.bridge_log.setPlainText("Ankimon Add-on not found or inactive.")
        else:
            self.bridge_log.setPlainText("Ankimon found, but no starter selected yet.")

    def set_stat(self, stat_name: str, value: int):
        companion = manager.active_companion()
        if not companion:
            QMessageBox.warning(self, "No Companion", "You need to select a companion first!")
            return
            
        setattr(companion, stat_name, value)
        state = manager.load()
        state.companions[companion.ankimon_id] = asdict(companion)
        manager.save()
        QMessageBox.information(self, "Success", f"{companion.name}'s {stat_name} set to {value}.")

    def update_ankimon(self, stat: str, val: int):
        companion = manager.active_companion()
        if not companion:
            QMessageBox.warning(self, "No Companion", "Select a companion first.")
            return
        if manager.bridge.update_ankimon_stat(companion.ankimon_id, {stat: val}):
            if stat == "hp" and companion.max_hp:
                companion.hp = min(companion.max_hp, companion.hp + val)
            QMessageBox.information(self, "Success", f"Added {val} to Ankimon {stat}.")
            self.refresh_bridge_status()
        else:
            QMessageBox.warning(self, "Error", "Could not update Ankimon stats.")

    def add_items(self):
        state = manager.load()
        for key in ITEMS.keys():
            state.inventory[key] = state.inventory.get(key, 0) + 10
        manager.save()
        QMessageBox.information(self, "Success", "Added 10 of every item to your inventory.")

    def clear_items(self):
        state = manager.load()
        for key in ITEMS.keys():
            state.inventory[key] = 0
        manager.save()
        QMessageBox.information(self, "Success", "Inventory cleared.")

    def simulate_reviews(self):
        state = manager.load()
        # Ensure last_study_day matches today so we just add reviews
        today = date.today().isoformat()
        if state.last_study_day != today:
            manager._advance_streak(state, today)
        state.today_review_count += 10
        manager.save()
        QMessageBox.information(self, "Success", f"Simulated 10 reviews. Today's count: {state.today_review_count}. Plays available: {manager.plays_available(state)}.")

    def reset_gift_timer(self):
        state = manager.load()
        state.last_daily_gift_day = ""
        manager.save()
        QMessageBox.information(self, "Success", "Daily gift timer reset. You can claim it again today.")

    def reset_study_day(self):
        state = manager.load()
        state.last_study_day = ""
        manager.save()
        QMessageBox.information(self, "Success", "Last study day cleared. Your next review will start a new day.")

    def _require_companion(self):
        companion = manager.active_companion()
        if not companion:
            QMessageBox.warning(self, "No Companion", "You need to select a companion first!")
        return companion

    def test_daily_gift(self):
        if not self._require_companion():
            return
        state = manager.load()
        state.last_market_gift_day = ""
        manager.save()
        from ..patcher import open_onigimon_care_dialog
        dialog = open_onigimon_care_dialog()
        QTimer.singleShot(300, lambda: dialog._on_bridge_cmd("onigimon_market_gift"))

    def test_play(self):
        companion = self._require_companion()
        if not companion:
            return
        state = manager.load()
        today = date.today().isoformat()
        if manager.plays_available(state) <= 0:
            if state.last_study_day != today:
                manager._advance_streak(state, today)
            state.today_review_count += 10
        if companion.energy < 10:
            companion.energy = 100
            state.companions[companion.ankimon_id] = asdict(companion)
        manager.save()
        message = manager.play()
        QMessageBox.information(self, "Test Play", message or "No response (play failed).")

    def test_train(self):
        companion = self._require_companion()
        if not companion:
            return
        state = manager.load()
        today = date.today().isoformat()
        if manager.plays_available(state) <= 0:
            if state.last_study_day != today:
                manager._advance_streak(state, today)
            state.today_review_count += 10
        if companion.energy < 15:
            companion.energy = 100
            state.companions[companion.ankimon_id] = asdict(companion)
        manager.save()
        message = manager.train()
        QMessageBox.information(self, "Test Training", message or "No response (training failed).")

    def _test_interaction(self, status: str, item_keys, title: str):
        if not self._require_companion():
            return
        state = manager.load()
        if item_keys and not any(int(state.inventory.get(k, 0) or 0) > 0 for k in item_keys):
            state.inventory[item_keys[0]] = state.inventory.get(item_keys[0], 0) + 1
            manager.save()
        message = manager.interact_with_status(status)
        QMessageBox.information(self, title, message or "No response.")

    def test_hygiene(self):
        self._test_interaction("hygiene", HYGIENE_ITEM_KEYS, "Test Hygiene")

    def test_hunger(self):
        self._test_interaction("hunger", FOOD_ITEM_KEYS, "Test Hunger")

def open_sandbox():
    dialog = OnigimonSandboxDialog(mw)
    dialog.exec()
