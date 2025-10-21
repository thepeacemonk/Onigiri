import json
from aqt import mw
from aqt.webview import AnkiWebView
from anki.decks import DeckId
from PyQt6.QtWidgets import QApplication


def show_transfer_window(source_dids_json: str) -> None:
    """
    Renders and displays a dedicated web view for transferring selected decks.
    This function is called from the main deck browser's JavaScript.
    """

    try:
        source_dids = json.loads(source_dids_json)
        if not isinstance(source_dids, list):
            raise TypeError("Expected a list of deck IDs.")
    except (json.JSONDecodeError, TypeError) as e:
        return

    all_decks = mw.col.decks.all_names_and_ids()
    target_decks = []

    # Filter for decks that are folders (have children) and are not the ones being moved.
    for deck in all_decks:
        if deck.id in source_dids:
            continue  # Skip decks that are part of the selection
        
        # A deck is considered a folder if it has children.
        if mw.col.decks.children(deck.id):
            target_decks.append(deck)

    deck_list_html = ""
    for deck in target_decks:
        # Indent sub-decks for better readability
        name_parts = deck.name.split("::")
        indentation = "&nbsp;&nbsp;&nbsp;&nbsp;" * (len(name_parts) - 1)
        display_name = name_parts[-1]

        deck_list_html += f"""
            <div class="transfer-deck-item" data-did="{deck.id}" data-name="{deck.name.lower()}">
                {indentation}{display_name}
            </div>
        """

    # Resolve this add-on's package to build correct web URLs
    addon_package = mw.addonManager.addonFromModule(__name__)

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 0;
                background-color: var(--canvas);
                color: var(--fg);
                overflow: hidden;
            }}
            .container {{
                display: flex;
                flex-direction: column;
                height: 100vh;
                padding: 20px 20px 20px 20px;
                box-sizing: border-box;
            }}
            
            /* --- Header Styling --- */
            .header-banner {{
                position: relative;
                width: 100%;
                margin: 0 0 20px 0;
                height: 100px !important;
                border-radius: 16px;
                overflow: hidden;
                min-height: 100px !important;
            }}
            .header-background {{
                background-image: url("/_addons/{addon_package}/system_files/satellite.png");
                background-size: cover;
                background-position: center;
                height: 100%;
                filter: blur(8px);
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background-color: #4f46e5;
            }}
            .header-content {{
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                display: flex !important;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                padding: 20px;
                text-align: center;
                z-index: 10;
            }}
            .plane-icon {{
                width: 30px !important;
                height: 30px !important;
                margin-bottom: 15px;
                display: block
            }}
            h3 {{
                margin: 0;
                font-size: 20px !important;
                color: white !important;
                font-weight: 700;
            }}
            /* --- End Header Styling --- */
            #search-bar {{
                width: 100%;
                padding: 10px 12px;
                margin-bottom: 15px;
                border: 1px solid var(--border);
                border-radius: 8px;
                background-color: var(--canvas-inset);
                color: var(--fg);
                font-size: 14px;
                box-sizing: border-box;
            }}
            #search-bar:focus {{
                outline: none;
                border-color: var(--accent-color);
                box-shadow: 0 0 0 2px var(--accent-color-alpha-20);
            }}
            .deck-list-container {{
                flex-grow: 1;
                overflow-y: auto;
                border: 1px solid var(--border-subtle);
                border-radius: 8px;
                padding: 5px;
            }}
            .transfer-deck-item {{
                padding: 8px 10px;
                cursor: pointer;
                border-radius: 8px;
                white-space: nowrap;
                font-size: 14px;
                border: 2px solid transparent;
                transition: all 0.2s ease;
            }}
            .transfer-deck-item:hover {{
                background-color: var(--canvas-inset);
            }}
            .transfer-deck-item.selected {{
                border-color: var(--accent-color);
                background-color: var(--accent-color-alpha-20);
                color: var(--accent-color);
                font-weight: 600;
            }}
            .actions {{
                padding-top: 20px;
                display: flex;
                justify-content: flex-end;
            }}
            #save-btn {{
                padding: 10px 20px;
                background-color: var(--accent-color);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: background-color 0.2s;
            }}
            #save-btn:hover {{
                background-color: var(--accent-color-hover);
            }}
            #save-btn:disabled {{
                background-color: var(--fg-disabled);
                cursor: not-allowed;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header-banner">
                <div class="header-background"></div>
                <div class="header-content">
                    <div class="plane-icon">
                        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 640" aria-hidden="true" focusable="false">
                            <path fill="white" d="M552 264C582.9 264 608 289.1 608 320C608 350.9 582.9 376 552 376L424.7 376L265.5 549.6C259.4 556.2 250.9 560 241.9 560L198.2 560C187.3 560 179.6 549.3 183 538.9L237.3 376L137.6 376L84.8 442C81.8 445.8 77.2 448 72.3 448L52.5 448C42.1 448 34.5 438.2 37 428.1L64 320L37 211.9C34.4 201.8 42.1 192 52.5 192L72.3 192C77.2 192 81.8 194.2 84.8 198L137.6 264L237.3 264L183 101.1C179.6 90.7 187.3 80 198.2 80L241.9 80C250.9 80 259.4 83.8 265.5 90.4L424.7 264L552 264z"/>
                        </svg>
                    </div>
                    <h3>Choose a destination for your selected decks:</h3>
                </div>
            </div>
            <input type="text" id="search-bar" placeholder="Search for a destination deck...">
            <div class="deck-list-container">
                {deck_list_html}
            </div>
            <div class="actions">
                <button id="save-btn" disabled>Save</button>
            </div>
        </div>
        <script>
            const sourceDids = {json.dumps(source_dids)};
            const saveButton = document.getElementById('save-btn');
            const deckListContainer = document.querySelector('.deck-list-container');
            const searchBar = document.getElementById('search-bar');
            let selectedDid = null;

            deckListContainer.addEventListener('click', (e) => {{
                const target = e.target.closest('.transfer-deck-item');
                if (!target) return;

                // Ensure we have a valid deck ID
                if (!target.dataset.did || target.dataset.did === 'undefined' || target.dataset.did === 'null') {{
                    alert('Error: Invalid deck selected. Please try again.');
                    return;
                }}

                deckListContainer.querySelectorAll('.selected').forEach(el => el.classList.remove('selected'));
                target.classList.add('selected');
                selectedDid = target.dataset.did;

                saveButton.disabled = false;
            }});

            searchBar.addEventListener('input', (e) => {{
                const query = e.target.value.toLowerCase().trim();
                document.querySelectorAll('.transfer-deck-item').forEach(item => {{
                    const name = item.dataset.name;
                    item.style.display = name.includes(query) ? '' : 'none';
                }});
            }});

            saveButton.addEventListener('click', () => {{
                if (!selectedDid || selectedDid === 'undefined' || selectedDid === 'null') {{
                    // Fallback: try to get the selected deck from DOM
                    const selectedElement = deckListContainer.querySelector('.transfer-deck-item.selected');
                    if (selectedElement && selectedElement.dataset.did) {{
                        selectedDid = selectedElement.dataset.did;
                    }} else {{
                        alert('Error: No destination deck selected. Please click on a deck first.');
                        return;
                    }}
                }}

                // Ensure deck IDs are integers
                const sourceDidsInt = sourceDids.map(id => parseInt(id));
                const targetDidInt = parseInt(selectedDid);

                // Validate that all deck IDs are valid integers
                if (sourceDidsInt.some(id => isNaN(id)) || isNaN(targetDidInt)) {{
                    alert('Error: Invalid deck IDs. Please try again.');
                    return;
                }}

                const payload = {{
                    source_dids: sourceDidsInt,
                    target_did: targetDidInt
                }};

                if (typeof pycmd !== 'function') {{
                    alert('Error: Communication with Anki failed. Please restart Anki.');
                    return;
                }}

                try {{
                    const command = 'onigiri_move_decks:' + JSON.stringify(payload);
                    pycmd(command);
                }} catch (error) {{
                    alert('Error sending command: ' + error.message);
                }}
            }});
        </script>
    </body>
    </html>
    """
    # Create and show the AnkiWebView
    web = AnkiWebView(title="AirDeck Control")
    web.setWindowTitle("AirDeck Control")
    web.stdHtml(html_content)
    web.resize(600, 800)  # Set width to 800px, height to 600px
    # Center the window on the screen
    window = web.window()
    screen = QApplication.primaryScreen().geometry()
    window_size = window.frameGeometry()
    x = (screen.width() - window_size.width()) // 2
    y = (screen.height() - window_size.height()) // 2
    window.move(x, y)
    web.eval("document.body.className = anki.theme;") # Apply dark/light theme
    web.show()
    # Store a reference on mw to prevent garbage collection
    mw.onigiri_transfer_window = web

def handle_onigiri_commands(handled, message, context):
    """
    Route custom Onigiri commands to their respective handlers.
    """
    if message.startswith("onigiri_show_transfer_window:"):
        try:
            source_dids_json = message.replace("onigiri_show_transfer_window:", "")
            show_transfer_window(source_dids_json)
            return True
        except Exception as e:
            return True
    
    return handled