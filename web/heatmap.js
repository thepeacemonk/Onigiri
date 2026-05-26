/*
    Onigiri Heatmap Renderer
    Draws the heatmap in year, month, and week views.
*/

window.OnigiriHeatmap = window.OnigiriHeatmap || {};

(function (exports) {
    "use strict";

    const state = {
        view: "year",
        targetDate: new Date(),
    };

    function prepareData(rawData) {
        return {
            reviewsByDay: new Map(Object.entries(rawData.calendar || {})),
            duesByDay: new Map(Object.entries(rawData.due_calendar || {})),
            todayKey: rawData.today_date_key,
            dailyAverage: rawData.daily_average || 0,
        };
    }

    function getIntensityLevel(count, dailyAverage) {
        if (count === 0) return 0;

        const avg = Math.max(dailyAverage, 5);

        if (count < 0.4 * avg) return 1;
        if (count < 0.7 * avg) return 2;
        if (count < 1.0 * avg) return 3;
        if (count < 1.3 * avg) return 4;
        if (count < 1.6 * avg) return 5;
        if (count < 2.0 * avg) return 6;
        if (count < 2.5 * avg) return 7;

        return 8;
    }

    function getDueIntensityLevel(count, dailyAverage) {
        if (count === 0) return 0;

        const avg = Math.max(dailyAverage, 5);

        if (count < 0.4 * avg) return 1;
        if (count < 0.7 * avg) return 2;
        if (count < 1.0 * avg) return 3;
        if (count < 1.3 * avg) return 4;
        if (count < 1.6 * avg) return 5;
        if (count < 2.0 * avg) return 6;
        if (count < 2.5 * avg) return 7;

        return 8;
    }

    function getLocalDateKey(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, "0");
        const day = String(date.getDate()).padStart(2, "0");
        return `${year}-${month}-${day}`;
    }

    function escapeAttr(value) {
        return String(value)
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function getWeekStartOffset(date, config) {
        const startsSunday = (config.heatmapWeekStart || "monday") === "sunday";
        return startsSunday ? date.getDay() : (date.getDay() + 6) % 7;
    }

    function orderedWeekdayLabels(config, longLabels) {
        const labels = longLabels
            ? ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
            : ["S", "M", "T", "W", "T", "F", "S"];
        if ((config.heatmapWeekStart || "monday") === "sunday") {
            return labels;
        }
        return labels.slice(1).concat(labels[0]);
    }

    function getCountsForDate(date, preparedData) {
        const dateKey = getLocalDateKey(date);
        return {
            reviewCount: preparedData.reviewsByDay.get(dateKey) || 0,
            dueCount: preparedData.duesByDay.get(dateKey) || 0,
        };
    }

    function createEmptyCell() {
        const emptyCell = document.createElement("div");
        emptyCell.className = "heatmap-day-cell empty";
        return emptyCell;
    }

    function applyShapeMask(shapeDiv, svgContent) {
        if (!svgContent) {
            return;
        }

        const dataUri = `url("data:image/svg+xml,${encodeURIComponent(svgContent)}")`;
        shapeDiv.style.webkitMaskImage = dataUri;
        shapeDiv.style.maskImage = dataUri;
        shapeDiv.style.webkitMaskSize = "contain";
        shapeDiv.style.maskSize = "contain";
        shapeDiv.style.webkitMaskRepeat = "no-repeat";
        shapeDiv.style.maskRepeat = "no-repeat";
        shapeDiv.style.webkitMaskPosition = "50% 50%";
        shapeDiv.style.maskPosition = "50% 50%";
    }

    function createCell(date, reviewCount, dueCount, config, todayKey, dailyAverage) {
        const cell = document.createElement("div");
        cell.className = "heatmap-day-cell";

        const dateKey = getLocalDateKey(date);
        const dateText = date.toLocaleDateString(undefined, {
            weekday: "long",
            year: "numeric",
            month: "long",
            day: "numeric",
        });

        let tooltipText;

        if (dateKey === todayKey) {
            cell.classList.add("today");
            cell.dataset.reviewCount = reviewCount;
            cell.dataset.level = getIntensityLevel(reviewCount, dailyAverage);
            tooltipText = `${reviewCount} review${reviewCount !== 1 ? "s" : ""} done today`;
        } else if (dateKey < todayKey) {
            cell.dataset.reviewCount = reviewCount;
            cell.dataset.level = getIntensityLevel(reviewCount, dailyAverage);
            tooltipText = `${reviewCount} review${reviewCount !== 1 ? "s" : ""} on ${dateText}`;
        } else {
            cell.classList.add("future-day");
            cell.dataset.dueCount = dueCount;
            cell.dataset.dueLevel = getDueIntensityLevel(dueCount, dailyAverage);
            tooltipText = `${dueCount} review${dueCount !== 1 ? "s" : ""} due on ${dateText}`;
        }

        const shapeDiv = document.createElement("div");
        shapeDiv.className = "day-shape";
        applyShapeMask(shapeDiv, config.heatmapSvgContent);

        cell.appendChild(shapeDiv);
        cell.setAttribute("data-tooltip", tooltipText);
        return cell;
    }

    function drawYearView(gridContainer, preparedData, config) {
        gridContainer.className = "heatmap-grid year-view";
        gridContainer.dataset.monthsHidden = !config.heatmapShowMonths;
        gridContainer.dataset.weekdaysHidden = !config.heatmapShowWeekdays;

        const year = state.targetDate.getFullYear();
        const firstDayOfYear = new Date(year, 0, 1);

        gridContainer.innerHTML = `
            <div class="heatmap-months"></div>
            <div class="heatmap-weekdays">${orderedWeekdayLabels(config, false).map(label => `<div>${label}</div>`).join("")}</div>
            <div class="heatmap-cells"></div>
        `;

        const cellsContainer = gridContainer.querySelector(".heatmap-cells");
        const monthsContainer = gridContainer.querySelector(".heatmap-months");
        let currentMonth = -1;

        for (let i = 0; i < 371; i++) {
            const dayOfWeek = getWeekStartOffset(firstDayOfYear, config);
            const date = new Date(firstDayOfYear);
            date.setDate(firstDayOfYear.getDate() - dayOfWeek + i);

            if (date.getFullYear() !== year) {
                cellsContainer.appendChild(createEmptyCell());
                continue;
            }

            if (date.getDate() === 1 && date.getMonth() !== currentMonth) {
                currentMonth = date.getMonth();
                const monthLabel = document.createElement("div");
                monthLabel.className = "month-label";
                monthLabel.textContent = date.toLocaleString("default", { month: "short" });
                monthLabel.style.gridColumn = Math.floor(i / 7) + 1;
                monthsContainer.appendChild(monthLabel);
            }

            const { reviewCount, dueCount } = getCountsForDate(date, preparedData);
            cellsContainer.appendChild(
                createCell(date, reviewCount, dueCount, config, preparedData.todayKey, preparedData.dailyAverage)
            );
        }
    }

    function drawMonthView(gridContainer, preparedData, config) {
        gridContainer.className = "heatmap-grid month-view";
        gridContainer.dataset.weekdaysHidden = !config.heatmapShowWeekdays;

        const year = state.targetDate.getFullYear();
        const month = state.targetDate.getMonth();
        const firstDayOfMonth = new Date(year, month, 1);

        gridContainer.innerHTML = `
            <div class="month-weekdays-header">${orderedWeekdayLabels(config, true).map(label => `<div>${label}</div>`).join("")}</div>
            <div class="month-cells-grid"></div>
        `;

        const cellsContainer = gridContainer.querySelector(".month-cells-grid");
        const firstDayOfWeek = getWeekStartOffset(firstDayOfMonth, config);

        for (let i = 0; i < firstDayOfWeek; i++) {
            cellsContainer.appendChild(createEmptyCell());
        }

        const lastDayOfMonth = new Date(year, month + 1, 0).getDate();
        for (let day = 1; day <= lastDayOfMonth; day++) {
            const date = new Date(year, month, day);
            const { reviewCount, dueCount } = getCountsForDate(date, preparedData);
            cellsContainer.appendChild(
                createCell(date, reviewCount, dueCount, config, preparedData.todayKey, preparedData.dailyAverage)
            );
        }
    }

    function drawWeekView(gridContainer, preparedData, config) {
        gridContainer.className = "heatmap-grid week-view";
        gridContainer.dataset.headerHidden = !config.heatmapShowWeekHeader;

        const startDate = new Date(state.targetDate);
        const startDayOfWeek = getWeekStartOffset(startDate, config);
        startDate.setDate(startDate.getDate() - startDayOfWeek);

        gridContainer.innerHTML = `
            <div class="week-days-header"></div>
            <div class="week-cells-grid"></div>
        `;

        const headerContainer = gridContainer.querySelector(".week-days-header");
        const cellsContainer = gridContainer.querySelector(".week-cells-grid");

        for (let i = 0; i < 7; i++) {
            const date = new Date(startDate);
            date.setDate(startDate.getDate() + i);

            const header = document.createElement("div");
            header.innerHTML = `
                <div class="weekday-label">${date.toLocaleString("default", { weekday: "short" })}</div>
                <div class="day-label">${date.getDate()}</div>
            `;
            headerContainer.appendChild(header);

            const { reviewCount, dueCount } = getCountsForDate(date, preparedData);
            cellsContainer.appendChild(
                createCell(date, reviewCount, dueCount, config, preparedData.todayKey, preparedData.dailyAverage)
            );
        }
    }

    function getSystemIconUrl(filename) {
        const addonPackage = window.ONIGIRI_CONFIG && window.ONIGIRI_CONFIG.addonPackage;
        return addonPackage ? `/_addons/${addonPackage}/system_files/system_icons/${filename}` : "";
    }

    function renderSystemIcon(className, filename) {
        const iconUrl = getSystemIconUrl(filename);
        return `<span class="heatmap-ui-icon heatmap-system-icon ${className}" style="mask-image:url('${iconUrl}');-webkit-mask-image:url('${iconUrl}');"></span>`;
    }

    function renderFlameIcon(hasStreak) {
        return renderSystemIcon(`heatmap-fire-icon ${hasStreak ? "active" : "inactive"}`, "fire.svg");
    }

    function renderYearChevron() {
        return renderSystemIcon("heatmap-year-chevron", "down.svg");
    }

    function buildNavContent(config) {
        const leftArrow = renderSystemIcon("heatmap-nav-icon-left", "left.svg");
        const rightArrow = renderSystemIcon("heatmap-nav-icon-right", "right.svg");

        if (state.view === "year") {
            return `
                <button class="nav-btn" data-nav="-1">${leftArrow}</button>
                <span class="nav-title">${state.targetDate.getFullYear()}</span>
                <button class="nav-btn" data-nav="1">${rightArrow}</button>
            `;
        }

        if (state.view === "month") {
            return `
                <button class="nav-btn" data-nav="-1">${leftArrow}</button>
                <span class="nav-title">${state.targetDate.toLocaleString("default", { month: "short", year: "numeric" })}</span>
                <button class="nav-btn" data-nav="1">${rightArrow}</button>
            `;
        }

        const startOfWeek = new Date(state.targetDate);
        startOfWeek.setDate(startOfWeek.getDate() - getWeekStartOffset(startOfWeek, config));
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);

        return `
            <button class="nav-btn" data-nav="-7">${leftArrow}</button>
            <span class="nav-title">${startOfWeek.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${endOfWeek.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
            <button class="nav-btn" data-nav="7">${rightArrow}</button>
        `;
    }

    function bindNavButtons(navEl) {
        navEl.addEventListener("click", (event) => {
            const btn = event.target.closest(".nav-btn");
            if (!btn) {
                return;
            }

            const amount = parseInt(btn.dataset.nav, 10);
            if (state.view === "year") {
                state.targetDate.setFullYear(state.targetDate.getFullYear() + amount);
            } else if (state.view === "month") {
                state.targetDate.setMonth(state.targetDate.getMonth() + amount);
            } else if (state.view === "week") {
                state.targetDate.setDate(state.targetDate.getDate() + amount);
            }

            renderCurrentView();
        });
    }

    let renderCurrentView = function () {};

    exports.render = function (containerId, data, config) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const preparedData = prepareData(data);

        if (config.heatmapDefaultView) {
            state.view = config.heatmapDefaultView;
        }

        renderCurrentView = function () {
            const i18n = config.i18n || {};
            const hasStreak = data.streak > 0;
            const longestStreak = data.longest_streak || 0;
            const longestStreakTip = longestStreak > 0
                ? `Longest streak: ${longestStreak} day${longestStreak !== 1 ? "s" : ""}`
                : "No streak yet";
            const streakMarkup = config.heatmapShowStreak
                ? `<div class="streak-counter onigiri-streak-tip" data-tooltip="${escapeAttr(longestStreakTip)}">${renderFlameIcon(hasStreak)}<span>${data.streak}</span></div>`
                : "";

            container.innerHTML = `
                <div class="onigiri-heatmap-header">
                    <div class="header-left">
                        <div class="heatmap-nav">${buildNavContent(config)}</div>
                    </div>
                    <div class="header-right">
                        ${streakMarkup}
                        <div class="heatmap-filters">
                            <button class="filter-btn ${state.view === "year" ? "active" : ""}" data-view="year">${i18n.year || "Year"}</button>
                            <button class="filter-btn ${state.view === "month" ? "active" : ""}" data-view="month">${i18n.month || "Month"}</button>
                            <button class="filter-btn ${state.view === "week" ? "active" : ""}" data-view="week">${i18n.week || "Week"}</button>
                        </div>
                    </div>
                </div>
                <div class="heatmap-grid"></div>
            `;

            const gridContainer = container.querySelector(".heatmap-grid");
            if (state.view === "year") {
                drawYearView(gridContainer, preparedData, config);
            } else if (state.view === "month") {
                drawMonthView(gridContainer, preparedData, config);
            } else {
                drawWeekView(gridContainer, preparedData, config);
            }

            const navEl = container.querySelector(".heatmap-nav");
            bindNavButtons(navEl);

            const filters = container.querySelector(".heatmap-filters");
            filters.addEventListener("click", (event) => {
                const btn = event.target.closest(".filter-btn");
                if (!btn) {
                    return;
                }
                state.view = btn.dataset.view;
                state.targetDate = new Date();
                renderCurrentView();
            });
        };

        renderCurrentView();
    };

    exports.autoRender = function () {
        if (window.onigiriHeatmapData && window.onigiriHeatmapConfig) {
            exports.render("onigiri-heatmap-container", window.onigiriHeatmapData, window.onigiriHeatmapConfig);
            if (typeof window.onigiriDismissOverlay === "function") {
                window.onigiriDismissOverlay("heatmap");
            }
            return true;
        }
        return false;
    };

    (function () {
        const tryAutoRender = () => {
            if (exports.autoRender()) {
                return;
            }

            let attempts = 0;
            const interval = setInterval(() => {
                attempts++;
                if (exports.autoRender() || attempts > 20) {
                    clearInterval(interval);
                }
            }, 100);
        };

        if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", tryAutoRender);
        } else {
            tryAutoRender();
        }
    })();
})(window.OnigiriHeatmap);
