(function () {
    // Import the sushi dishes data
    let todaysSpecial = null;
    let dailyChallenge = {
        targetCards: 0,
        cardsDone: 0,
        completed: false
    };

    // Function to initialize the daily challenge
    function initDailyChallenge() {
        // Get current restaurant theme ID from backend payload
        const currentThemeId = window.ONIGIRI_RESTAURANT_LEVEL?.current_theme_id || 'default';

        // Get today's special based on the restaurant
        if (window.getTodaysSpecial) {
            todaysSpecial = window.getTodaysSpecial(currentThemeId);
        } else {
            todaysSpecial = window.getTodaysSushiSpecial();
        }

        // Check for backend data first (Source of Truth)
        const backendData = window.ONIGIRI_RESTAURANT_LEVEL?.daily_special;

        if (backendData && backendData.enabled) {
            dailyChallenge = {
                targetCards: backendData.target,
                cardsDone: backendData.current_progress,
                completed: backendData.current_progress >= backendData.target,
                date: new Date().toDateString()
            };
            // We don't rely on localStorage for the active challenge when backend data is available
        } else {
            // Fallback to localStorage logic if backend data is missing
            const savedProgress = localStorage.getItem('onigiriDailyChallenge');
            const today = new Date().toDateString();

            if (savedProgress) {
                const progress = JSON.parse(savedProgress);
                if (progress.date === today) {
                    dailyChallenge = progress.challenge;
                } else {
                    if (progress.challenge.completed && !progress.challenge.savedToHistory) {
                        saveCompletedSpecial(progress.challenge);
                        progress.challenge.savedToHistory = true;
                        localStorage.setItem('onigiriDailyChallenge', JSON.stringify(progress));
                    }
                    resetDailyChallenge();
                }
            } else {
                resetDailyChallenge();
            }
        }

        // Initialize completed specials display
        initCompletedSpecials();

        // Update the UI
        updateDailyChallengeUI();
    }

    // Save a completed special to the history
    function saveCompletedSpecial(challenge) {
        const today = new Date();
        const completedSpecial = {
            date: today.toISOString().split('T')[0], // YYYY-MM-DD format
            name: todaysSpecial.name,
            description: todaysSpecial.description,
            difficulty: todaysSpecial.difficulty || 'common',
            cardsCompleted: challenge.cardsDone,
            targetCards: challenge.targetCards,
            xpEarned: todaysSpecial.xpReward || 0
        };

        // Get existing history or create new array
        const history = JSON.parse(localStorage.getItem('onigiriCompletedSpecials') || '[]');

        // Add new completed special to the beginning of the array
        history.unshift(completedSpecial);

        // Keep only the last 30 days of history
        if (history.length > 30) {
            history.length = 30;
        }

        // Save back to localStorage
        localStorage.setItem('onigiriCompletedSpecials', JSON.stringify(history));
    }

    // Initialize the completed specials display
    function initCompletedSpecials() {
        let allSpecials = [];
        if (window.ONIGIRI_RESTAURANT_LEVEL?.completed_specials) {
            allSpecials = window.ONIGIRI_RESTAURANT_LEVEL.completed_specials;
        } else {
            allSpecials = JSON.parse(localStorage.getItem('onigiriCompletedSpecials') || '[]');
        }

        // Calculate 30 days ago date
        const now = new Date();
        const thirtyDaysAgo = new Date(now.getTime() - (30 * 24 * 60 * 60 * 1000));
        const thirtyDaysAgoStr = thirtyDaysAgo.toISOString().split('T')[0];

        // Split into recent (last 30 days) and archived (older than 30 days)
        const recentSpecials = [];
        const archivedSpecials = [];

        allSpecials.forEach(special => {
            const specialDate = special.date || '';
            if (specialDate >= thirtyDaysAgoStr) {
                recentSpecials.push(special);
            } else {
                archivedSpecials.push(special);
            }
        });

        // Sort recent specials by date in descending order (most recent first)
        recentSpecials.sort((a, b) => {
            const dateA = a.date || '';
            const dateB = b.date || '';
            return dateB.localeCompare(dateA); // descending order
        });

        // Initialize recent specials display (last 30 days only)
        initRecentSpecials(recentSpecials);

        // Initialize archived specials summary (ALL specials - all-time record)
        initArchivedSpecialsSummary(allSpecials);
    }

    // Initialize recent specials timeline (last 30 days)
    function initRecentSpecials(history) {
        const historyContainer = document.querySelector('.completed-specials-list');
        const countElement = document.querySelector('.completed-count');

        if (!historyContainer) return;

        // Update the count in the header
        if (countElement) {
            countElement.textContent = `${history.length} completed`;
        }

        if (history.length === 0) {
            historyContainer.innerHTML = '<p class="no-history">No completed specials in the last 30 days. Complete your daily challenge to see it here!</p>';
            return;
        }

        const difficultyIcons = {
            'common': '⭐',
            'uncommon': '🌟',
            'rare': '✨',
            'epic': '💫',
            'legendary': '🔥'
        };

        const html = `
            <div class="completed-specials-timeline">
                ${history.map((special, index) => `
                    <div class="timeline-item">
                        <div class="timeline-content">
                            <div class="timeline-header">
                                <div class="timeline-title">
                                    <span class="timeline-icon">${difficultyIcons[special.difficulty] || '⭐'}</span>
                                    <h4 class="special-name">${special.name}</h4>
                                </div>
                                <span class="special-date">${special.date}</span>
                            </div>
                            ${special.description ? `<p class="special-desc">${special.description}</p>` : ''}
                            <div class="timeline-footer">
                                <span class="special-difficulty ${special.difficulty}">
                                    ${special.difficulty.charAt(0).toUpperCase() + special.difficulty.slice(1)}
                                </span>
                                <div class="timeline-stats">
                                    <span class="stat cards">${special.cardsCompleted}/${special.targetCards} cards</span>

                                </div>
                            </div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        historyContainer.innerHTML = html;
    }

    // Initialize archived specials summary (older than 30 days)
    function initArchivedSpecialsSummary(archivedSpecials) {
        const summaryContainer = document.querySelector('.archived-specials-summary');
        const countElement = document.querySelector('.archived-count');

        if (!summaryContainer) return;

        // Count by rarity
        const rarityCounts = {
            'common': 0,
            'uncommon': 0,
            'rare': 0,
            'epic': 0,
            'legendary': 0
        };

        archivedSpecials.forEach(special => {
            const difficulty = (special.difficulty || 'common').toLowerCase();
            if (rarityCounts.hasOwnProperty(difficulty)) {
                rarityCounts[difficulty]++;
            } else {
                rarityCounts['common']++;
            }
        });

        const totalArchived = archivedSpecials.length;

        // Update the count in the header
        if (countElement) {
            countElement.textContent = `${totalArchived} recipes`;
        }

        if (totalArchived === 0) {
            summaryContainer.innerHTML = '<p class="no-history">Your all-time recipe collection will appear here when you complete specials.</p>';
            return;
        }

        const rarityInfo = {
            'common': { icon: '⭐', label: 'Common', color: '#4CAF50' },
            'uncommon': { icon: '🌟', label: 'Uncommon', color: '#2196F3' },
            'rare': { icon: '✨', label: 'Rare', color: '#9C27B0' },
            'epic': { icon: '💫', label: 'Epic', color: '#FF9800' },
            'legendary': { icon: '🔥', label: 'Legendary', color: '#F44336' }
        };

        const html = `
            <div class="rarity-collection">
                ${Object.entries(rarityInfo).map(([key, info]) => {
            const count = rarityCounts[key];
            return `
                        <div class="rarity-item ${count > 0 ? 'has-items' : 'empty'}">
                            <div class="rarity-icon" style="color: ${info.color}">${info.icon}</div>
                            <div class="rarity-info">
                                <span class="rarity-label" style="color: ${info.color}">${info.label}</span>
                                <span class="rarity-count">${count} recipe${count !== 1 ? 's' : ''}</span>
                            </div>
                        </div>
                    `;
        }).join('')}
            </div>
            <div class="collection-total">
                <span class="total-label">Total Recipes Collected:</span>
                <span class="total-count">${totalArchived}</span>
            </div>
        `;

        summaryContainer.innerHTML = html;
    }

    // Reset the daily challenge for a new day
    function resetDailyChallenge() {
        dailyChallenge = {
            targetCards: todaysSpecial.targetCards,
            cardsDone: 0,
            completed: false,
            date: new Date().toDateString()
        };
        saveChallengeProgress();
    }

    // Save the current challenge progress to localStorage
    function saveChallengeProgress() {
        localStorage.setItem('onigiriDailyChallenge', JSON.stringify({
            date: new Date().toDateString(),
            challenge: dailyChallenge
        }));
    }

    // Update the daily challenge UI
    function updateDailyChallengeUI() {
        if (!todaysSpecial) return;

        const elements = {
            sushiName: document.querySelector('.sushi-name'),
            sushiDesc: document.querySelector('.sushi-description'),
            progressFill: document.querySelector('.progress-fill'),
            cardsDone: document.querySelector('.cards-done'),
            cardsTarget: document.querySelector('.cards-target'),
            challengeStatus: document.querySelector('.challenge-status'),
            dailySpecialCard: document.querySelector('.daily-special'),
            difficultyBadge: document.querySelector('.difficulty-badge'),
            difficultyText: document.querySelector('.difficulty-text'),
            challengeReward: document.querySelector('.challenge-reward'),
            rewardXp: document.querySelector('.reward-xp')
        };

        // Check if all required elements exist
        if (Object.values(elements).some(el => !el)) return;

        // Update the sushi info
        elements.sushiName.textContent = '';
        elements.sushiName.appendChild(elements.difficultyBadge);
        const nameSpan = document.createElement('span');
        nameSpan.textContent = todaysSpecial.name;
        elements.sushiName.appendChild(nameSpan);
        elements.sushiDesc.textContent = todaysSpecial.description;

        // Update progress
        const progress = Math.min(dailyChallenge.cardsDone / dailyChallenge.targetCards, 1);
        elements.progressFill.style.width = `${progress * 100}%`;
        elements.cardsDone.textContent = dailyChallenge.cardsDone;
        elements.cardsTarget.textContent = dailyChallenge.targetCards;

        // Update difficulty badge
        elements.difficultyText.textContent = todaysSpecial.difficulty;
        elements.difficultyBadge.className = `difficulty-badge difficulty-${todaysSpecial.difficulty}`;
        elements.difficultyBadge.style.display = 'inline-flex';

        // Update Daily Special card background
        const difficulties = ['common', 'uncommon', 'rare', 'epic', 'legendary'];
        difficulties.forEach(diff => elements.dailySpecialCard.classList.remove(`difficulty-${diff}`));
        elements.dailySpecialCard.classList.add(`difficulty-${todaysSpecial.difficulty}`);

        // Update reward display
        elements.rewardXp.textContent = `${todaysSpecial.xpReward} XP`;
        elements.challengeReward.style.display = 'flex';

        // Update status message and completion state
        if (dailyChallenge.completed) {
            elements.challengeStatus.textContent = '🎉 Challenge completed! Great job chef!';
            elements.dailySpecialCard.classList.add('challenge-complete');

            // Add XP reward to the progress if not already added
            if (!dailyChallenge.xpAwarded) {
                awardXPReward(todaysSpecial.xpReward);
                dailyChallenge.xpAwarded = true;
                saveChallengeProgress();
            }
        } else {
            const remaining = dailyChallenge.targetCards - dailyChallenge.cardsDone;
            if (dailyChallenge.cardsDone > 0) {
                elements.challengeStatus.textContent = `Keep going! Just ${remaining} more cards to complete today's challenge.`;
            } else {
                elements.challengeStatus.textContent = `To prepare, study ${dailyChallenge.targetCards} cards today.`;
            }
            elements.dailySpecialCard.classList.remove('challenge-complete');
        }
    }

    // Function to update the challenge progress
    function updateChallengeProgress() {
        if (dailyChallenge.completed) return;

        // If we have backend data, we trust it and don't recalculate from DOM
        if (window.ONIGIRI_RESTAURANT_LEVEL?.daily_special?.enabled) {
            updateDailyChallengeUI();
            return;
        }

        // Get the review count from the 'Reviews today' element in the stats
        const todayReviewsElement = document.querySelector('[data-bind="today_reviews"]');
        let cardsDone = 0;

        if (todayReviewsElement) {
            // Parse the number from the element's text content (handles formatted numbers with commas)
            cardsDone = parseInt(todayReviewsElement.textContent.replace(/,/g, '')) || 0;
        }

        const wasCompleted = dailyChallenge.completed;

        // Update the challenge progress
        dailyChallenge.cardsDone = Math.min(cardsDone, dailyChallenge.targetCards);

        // Check if challenge is completed
        if (dailyChallenge.cardsDone >= dailyChallenge.targetCards) {
            dailyChallenge.completed = true;
            if (!wasCompleted) {
                // Only show confetti on the transition to completed
                showConfetti();
                // Save to completed specials
                saveCompletedSpecial(dailyChallenge);
            }
        }

        // Save progress and update UI
        saveChallengeProgress();
        updateDailyChallengeUI();
    }

    // Function to award XP for completing the challenge
    function awardXPReward(xpAmount) {
        // This function would typically interact with your XP system
        // The notification has been removed as per user request
    }

    // Show confetti effect when challenge is completed
    function showConfetti() {
        const confettiContainer = document.createElement('div');
        confettiContainer.style.position = 'fixed';
        confettiContainer.style.top = '0';
        confettiContainer.style.left = '0';
        confettiContainer.style.width = '100%';
        confettiContainer.style.height = '100%';
        confettiContainer.style.pointerEvents = 'none';
        confettiContainer.style.zIndex = '1000';
        document.body.appendChild(confettiContainer);

        // Create confetti elements
        for (let i = 0; i < 50; i++) {
            const confetti = document.createElement('div');
            confetti.style.position = 'absolute';
            confetti.style.width = '10px';
            confetti.style.height = '10px';
            confetti.style.backgroundColor = getRandomColor();
            confetti.style.borderRadius = '50%';
            confetti.style.left = Math.random() * 100 + '%';
            confetti.style.top = '100%';
            confetti.style.animation = `confetti ${Math.random() * 3 + 2}s linear forwards`;
            confettiContainer.appendChild(confetti);
        }

        // Remove confetti after animation
        setTimeout(() => {
            confettiContainer.remove();
        }, 3000);
    }

    // Helper function to get a random color for confetti
    function getRandomColor() {
        const colors = ['#ff9800', '#ff5722', '#e91e63', '#9c27b0', '#673ab7', '#3f51b5', '#2196f3', '#03a9f4', '#00bcd4', '#009688', '#4caf50', '#8bc34a', '#cddc39', '#ffeb3b', '#ffc107'];
        return colors[Math.floor(Math.random() * colors.length)];
    }

    function applyNightModeClass() {
        const body = document.body;
        if (!body) {
            return;
        }
        const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
        if (prefersDark) {
            body.classList.add('night-mode');
        } else {
            body.classList.remove('night-mode');
        }
    }

    function formatNumber(value) {
        if (typeof value !== 'number' || !Number.isFinite(value)) {
            return '0';
        }
        return value.toLocaleString();
    }

    function addSnowAnimation() {
        // Check if snow is already added
        if (document.getElementById('snow-container')) {
            return;
        }

        // Create snow container
        const snowContainer = document.createElement('div');
        snowContainer.id = 'snow-container';
        snowContainer.style.position = 'fixed';
        snowContainer.style.top = '0';
        snowContainer.style.left = '0';
        snowContainer.style.width = '100%';
        snowContainer.style.height = '100%';
        snowContainer.style.pointerEvents = 'none';
        snowContainer.style.zIndex = '100';
        snowContainer.style.overflow = 'hidden';

        // Create 30 snowflakes with random starting positions
        for (let i = 0; i < 30; i++) {
            const snowflake = document.createElement('div');
            snowflake.className = 'snowflake';
            snowflake.textContent = '❄';
            snowflake.style.position = 'absolute';
            snowflake.style.color = '#fff';
            snowflake.style.fontSize = '1.5em';
            snowflake.style.opacity = '0.8';
            snowflake.style.textShadow = '0 0 5px rgba(255, 255, 255, 0.8)';
            snowflake.style.left = (i * 3.33) + '%';

            // Random starting position (anywhere from -100vh to -10vh to avoid top edge)
            const randomStart = -(Math.random() * 90 + 10);
            snowflake.style.top = randomStart + 'vh';

            snowflake.style.animationDelay = (i * 0.3) % 4 + 's';
            snowflake.style.animationDuration = (8 + (i % 4)) + 's';
            snowContainer.appendChild(snowflake);
        }

        document.body.appendChild(snowContainer);

        // Add CSS animation if not already present
        if (!document.getElementById('snow-animation-style')) {
            const style = document.createElement('style');
            style.id = 'snow-animation-style';
            style.textContent = `
                .snowflake {
                    animation: snowfall linear infinite;
                }

                @keyframes snowfall {
                    0% {
                        transform: translateY(0) translateX(0);
                        opacity: 0;
                    }
                    10% {
                        opacity: 0.8;
                    }
                    90% {
                        opacity: 0.8;
                    }
                    100% {
                        transform: translateY(100vh) translateX(30px);
                        opacity: 0;
                    }
                }
            `;
            document.head.appendChild(style);
        }
    }

    function removeSnowAnimation() {
        const snowContainer = document.getElementById('snow-container');
        if (snowContainer) {
            snowContainer.remove();
        }

        const snowStyle = document.getElementById('snow-animation-style');
        if (snowStyle) {
            snowStyle.remove();
        }
    }

    function renderRestaurantLevel() {
        const payload = window.ONIGIRI_RESTAURANT_LEVEL || {};
        const progress = payload.progress || {};
        const stats = payload.stats || {};

        // Apply theme if present
        const themeColor = payload.theme_color;
        if (themeColor) {
            const rootStyle = document.documentElement.style;
            rootStyle.setProperty('--header-bg', `color-mix(in srgb, ${themeColor}, white 70%)`);
            // Attempt to create a dark variant and gradient using CSS color-mix (modern browsers)
            // Fallback or simple version if not supported will just use the color
            rootStyle.setProperty('--header-bg-dark', `color-mix(in srgb, ${themeColor}, black 60%)`);
            // Set the progress fill to use the theme color directly
            rootStyle.setProperty('--progress-fill', themeColor);
        }

        // Apply theme image if present
        const themeImage = payload.theme_image;
        const imageBasePath = payload.image_base_path;

        // Apply theme colors and image separately
        let styleTag = document.getElementById('dynamic-theme-image');
        if (!styleTag) {
            styleTag = document.createElement('style');
            styleTag.id = 'dynamic-theme-image';
            document.head.appendChild(styleTag);
        }

        let themeStyles = '';

        // Apply theme image if present
        if (themeImage && imageBasePath) {
            const imagePath = `${imageBasePath}${themeImage}`;
            themeStyles += `
                .rl-header::after {
                    background-image: url("${imagePath}") !important;
                }
            `;
        }

        // Apply theme color if present (independent of image)
        if (themeColor) {
            // Convert hex to rgba for transparency
            const hexToRgb = (hex) => {
                const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
                return result ? {
                    r: parseInt(result[1], 16),
                    g: parseInt(result[2], 16),
                    b: parseInt(result[3], 16)
                } : null;
            };

            const rgb = hexToRgb(themeColor);
            const rgbaColor = rgb ? `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.15)` : themeColor;
            const rgbaColorMedium = rgb ? `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.5)` : themeColor;
            const rgbaColorStrong = rgb ? `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.25)` : themeColor;
            const rgbaColorBorder = rgb ? `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, 0.4)` : themeColor;

            themeStyles += `
                .restaurant-level-page .daily-special {
                    /* background: var(--header-bg, ${themeColor}) !important; */
                    /* border-color: ${rgbaColorBorder} !important; */
                }
                
                .night-mode .restaurant-level-page .daily-special {
                    /* background: var(--header-bg-dark, ${themeColor}) !important; */
                }
                

                
                .restaurant-level-page .rl-level-chip {
                    background: ${rgbaColorStrong} !important;
                    color: var(--fg, #202124) !important;
                }
                
                .night-mode .restaurant-level-page .rl-level-chip {
                    background: ${rgbaColorStrong} !important;
                    color: white !important;
                }
                
                .restaurant-level-page .rl-progress-bar {
                    background: ${rgbaColor} !important;
                }
                
                /*
                .restaurant-level-page .progress-bar {
                    background: ${rgbaColor} !important;
                }
                */
                
                .night-mode .restaurant-level-page .rl-progress-bar {
                    background: ${rgbaColor} !important;
                }
                
                /*
                .night-mode .restaurant-level-page .progress-bar {
                    background: ${rgbaColor} !important;
                }
                */
                
                .restaurant-level-page .progress-fill,
                .restaurant-level-page .rl-progress-fill {
                    /* background: ${themeColor} !important; */
                }
            `;
        }

        // Apply the combined styles
        if (themeStyles) {
            styleTag.textContent = themeStyles;
        } else {
            // Remove style tag if no theme is active
            styleTag.remove();
        }


        // Add snow animation for Santa's Coffee theme
        if (themeImage && themeImage === "Santa's Coffee.png") {
            addSnowAnimation();
        } else {
            removeSnowAnimation();
        }

        // Initialize the daily challenge if not already done
        if (!todaysSpecial) {
            // Load the sushi dishes script if not already loaded
            if (window.getTodaysSushiSpecial) {
                initDailyChallenge();
            } else {
                const script = document.createElement('script');
                script.src = 'gamification/restaurant_level/special_dishes.js';
                script.onload = function () {
                    initDailyChallenge();
                    // Ensure completed specials are initialized even if daily challenge fails
                    initCompletedSpecials();
                };
                script.onerror = function () {
                    console.error('Failed to load sushi dishes, initializing completed specials anyway');
                    initCompletedSpecials();
                };
                document.head.appendChild(script);
            }
        } else {
            // Update challenge progress with current stats from DOM
            updateChallengeProgress();
            // Ensure completed specials are initialized
            initCompletedSpecials();
        }

        const root = document.querySelector('.restaurant-level-page');
        if (!root) {
            return;
        }

        root.dataset.enabled = progress.enabled ? 'true' : 'false';

        const levelValue = document.querySelector('[data-bind="level"]');
        if (levelValue) {
            levelValue.textContent = progress.level ?? 0;
        }

        // Update restaurant name
        const nameHeader = document.querySelector('.rl-hero-copy h1');
        if (nameHeader && progress.name) {
            nameHeader.textContent = progress.name;
        }

        const progressFill = document.querySelector('.rl-progress-bar .rl-progress-fill');
        if (progressFill) {
            let fraction = Number(progress.progressFraction || 0);
            if (!Number.isFinite(fraction) || fraction < 0) {
                fraction = 0;
            }
            if (fraction > 1) {
                fraction = 1;
            }
            if ((progress.xpToNextLevel || 0) <= 0) {
                fraction = 1;
            }
            progressFill.style.width = `${(fraction * 100).toFixed(1)}%`;
        }

        const xpDetail = document.querySelector('[data-bind="xp_detail"]');
        if (xpDetail) {
            const xpInto = progress.xpIntoLevel ?? 0;
            const xpNext = progress.xpToNextLevel ?? 0;
            const totalXp = progress.totalXp ?? 0;
            if (xpNext > 0) {
                xpDetail.textContent = `${formatNumber(xpInto)} / ${formatNumber(xpNext)} XP`;
            } else {
                xpDetail.textContent = `${formatNumber(totalXp)} XP total`;
            }
        }

        const phrase = document.querySelector('[data-bind="phrase"]');
        if (phrase) {
            phrase.textContent = progress.phrase || 'Keep serving knowledge!';
        }

        const todayReviews = document.querySelector('[data-bind="today_reviews"]');
        if (todayReviews) {
            todayReviews.textContent = formatNumber(stats.todayReviews || 0);
            // Update the challenge progress whenever review count changes
            if (typeof updateChallengeProgress === 'function') {
                updateChallengeProgress();
            }
        }

        const weekReviews = document.querySelector('[data-bind="week_reviews"]');
        if (weekReviews) {
            weekReviews.textContent = formatNumber(stats.weekReviews || 0);
        }

        const totalXp = document.querySelector('[data-bind="total_xp"]');
        if (totalXp) {
            totalXp.textContent = formatNumber(stats.totalXp || progress.totalXp || 0);
        }
    }

    function updateCountdown() {
        const timeElement = document.getElementById('restaurant-countdown-time');
        if (!timeElement) return;

        // Get the countdown time from the config
        const config = window.ONIGIRI_RESTAURANT_LEVEL?.config || {};
        const countdownHour = parseInt(config.restaurant_countdown_hour) || 4;
        const countdownMinute = parseInt(config.restaurant_countdown_minute) || 0;

        const now = new Date();
        // Set the target time to the configured time of the next day
        const target = new Date(now);
        target.setHours(countdownHour, countdownMinute, 0, 0);

        // If it's already past the target time today, set target to the same time tomorrow
        if (now >= target) {
            target.setDate(target.getDate() + 1);
        }

        function update() {
            const now = new Date();
            const diff = target - now;

            if (diff <= 0) {
                // If countdown reaches zero, reset for the next day
                target.setDate(target.getDate() + 1);
                update();
                return;
            }

            // Calculate hours, minutes, and seconds
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((diff % (1000 * 60)) / 1000);

            // Format as HH:MM:SS
            timeElement.textContent = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        }

        // Update immediately and then every second
        update();
        setInterval(update, 1000);
    }

    document.addEventListener('DOMContentLoaded', function () {
        applyNightModeClass();
        renderRestaurantLevel();
        updateCountdown();
        initDailyChallenge();
        // Update challenge progress on initial load
        if (typeof updateChallengeProgress === 'function') {
            updateChallengeProgress();
        }
        // Add tab switching for the history section
        const tabs = document.querySelectorAll('.history-tab');
        if (tabs.length > 0) {
            tabs.forEach(tab => {
                tab.addEventListener('click', (e) => {
                    e.preventDefault();
                    const target = tab.getAttribute('data-tab');

                    // Update active tab
                    document.querySelectorAll('.history-tab').forEach(t => t.classList.remove('active'));
                    tab.classList.add('active');

                    // Show target content
                    document.querySelectorAll('.tab-content').forEach(content => {
                        content.style.display = 'none';
                    });
                    document.getElementById(target).style.display = 'block';
                });
            });
        }

        if (typeof window.matchMedia === 'function') {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyNightModeClass);
        }
    });
})();
