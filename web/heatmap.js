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
            <div class="heatmap-weekdays"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div>
            <div class="heatmap-cells"></div>
        `;

        const cellsContainer = gridContainer.querySelector(".heatmap-cells");
        const monthsContainer = gridContainer.querySelector(".heatmap-months");
        let currentMonth = -1;

        for (let i = 0; i < 371; i++) {
            const dayOfWeek = (firstDayOfYear.getDay() + 6) % 7;
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
            <div class="month-weekdays-header"><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div><div>Sun</div></div>
            <div class="month-cells-grid"></div>
        `;

        const cellsContainer = gridContainer.querySelector(".month-cells-grid");
        const firstDayOfWeek = (firstDayOfMonth.getDay() + 6) % 7;

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
        const startDayOfWeek = (startDate.getDay() + 6) % 7;
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

    function buildYearNavContent(data) {
        const today = new Date();
        const currentYear = today.getFullYear();
        const selectedYear = state.targetDate.getFullYear();
        const firstYear = data.firstYear && data.firstYear <= currentYear ? data.firstYear : currentYear;

        let items = "";
        for (let year = currentYear; year >= firstYear; year--) {
            items += `<div class="year-dropdown-item${year === selectedYear ? " selected" : ""}" data-year="${year}">${year}</div>`;
        }

        return `<div class="year-select-wrapper"><button class="year-select-btn">${selectedYear}${renderYearChevron()}</button><div class="year-dropdown-menu">${items}</div></div>`;
    }

    function buildNavContent(data) {
        const leftArrow = renderSystemIcon("heatmap-nav-icon-left", "down.svg");
        const rightArrow = renderSystemIcon("heatmap-nav-icon-right", "down.svg");

        if (state.view === "year") {
            return buildYearNavContent(data);
        }

        if (state.view === "month") {
            return `
                <button class="nav-btn" data-nav="-1">${leftArrow}</button>
                <span class="nav-title">${state.targetDate.toLocaleString("default", { month: "short", year: "numeric" })}</span>
                <button class="nav-btn" data-nav="1">${rightArrow}</button>
            `;
        }

        const startOfWeek = new Date(state.targetDate);
        startOfWeek.setDate(startOfWeek.getDate() - ((startOfWeek.getDay() + 6) % 7));
        const endOfWeek = new Date(startOfWeek);
        endOfWeek.setDate(startOfWeek.getDate() + 6);

        return `
            <button class="nav-btn" data-nav="-7">${leftArrow}</button>
            <span class="nav-title">${startOfWeek.toLocaleDateString(undefined, { month: "short", day: "numeric" })} - ${endOfWeek.toLocaleDateString(undefined, { month: "short", day: "numeric" })}</span>
            <button class="nav-btn" data-nav="7">${rightArrow}</button>
        `;
    }

    function bindYearDropdown(navEl) {
        const yearWrapper = navEl.querySelector(".year-select-wrapper");
        if (!yearWrapper) {
            return;
        }

        const yearBtn = yearWrapper.querySelector(".year-select-btn");
        const yearMenu = yearWrapper.querySelector(".year-dropdown-menu");

        yearBtn.addEventListener("click", (event) => {
            event.stopPropagation();
            const isOpen = yearMenu.classList.contains("open");
            yearMenu.classList.toggle("open", !isOpen);
            yearBtn.classList.toggle("open", !isOpen);

            if (!isOpen) {
                setTimeout(() => {
                    document.addEventListener("click", function onDocClick(docEvent) {
                        if (!yearWrapper.contains(docEvent.target)) {
                            yearMenu.classList.remove("open");
                            yearBtn.classList.remove("open");
                        }
                        document.removeEventListener("click", onDocClick);
                    });
                }, 0);
            }
        });

        yearMenu.querySelectorAll(".year-dropdown-item").forEach((item) => {
            item.addEventListener("click", (event) => {
                event.stopPropagation();
                state.targetDate.setFullYear(parseInt(item.dataset.year, 10));
                yearMenu.classList.remove("open");
                yearBtn.classList.remove("open");
                renderCurrentView();
            });
        });
    }

    function bindNavButtons(navEl) {
        navEl.addEventListener("click", (event) => {
            const btn = event.target.closest(".nav-btn");
            if (!btn) {
                return;
            }

            const amount = parseInt(btn.dataset.nav, 10);
            if (state.view === "month") {
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
            const hasStreak = data.streak > 0;
            const longestStreak = data.longest_streak || 0;
            const streakTooltip = longestStreak > 0
                ? `Longest streak: ${longestStreak} day${longestStreak !== 1 ? "s" : ""}`
                : "No streak yet";
            const streakMarkup = config.heatmapShowStreak
                ? `<div class="streak-counter onigiri-streak-tip" data-tooltip="${streakTooltip}">${renderFlameIcon(hasStreak)}${data.streak}</div>`
                : "";

            container.innerHTML = `
                <div class="heatmap-nav">
                    ${buildNavContent(data)}
                    ${streakMarkup}
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
            bindYearDropdown(navEl);
            bindNavButtons(navEl);
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
