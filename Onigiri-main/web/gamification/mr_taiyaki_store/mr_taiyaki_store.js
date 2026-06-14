var storeData = {};

// --- 1. INITIALIZATION ---
function initStore(data) {
    console.log("Initializing Store with data:", data);
    storeData = data;
    updateWallet();
    renderItems('restaurants', data.restaurants);
    renderItems('evolutions', data.evolutions);
}

// --- 2. UI UPDATES ---
function updateWallet() {
    const balanceEl = document.getElementById('coin-balance');
    if (balanceEl) {
        // Animate the number counting up/down
        animateValue(balanceEl, parseInt(balanceEl.textContent), storeData.coins, 1000);
    }

    if (storeData.coin_image_path) {
        const icon = document.getElementById('wallet-coin-icon');
        if (icon) icon.src = storeData.coin_image_path;
    }
}

// Helper to animate numbers
function animateValue(obj, start, end, duration) {
    let startTimestamp = null;
    const step = (timestamp) => {
        if (!startTimestamp) startTimestamp = timestamp;
        const progress = Math.min((timestamp - startTimestamp) / duration, 1);
        obj.innerHTML = Math.floor(progress * (end - start) + start);
        if (progress < 1) {
            window.requestAnimationFrame(step);
        }
    };
    window.requestAnimationFrame(step);
}

