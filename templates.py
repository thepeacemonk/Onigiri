# In templates.py

custom_body_template = """
<style>
    /* --- Sidebar Button Fix --- */
    .sidebar-left .menu-item,
    .sidebar-left .add-button-dashed,
    .sidebar-left .menu-group summary {{
        display: flex !important;
        align-items: center !important;
        width: 100%% !important;
        padding: 8px 12px !important;
        margin-bottom: 4px !important;
        box-sizing: border-box !important;
        border-radius: 6px !important;
        transition: background-color 0.2s ease !important;
        cursor: pointer !important;
        pointer-events: auto !important; /* This line re-enables clicks */
        flex-shrink: 0;   /* Prevents the buttons from shrinking vertically */
        min-height: 33px; /* Gives buttons a consistent, minimum height */
    }}

    .sidebar-left .menu-item:hover,
    .sidebar-left .add-button-dashed:hover,
    .sidebar-left .menu-group summary:hover {{
        background-color: rgba(128, 128, 128, 0.15) !important;
    }}

    .sidebar-left .icon {{
        margin-right: 12px !important;
        flex-shrink: 0;
    }}

    /* --- Deck List Click Area Fix --- */
    .deck-table .decktd {{
        display: flex;
        align-items: center;
        padding: 0 5px !important;
        pointer-events: auto !important; /* This line re-enables clicks */
    }}

    .deck-table a.deck {{
        flex-grow: 1;
        padding: 6px 8px;
        border-radius: 4px;
        transition: background-color 0.2s ease;
        display: block;
        pointer-events: auto !important; /* Ensure the link itself is clickable */
    }}

    .deck-table tr:not(.drag-hover) a.deck:hover {{
         background-color: rgba(128, 128, 128, 0.1);
    }}
    /* --- Deck List Scrolling Fix --- */
    .sidebar-expanded-content {{
        display: flex;
        flex-direction: column;
        /* Make this container fill the full height of the sidebar */
        height: 100%%;
        overflow: hidden; /* Prevents the parent from scrolling */
    }}

    #deck-list-container {{
        /* Make the deck list grow to fill all available vertical space */
        flex: 1; 
        /* Add a vertical scrollbar ONLY when the content overflows */
        overflow-y: auto;
        /* Prevents sizing issues within the flex container */
        min-height: 0; 
    }}
</style>
<div class="container modern-main-menu">
    <div class="sidebar-left skeleton-loading {sidebar_initial_class}" style="{sidebar_style}">
        
        <div class="sidebar-toggle-btn">
            <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"></polyline></svg>
        </div>

        <div class="sidebar-expanded-content">
            <h2>{welcome_message}</h2>
            {profile_bar}
            <div class="add-button-dashed" id="add-btn" onclick="pycmd('add')">
                <i class="icon"></i>
                <span>Add</span>
            </div>
            <div class="menu-item" id="browser-btn" onclick="pycmd('browse')">
                <i class="icon"></i>
                <span>Browser</span>
            </div>
            <div class="menu-item" id="stats-btn" onclick="pycmd('stats')">
                <i class="icon"></i>
                <span>Stats</span>
            </div>
            <div class="menu-item" id="sync-btn" onclick="pycmd('sync')">
                <i class="icon"></i>
                <span>Sync</span>
            </div>
            <div class="menu-item" id="onigiri-settings-btn" onclick="pycmd('openOnigiriSettings')">
                <i class="icon"></i>
                <span>Settings</span>
            </div>
            
            <details class="menu-group">
                <summary class="menu-item">
                    <i class="icon"></i>
                    <span>More</span>
                </summary>
                <div class="menu-group-items">
                    <div class="menu-item" id="get-shared-btn" onclick="pycmd('shared')">
                        <i class="icon"></i>
                        <span>Get Shared</span>
                    </div>
                    <div class="menu-item" id="create-deck-btn" onclick="pycmd('create')">
                        <i class="icon"></i>
                        <span>Create Deck</span>
                    </div>
                    <div class="menu-item" id="import-file-btn" onclick="pycmd('import')">
                        <i class="icon"></i>
                        <span>Import File</span>
                    </div>
                </div>
            </details>
            
            <h2>DECKS</h2>
            <div id="deck-list-container">
                <table class="deck-table">
                    <tbody>
                        %(tree)s
                    </tbody>
                </table>
            </div>
        </div>

        <div class="sidebar-collapsed-content">
            <div class="collapsed-profile-placeholder"></div>
            <div class="collapsed-actions-placeholder">
                <div></div><div></div><div></div><div></div><div></div><div></div>
            </div>
            <div class="collapsed-decks-placeholder"></div>
        </div>
    </div>
    <div class="resize-handle"></div>
    <div class="main-content">
        <div class="injected-stats-block">
            %(stats)s
        </div>
    </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    if (typeof anki !== 'undefined' && anki.setupDeckBrowser) {{
        anki.setupDeckBrowser();
    }}
}});
</script>
"""