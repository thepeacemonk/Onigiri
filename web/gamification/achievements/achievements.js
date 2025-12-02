(function () {
    function applyNightMode() {
        const body = document.body;
        if (!body) {
            return;
        }
        body.classList.toggle('night-mode', window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }

    function formatDate(timestamp) {
        if (!timestamp) {
            return '';
        }
        try {
            const date = new Date(timestamp * 1000);
            return date.toLocaleDateString();
        } catch (err) {
            return '';
        }
    }

    function updateRestaurantLevelSection(restaurantLevel) {
        const restaurantSection = document.querySelector('.restaurant-level-card[data-bind="restaurant-level"]');
        if (!restaurantSection) {
            return;
        }

        const summary = restaurantSection.querySelector('.restaurant-level-summary');
        const levelValue = restaurantSection.querySelector('[data-bind="rl-level"]');
        const xpLabel = restaurantSection.querySelector('[data-bind="rl-xp"]');
        const phraseLabel = restaurantSection.querySelector('[data-bind="rl-phrase"]');
        const progressFill = restaurantSection.querySelector('.restaurant-level-progress .rl-progress-fill');

        const enabledRL = Boolean(restaurantLevel && restaurantLevel.enabled);
        restaurantSection.dataset.enabled = enabledRL ? 'true' : 'false';
        if (summary) {
            summary.dataset.enabled = enabledRL ? 'true' : 'false';
        }

        if (!enabledRL) {
            return;
        }

        const levelNumber = restaurantLevel.level ?? 0;
        if (levelValue) {
            levelValue.textContent = levelNumber;
        }

        const xpInto = restaurantLevel.xpIntoLevel ?? 0;
        const xpNext = restaurantLevel.xpToNextLevel ?? 0;
        const totalXp = restaurantLevel.totalXp ?? 0;

        if (xpLabel) {
            if (xpNext > 0) {
                xpLabel.textContent = `${xpInto.toLocaleString()} / ${xpNext.toLocaleString()} XP`;
            } else {
                xpLabel.textContent = `${totalXp.toLocaleString()} XP total`;
            }
        }

        const phrase = restaurantLevel.phrase || 'Keep serving knowledge!';
        if (phraseLabel) {
            phraseLabel.textContent = phrase;
        }

        if (progressFill) {
            let fraction = Number(restaurantLevel.progressFraction || 0);
            if (!Number.isFinite(fraction) || fraction < 0) {
                fraction = 0;
            }
            if (fraction > 1) {
                fraction = 1;
            }
            if (xpNext <= 0) {
                fraction = 1;
            }
            progressFill.style.width = `${(fraction * 100).toFixed(1)}%`;
        }
    }

    function renderAchievements() {
        const data = window.ONIGIRI_ACHIEVEMENTS || {};
        const enabled = Boolean(data.enabled);
        const snapshot = data.snapshot || {};
        const metrics = snapshot.metrics || {};
        const achievements = snapshot.achievements || [];
        const customGoals = snapshot["custom_goals"] || [];
        const goals = snapshot.goals || [];
        const heatmap = snapshot.heatmap || {};
        const restaurantLevel = snapshot["restaurant_level"] || {};

        const body = document.querySelector('.achievements-page');
        if (!body) {
            return;
        }
        body.dataset.enabled = enabled ? 'true' : 'false';

        const ringValue = document.querySelector('.ring-value');
        if (ringValue) {
            const unlockedCount = achievements.filter((ach) => ach.unlocked).length;
            ringValue.textContent = unlockedCount;
        }

        const ringLabel = document.querySelector('.ring-label');
        if (ringLabel) {
            ringLabel.textContent = 'Unlocked';
        }

        const records = [
            {
                selector: '.record-card[data-record="streak"] .record-value',
                value: metrics.max_streak || 0,
            },
            {
                selector: '.record-card[data-record="streak"] .record-date',
                value: metrics.last_streak_day ? `As of ${formatDate(metrics.last_streak_day)}` : '',
            },
            {
                selector: '.record-card[data-record="max-reviews"] .record-value',
                value: metrics.max_daily_reviews || 0,
            },
            {
                selector: '.record-card[data-record="max-reviews"] .record-date',
                value: metrics.max_daily_reviews_date ? `Logged ${formatDate(metrics.max_daily_reviews_date)}` : '',
            },
            {
                selector: '.record-card[data-record="focus"] .record-value',
                value: metrics.longest_session_minutes || 0,
            },
            {
                selector: '.record-card[data-record="focus"] .record-date',
                value: metrics.longest_session_day ? `Set ${formatDate(metrics.longest_session_day)}` : '',
            },
        ];

        records.forEach(({ selector, value }) => {
            const el = document.querySelector(selector);
            if (el) {
                el.textContent = value;
            }
        });

        const awardGroupsContainer = document.querySelector('.award-groups[data-bind="awards"]');
        if (!awardGroupsContainer) {
            return;
        }

        const categoryDefinitions = [
            { id: 'streak_medals', title: 'Streak Medals' },
            { id: 'perfection', title: 'Perfection' },
            { id: 'culinary_master', title: 'Culinary Master' },
            { id: 'new_ingredients', title: 'New Ingredients' },
            { id: 'onigiri_restaurant', title: 'Onigiri Restaurant' },
            { id: 'special_recipes', title: 'Special Recipes' },
        ];

        awardGroupsContainer.innerHTML = '';

        const handledCategories = new Set();

        const createAwardCard = (achievement) => {
            const article = document.createElement('article');
            article.className = 'award-card';
            article.dataset.state = achievement.unlocked ? 'unlocked' : 'locked';

            const icon = document.createElement('div');
            icon.className = 'award-icon';
            if (achievement.icon && (achievement.icon.includes('/') || achievement.icon.includes('.'))) {
                const img = document.createElement('img');
                img.src = achievement.icon;
                img.style.height = '1.2em';
                img.style.width = 'auto';
                img.style.verticalAlign = 'middle';
                icon.appendChild(img);
            } else {
                icon.textContent = achievement.icon || '🍙';
            }

            const title = document.createElement('h3');
            title.className = 'award-title';
            title.textContent = achievement.name;

            const desc = document.createElement('p');
            desc.className = 'award-progress';
            desc.textContent = achievement.description;

            const progress = document.createElement('p');
            progress.className = 'award-progress';
            if (achievement.repeatable) {
                progress.textContent = achievement.unlocked ? 'Unlocked' : `Progress: ${achievement.progress || 0}/${achievement.threshold}`;
            } else if (!achievement.unlocked) {
                progress.textContent = `Progress: ${achievement.progress || 0}/${achievement.threshold}`;
            } else {
                progress.textContent = 'Unlocked';
            }

            const badgeCount = achievement.repeatable ? achievement.count : achievement.unlocked ? 1 : 0;
            if (badgeCount > 1) {
                const badge = document.createElement('span');
                badge.className = 'badge badge--repeat';
                badge.textContent = `${badgeCount}×`;
                article.appendChild(badge);
            }

            article.appendChild(icon);
            article.appendChild(title);
            article.appendChild(desc);
            article.appendChild(progress);

            return article;
        };

        const renderGroup = (groupId, title) => {
            const groupAchievements = achievements.filter((achievement) => achievement.category === groupId);
            if (!groupAchievements.length) {
                return;
            }

            handledCategories.add(groupId);

            const group = document.createElement('div');
            group.className = 'award-group';
            group.dataset.category = groupId;

            const heading = document.createElement('div');
            heading.className = 'award-group-heading';

            const headingTitle = document.createElement('h3');
            headingTitle.className = 'award-group-title';
            headingTitle.textContent = title;

            heading.appendChild(headingTitle);
            group.appendChild(heading);

            const grid = document.createElement('div');
            grid.className = 'award-grid';

            groupAchievements.forEach((achievement) => {
                grid.appendChild(createAwardCard(achievement));
            });

            group.appendChild(grid);
            awardGroupsContainer.appendChild(group);
        };

        categoryDefinitions.forEach(({ id, title }) => renderGroup(id, title));

        const remaining = achievements.filter((achievement) => !handledCategories.has(achievement.category));
        if (remaining.length) {
            const otherGroup = document.createElement('div');
            otherGroup.className = 'award-group';
            otherGroup.dataset.category = 'other';

            const otherHeading = document.createElement('div');
            otherHeading.className = 'award-group-heading';

            const otherTitle = document.createElement('h3');
            otherTitle.className = 'award-group-title';
            otherTitle.textContent = 'Other';

            otherHeading.appendChild(otherTitle);
            otherGroup.appendChild(otherHeading);

            const otherGrid = document.createElement('div');
            otherGrid.className = 'award-grid';

            remaining.forEach((achievement) => {
                otherGrid.appendChild(createAwardCard(achievement));
            });

            otherGroup.appendChild(otherGrid);
            awardGroupsContainer.appendChild(otherGroup);
        }

        function renderGoalList(container, items, emptyMessage, mapper) {
            if (!container) {
                return;
            }
            container.innerHTML = '';

            if (!items.length) {
                const emptyItem = document.createElement('li');
                emptyItem.className = 'goal-item goal-item--empty';
                emptyItem.textContent = emptyMessage;
                container.appendChild(emptyItem);
                return;
            }

            items.forEach((goal) => {
                const item = document.createElement('li');
                item.className = 'goal-item goal-item--custom';
                mapper(goal, item);
                container.appendChild(item);
            });
        }

        const customGoalsList = document.querySelector('.goal-list--custom[data-bind="custom-goals"]');
        renderGoalList(
            customGoalsList,
            customGoals,
            'No custom goals configured yet. Enable them in Onigiri Settings → Achievements.',
            (goal, item) => {
                const icon = document.createElement('span');
                icon.className = 'goal-icon';
                icon.setAttribute('aria-hidden', 'true');
                if (goal.icon && (goal.icon.includes('/') || goal.icon.includes('.'))) {
                    const img = document.createElement('img');
                    img.src = goal.icon;
                    img.style.height = '1.2em';
                    img.style.width = 'auto';
                    img.style.verticalAlign = 'middle';
                    icon.appendChild(img);
                } else {
                    icon.textContent = goal.icon || '🍙';
                }

                const copy = document.createElement('div');
                copy.className = 'goal-copy';

                const title = document.createElement('p');
                title.className = 'goal-title';
                title.textContent = goal.title || 'Goal';

                const detail = document.createElement('p');
                detail.className = 'goal-detail';

                const target = goal.target ?? 0;
                const progressValue = goal.progress ?? 0;
                const remaining = Math.max(target - progressValue, 0);
                const enabled = Boolean(goal.enabled);

                if (!enabled) {
                    item.classList.add('goal-item--disabled');
                    detail.textContent = 'Disabled. Enable this goal in settings to start tracking it.';
                } else if (!target) {
                    item.classList.add('goal-item--disabled');
                    detail.textContent = 'No target set yet. Increase the target value in settings to begin tracking.';
                } else {
                    const lines = [];
                    if (goal.period_label) {
                        lines.push(goal.period_label);
                    }
                    lines.push(remaining > 0 ? `${remaining} to go!` : 'Goal complete!');
                    detail.innerHTML = lines.join('<br>');
                }

                const status = document.createElement('span');
                status.className = 'goal-progress';

                if (!enabled || !target) {
                    status.classList.add('goal-progress--inactive');
                    status.textContent = '--';
                } else {
                    status.textContent = `${progressValue} / ${target}`;
                    if (remaining <= 0) {
                        item.classList.add('goal-item--complete');
                        status.textContent = `${target} ✓`;
                    }
                }

                const count = Number(goal.completion_count || 0);
                if (count === 1) {
                    const badge = document.createElement('span');
                    badge.className = 'goal-badge';
                    badge.textContent = `${count}×`;
                    badge.setAttribute('title', 'Times completed');
                    item.appendChild(badge);
                }

                copy.appendChild(title);
                copy.appendChild(detail);

                item.appendChild(icon);
                item.appendChild(copy);
                item.appendChild(status);
            }
        );

        const goalList = document.querySelector('.goal-list[data-bind="goals"]');
        renderGoalList(
            goalList,
            goals,
            'No achievements in progress yet. Keep reviewing to start new goals!',
            (goal, item) => {
                const icon = document.createElement('span');
                icon.className = 'goal-icon';
                icon.setAttribute('aria-hidden', 'true');
                if (goal.icon && (goal.icon.includes('/') || goal.icon.includes('.'))) {
                    const img = document.createElement('img');
                    img.src = goal.icon;
                    img.style.height = '1.2em';
                    img.style.width = 'auto';
                    img.style.verticalAlign = 'middle';
                    icon.appendChild(img);
                } else {
                    icon.textContent = goal.icon || '🍙';
                }

                const copy = document.createElement('div');
                copy.className = 'goal-copy';

                const title = document.createElement('p');
                title.className = 'goal-title';
                title.textContent = goal.name || 'Achievement';

                const detail = document.createElement('p');
                detail.className = 'goal-detail';
                detail.textContent = goal.description || '';

                copy.appendChild(title);
                if (goal.description) {
                    copy.appendChild(detail);
                }

                const progress = document.createElement('span');
                progress.className = 'goal-progress';
                const current = goal.progress ?? 0;
                const threshold = goal.threshold ?? 0;
                const remaining = goal.remaining ?? Math.max(threshold - current, 0);
                const progressLabel = threshold > 0 ? `${current} / ${threshold}` : `${current}`;
                progress.textContent = remaining > 0 ? `${progressLabel}` : progressLabel;

                item.appendChild(icon);
                item.appendChild(copy);
                item.appendChild(progress);
            }
        );
    }

    document.addEventListener('DOMContentLoaded', () => {
        applyNightMode();
        renderAchievements();

        if (typeof window.matchMedia === 'function') {
            window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyNightMode);
        }
    });
})();