function switchTab(tabName) {
    document.querySelectorAll('.nav-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelector(`.nav-btn[onclick="switchTab('${tabName}')"]`).classList.add('active');

    document.querySelectorAll('.items-grid').forEach(grid => grid.classList.remove('active'));
    document.getElementById(`${tabName}-grid`).classList.add('active');
}

// --- 3. RENDERING ---
function renderItems(gridId, items) {
    const grid = document.getElementById(`${gridId}-grid`);
    if (!grid) return;

    grid.innerHTML = '';
    const template = document.getElementById('item-template');

    Object.entries(items).forEach(([id, item]) => {
        const clone = template.content.cloneNode(true);

        // Fill Data
        clone.querySelector('.item-name').textContent = item.name;
        clone.querySelector('.item-price').textContent = item.price;

        // Handle Coin Icon
        const coinSymbol = clone.querySelector('.coin-symbol');
        if (storeData.coin_image_path) {
            const img = document.createElement('img');
            img.src = storeData.coin_image_path;
            img.className = 'coin-icon-small';
            coinSymbol.textContent = '';
            coinSymbol.appendChild(img);
        }

        // Handle Images
        const previewImage = clone.querySelector('.preview-image');
        const previewColor = clone.querySelector('.preview-color');

        if (item.image && storeData.image_base_path) {
            previewImage.src = storeData.image_base_path + item.image;
            previewImage.style.display = 'block';
            previewImage.onerror = () => { previewImage.style.display = 'none'; };
        }

        if (item.theme) {
            previewColor.style.backgroundColor = item.theme;
        } else {
            previewColor.style.background = 'linear-gradient(45deg, #f3f4f6, #d1d5db)';
        }

        // Handle Buttons
        const btn = clone.querySelector('.action-btn');
        const isOwned = storeData.owned_items.includes(id);
        const isEquipped = storeData.current_theme_id === id;

        // Clean up old classes
        btn.className = 'action-btn';

        if (isEquipped) {
            btn.textContent = "Unequip";
            btn.classList.add('unequip');
            btn.onclick = () => equipItem('default');
        } else if (isOwned) {
            btn.textContent = "Equip";
            btn.classList.add('equip');
            btn.onclick = () => equipItem(id);
        } else {
            btn.textContent = "Buy";
            btn.classList.add('buy');

            if (storeData.coins < item.price) {
                btn.disabled = true;
                btn.title = "Not enough coins";
                btn.style.opacity = "0.5";
            } else {
                btn.onclick = () => buyItem(id);
            }
        }

        grid.appendChild(clone);
    });
}

// --- 4. ACTIONS (SEND TO ANKI) ---

function buyItem(itemId) {
    // Anki pycmd cannot take a callback. We send the command, and Python calls a function back.
    pycmd(`buy_item:${itemId}`);
}

function equipItem(itemId) {
    pycmd(`equip_item:${itemId}`);
}

function buyRealMoneyCoins() {
    showCustomPrompt("Taiyaki Coin Code", "Enter your Coin Code (e.g. ONI-XXXX-YYY):", (code) => {
        if (code) {
            console.log("[ONIGIRI JS] Redeeming code:", code);
            const btn = document.getElementById('buy-coins-btn');
            if (btn) {
                btn.innerHTML = "Verifying...";
                btn.style.opacity = "0.7";
                btn.disabled = true;
            }
            // Send to Python
            console.log("[ONIGIRI JS] Sending pycmd:", `redeem_code:${code}`);
            pycmd(`redeem_code:${code}`);
        } else {
            console.log("[ONIGIRI JS] Code redemption cancelled");
        }
    });
}

// --- 5. RESPONSES (CALLED BY PYTHON) ---

// Python calls this after a purchase attempt
window.onPurchaseResult = function (result) {
    if (result.success) {
        storeData.coins = result.new_balance;
        storeData.owned_items.push(result.item_id);
        updateWallet();
        // Refresh UI
        renderItems('restaurants', storeData.restaurants);
        renderItems('evolutions', storeData.evolutions);
        // Optional: Play sound or show success animation
    } else {
        alert(result.message || "Purchase failed.");
    }
}

// Python calls this after an equip attempt
window.onEquipResult = function (result) {
    if (result.success) {
        storeData.current_theme_id = result.item_id;
        renderItems('restaurants', storeData.restaurants);
        renderItems('evolutions', storeData.evolutions);
    } else {
        alert(result.message);
    }
}

// Python calls this after code redemption
window.onRedeemResult = function (result) {
    console.log("[ONIGIRI JS] onRedeemResult called with:", result);

    // Reset button
    const btn = document.getElementById('buy-coins-btn');
    if (btn) {
        btn.innerHTML = `Get More Coins
            <span class="buy-coins-btn-sparkle buy-coins-btn-sparkle--top"></span>
            <span class="buy-coins-btn-sparkle buy-coins-btn-sparkle--left"></span>
            <span class="buy-coins-btn-sparkle buy-coins-btn-sparkle--right"></span>
        `;
        btn.style.opacity = "1";
        btn.disabled = false;
    }

    if (result.success) {
        console.log("[ONIGIRI JS] Redemption successful! New balance:", result.new_balance);
        storeData.coins = result.new_balance;
        updateWallet();
        alert(result.message); // "Success! 500 Coins added."
    } else {
        console.log("[ONIGIRI JS] Redemption failed:", result.message);
        alert("Redemption Failed:\n" + result.message);
    }
}

// --- 6. UTILS ---

function showCustomPrompt(title, message, callback) {
    // Existing modal code...
    const overlay = document.createElement('div');
    overlay.className = 'custom-prompt-overlay';
    const modal = document.createElement('div');
    modal.className = 'custom-prompt-modal';
    modal.innerHTML = `
        <div class="custom-prompt-header"><h2>${title}</h2></div>
        <div class="custom-prompt-body"><p>${message}</p><input type="text" class="custom-prompt-input" placeholder="Code..." /></div>
        <div class="custom-prompt-footer">
            <button class="custom-prompt-btn custom-prompt-btn-cancel">Cancel</button>
            <button class="custom-prompt-btn custom-prompt-btn-ok">OK</button>
        </div>
    `;
    overlay.appendChild(modal);
    document.body.appendChild(overlay);

    const input = modal.querySelector('.custom-prompt-input');
    const okBtn = modal.querySelector('.custom-prompt-btn-ok');
    const cancelBtn = modal.querySelector('.custom-prompt-btn-cancel');

    setTimeout(() => input.focus(), 100);

    const handleOk = () => {
        const value = input.value.trim();
        document.body.removeChild(overlay);
        callback(value);
    };

    const handleCancel = () => {
        document.body.removeChild(overlay);
        callback(null);
    };

    okBtn.addEventListener('click', handleOk);
    cancelBtn.addEventListener('click', handleCancel);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) handleCancel(); });
    input.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleOk(); });
    document.addEventListener('keydown', function escapeHandler(e) {
        if (e.key === 'Escape') {
            handleCancel();
            document.removeEventListener('keydown', escapeHandler);
        }
    });
}

// Wait for Python to inject data
document.addEventListener('DOMContentLoaded', () => {
    if (window.ONIGIRI_STORE_DATA) {
        initStore(window.ONIGIRI_STORE_DATA);
    }
});