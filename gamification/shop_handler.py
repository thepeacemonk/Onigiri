import json
import requests
from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo, tooltip
from anki.hooks import addHook
from .restaurant_level import manager as restaurant_manager



SHOP_API_URL = "https://script.google.com/macros/s/AKfycbwg5HMxT9FWQIbPIVRrI6u8k_JheZBRUWWI0q5Jcl-ecRrPB4L25FJDh65YFjv__i4k/exec"

class StoreWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mr. Taiyaki Store")
        self.resize(1050, 700)
        
        # Setup Webview
        self.web = mw.web.create_standard_webview(self)
        
        # Layout
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.web)
        self.setLayout(layout)

        # Bind the bridge
        self.web.set_bridge_command(self.handle_bridge_command, self)

        # Load the HTML
        self.load_store()

    def load_store(self):
        # Get the main package name (e.g., "123456789")
        addon_package = mw.addonManager.addonFromModule(__name__)
        
        # --- UPDATE: PATHS FOR WEB/MR_TAIYAKI_STORE ---
        
        # 1. Web Paths (URL format for the browser to find JS/CSS)
        # These point to: /_addons/{package_id}/web/mr_taiyaki_store/filename
        base_web_path = f"/_addons/{addon_package}/web/mr_taiyaki_store"
        js_path = f"{base_web_path}/mr_taiyaki_store.js"
        css_path = f"{base_web_path}/mr_taiyaki_store.css"
        
        # 2. File Reading (Reading the HTML content from disk)
        # We ask Anki to find the file relative to the addon root
        html_content = mw.addonManager.getResource(addon_package, "web/mr_taiyaki_store/mr_taiyaki_store.html")
        
        # --- END PATH UPDATE ---

        # Prepare the INIT data
        init_data = self.get_store_data()
        json_data = json.dumps(init_data)

        # Injection Block
        # We inject the data and the correct paths to CSS/JS
        injection = f"""
        <script>window.ONIGIRI_STORE_DATA = {json_data};</script>
        <link rel="stylesheet" href="{css_path}">
        <script src="{js_path}"></script>
        """
        
        # Append before closing body
        if html_content:
            final_html = html_content.replace("</body>", f"{injection}</body>")
            self.web.stdHtml(final_html, css=None, js=None, context=None)
        else:
            showInfo("Error: Could not find mr_taiyaki_store.html in web/mr_taiyaki_store/")

    def handle_bridge_command(self, cmd):
        # 1. Handle BUY
        if cmd.startswith("buy_item:"):
            item_id = cmd.split(":")[1]
            self.process_purchase(item_id)
            
        # 2. Handle EQUIP
        elif cmd.startswith("equip_item:"):
            item_id = cmd.split(":")[1]
            self.process_equip(item_id)
            
        # 3. Handle REDEEM
        elif cmd.startswith("redeem_code:"):
            code = cmd.split(":")[1]
            self.process_redemption(code)

    def get_store_data(self):
        """
        Returns the dictionary required by the JS initStore()
        """
        config = mw.addonManager.getConfig(__name__)
        
        return {
            "coins": config.get('coin_balance', 0),
            "owned_items": config.get('owned_items', ['default']),
            "current_theme_id": config.get('current_theme_id', 'default'),
            
            # Paths for images (optional)
            "coin_image_path": "", 
            "image_base_path": "",
            
            # DEFINE YOUR ITEMS HERE
            "restaurants": {
                "matcha_cafe": {"name": "Matcha Cafe", "price": 500, "theme": "#98d8aa", "image": "matcha.png"},
                "sushi_bar": {"name": "Sushi Bar", "price": 1200, "theme": "#ff8e8e", "image": "sushi.png"},
                "french_bakery": {"name": "French Bakery", "price": 800, "theme": "#f1c40f", "image": "croissant.png"},
            },
            "evolutions": {
                "golden_taiyaki": {"name": "Golden Taiyaki", "price": 5000, "theme": "gold", "image": "gold_fish.png"}
            }
        }

    # --- LOGIC HANDLERS ---

    def process_purchase(self, item_id):
        success, message = restaurant_manager.buy_item(item_id)
        
        if success:
            # Get updated balance
            data = restaurant_manager.get_store_data()
            new_balance = data.get("coins", 0)
            
            self.reply_to_js("onPurchaseResult", {
                "success": True, 
                "new_balance": new_balance,
                "item_id": item_id,
                "message": message
            })
        else:
            self.reply_to_js("onPurchaseResult", {"success": False, "message": message})

    def process_equip(self, item_id):
        success, message = restaurant_manager.equip_item(item_id)
        
        if success:
             self.reply_to_js("onEquipResult", {"success": True, "item_id": item_id})
        else:
             # JS didn't expect error message but we can log it or just fail silently as before
             pass

    def process_redemption(self, code):
        """
        Talks to Google Sheets in the background
        """
        print(f"[ONIGIRI DEBUG] Starting redemption for code: {code}")
        
        from aqt.operations import QueryOp
        
        def on_success(result):
            if result["success"]:
                # Update Local Config (Main Thread)
                config = mw.addonManager.getConfig(__name__)
                current = config.get('coin_balance', 0)
                new_balance = current + result["added_coins"]
                config['coin_balance'] = new_balance
                mw.addonManager.writeConfig(__name__, config)
                
                self.reply_to_js("onRedeemResult", {
                    "success": True,
                    "new_balance": new_balance,
                    "message": f"Success! +{result['added_coins']} Coins added."
                })
            else:
                self.reply_to_js("onRedeemResult", {
                    "success": False,
                    "message": result["message"]
                })

        def on_failure(error):
            self.reply_to_js("onRedeemResult", {
                "success": False,
                "message": f"Error: {str(error)}"
            })

        def background_op(col):
            # This runs in background thread
            try:
                payload = {"code": code}
                response = requests.post(SHOP_API_URL, json=payload, timeout=10)
                
                try:
                    data = response.json()
                except json.JSONDecodeError:
                    return {"success": False, "message": f"Server returned invalid response: {response.text[:100]}"}
                
                if data.get("result") == "success":
                    return {
                        "success": True, 
                        "added_coins": int(data.get("coins", 0))
                    }
                else:
                    return {
                        "success": False, 
                        "message": data.get("message", "Invalid Code")
                    }
            except requests.exceptions.Timeout:
                return {"success": False, "message": "Request timed out. Please check your internet connection."}
            except requests.exceptions.ConnectionError:
                return {"success": False, "message": "Could not connect to server. Please check your internet connection."}
            except Exception as e:
                return {"success": False, "message": str(e)}

        op = QueryOp(
            parent=self,
            op=background_op,
            success=on_success
        )
        op.with_progress().run_in_background()

    def reply_to_js(self, function_name, data_dict):
        """
        Helper to send JSON back to JS functions
        """
        json_str = json.dumps(data_dict)
        self.web.eval(f"{function_name}({json_str});")

# --- EXPOSED FUNCTION TO OPEN SHOP ---
def open_shop_window():
    mw.shop_dialog = StoreWindow(mw)
    mw.shop_dialog.show()