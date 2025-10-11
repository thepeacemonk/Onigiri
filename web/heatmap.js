/*
    Onigiri Heatmap Renderer
    This script is responsible for drawing the heatmap graph based on review data,
    with different views for Year, Month, and Week.
*/

// Ensure the OnigiriHeatmap object exists
window.OnigiriHeatmap = window.OnigiriHeatmap || {};

(function (exports) {
    "use strict";

    // --- STATE MANAGEMENT & CACHE ---
    let state = {
        view: 'year', // 'year', 'month', 'week'
        targetDate: new Date(),
    };

    // --- DATA PREPARATION ---
    function prepareData(rawData) {
        const reviewsByDay = new Map();
        let maxReviews = 0;
        for (const dayNumStr in rawData) {
            const dayNum = parseInt(dayNumStr, 10);
            // This creates a date object at midnight UTC for the given day number.
            // Python has already calculated the correct "Anki day" (with rollover),
            // so we don't need to do any extra timezone math here.
            const date = new Date(dayNum * 86400 * 1000);

            // .toISOString() correctly gives us the UTC date string (e.g., '2025-09-05')
            // which we use as a key.
            const dateKey = date.toISOString().slice(0, 10);
            
            const count = rawData[dayNumStr];
            reviewsByDay.set(dateKey, count);
            if (count > maxReviews) {
                maxReviews = count;
            }
        }
        return { reviewsByDay, maxReviews };
    }

    // This function calculates a 0-1 intensity factor based on specific card count thresholds.
    function createIntensityScale() {
        return (count) => {
            if (count >= 300) return 1.0;  // 100%
            
            if (count >= 100) return 0.6;  // 60% 
            
            if (count >= 1) return 0.3;    // 30% 
            return 0; // 0% for 0
        };
    }

    // --- VIEW RENDERERS ---

    function drawYearView(gridContainer, preparedData, intensityScale, config) {
        gridContainer.className = 'heatmap-grid year-view';
        gridContainer.dataset.monthsHidden = !config.heatmapShowMonths;
        gridContainer.dataset.weekdaysHidden = !config.heatmapShowWeekdays;

        const target = state.targetDate;
        const year = target.getFullYear();
        const firstDayOfYear = new Date(year, 0, 1);

        let html = `
            <div class="heatmap-months"></div>
            <div class="heatmap-weekdays"><div>M</div><div>T</div><div>W</div><div>T</div><div>F</div><div>S</div><div>S</div></div>
            <div class="heatmap-cells"></div>
        `;
        gridContainer.innerHTML = html;

        const cellsContainer = gridContainer.querySelector('.heatmap-cells');
        const monthsContainer = gridContainer.querySelector('.heatmap-months');
        let currentMonth = -1;

        for (let i = 0; i < 371; i++) {
            const dayOfWeek = (firstDayOfYear.getDay() + 6) % 7;
            const date = new Date(firstDayOfYear);
            date.setDate(firstDayOfYear.getDate() - dayOfWeek + i);

            if (date.getFullYear() !== year) {
                const emptyCell = document.createElement('div');
                emptyCell.className = 'heatmap-day-cell empty';
                cellsContainer.appendChild(emptyCell);
                continue;
            }

            if (date.getDate() === 1 && date.getMonth() !== currentMonth) {
                currentMonth = date.getMonth();
                const monthLabel = document.createElement('div');
                monthLabel.className = 'month-label';
                monthLabel.textContent = date.toLocaleString('default', { month: 'short' });
                monthLabel.style.gridColumn = Math.floor(i / 7) + 1;
                monthsContainer.appendChild(monthLabel);
            }

            const dateKey = date.toISOString().slice(0, 10);
            const reviewCount = preparedData.reviewsByDay.get(dateKey) || 0;
            const cell = createCell(date, reviewCount, intensityScale, config);
            cellsContainer.appendChild(cell);
        }
    }

    function drawMonthView(gridContainer, preparedData, intensityScale, config) {
        gridContainer.className = 'heatmap-grid month-view';
        gridContainer.dataset.weekdaysHidden = !config.heatmapShowWeekdays;
        const target = state.targetDate;
        const year = target.getFullYear();
        const month = target.getMonth();
        const firstDayOfMonth = new Date(year, month, 1);

        let html = `
            <div class="month-weekdays-header"><div>Mon</div><div>Tue</div><div>Wed</div><div>Thu</div><div>Fri</div><div>Sat</div><div>Sun</div></div>
            <div class="month-cells-grid"></div>
        `;
        gridContainer.innerHTML = html;
        const cellsContainer = gridContainer.querySelector('.month-cells-grid');

        const firstDayOfWeek = (firstDayOfMonth.getDay() + 6) % 7;
        for (let i = 0; i < firstDayOfWeek; i++) {
            const emptyCell = document.createElement('div');
            emptyCell.className = 'heatmap-day-cell empty';
            cellsContainer.appendChild(emptyCell);
        }

        const lastDayOfMonth = new Date(year, month + 1, 0).getDate();
        for (let i = 1; i <= lastDayOfMonth; i++) {
            const date = new Date(year, month, i);
            const dateKey = date.toISOString().slice(0, 10);
            const reviewCount = preparedData.reviewsByDay.get(dateKey) || 0;
            const cell = createCell(date, reviewCount, intensityScale, config);
            cellsContainer.appendChild(cell);
        }
    }

    function drawWeekView(gridContainer, preparedData, intensityScale, config) {
        gridContainer.className = 'heatmap-grid week-view';
        gridContainer.dataset.headerHidden = !config.heatmapShowWeekHeader;
        const target = state.targetDate;
        const startDate = new Date(target);
        const startDayOfWeek = (target.getDay() + 6) % 7;
        startDate.setDate(startDate.getDate() - startDayOfWeek);

        let html = `
            <div class="week-days-header"></div>
            <div class="week-cells-grid"></div>
        `;
        gridContainer.innerHTML = html;

        const headerContainer = gridContainer.querySelector('.week-days-header');
        const cellsContainer = gridContainer.querySelector('.week-cells-grid');

        for (let i = 0; i < 7; i++) {
            const date = new Date(startDate);
            date.setDate(startDate.getDate() + i);

            const header = document.createElement('div');
            header.innerHTML = `
                <div class="weekday-label">${date.toLocaleString('default', { weekday: 'short' })}</div>
                <div class="day-label">${date.getDate()}</div>
            `;
            headerContainer.appendChild(header);

            const dateKey = date.toISOString().slice(0, 10);
            const reviewCount = preparedData.reviewsByDay.get(dateKey) || 0;
            const cell = createCell(date, reviewCount, intensityScale, config);
            cellsContainer.appendChild(cell);
        }
    }

    function createCell(date, reviewCount, intensityScale, config) {
        const cell = document.createElement('div');
        cell.className = 'heatmap-day-cell';
        cell.dataset.reviewCount = reviewCount;
        
        // Set the intensity as a CSS custom property. CSS will handle the rest.
        const intensity = intensityScale(reviewCount);
        cell.style.setProperty('--heatmap-intensity', intensity.toFixed(3));

        const shapeDiv = document.createElement('div');
        shapeDiv.className = 'day-shape';

        // The SVG mask logic remains unchanged.
        if (config.heatmapSvgContent) {
            const encodedSvg = encodeURIComponent(config.heatmapSvgContent);
            const dataUri = `url("data:image/svg+xml,${encodedSvg}")`;
            shapeDiv.style.webkitMaskImage = dataUri;
            shapeDiv.style.maskImage = dataUri;
            shapeDiv.style.webkitMaskSize = 'contain';
            shapeDiv.style.maskSize = 'contain';
            shapeDiv.style.webkitMaskRepeat = 'no-repeat';
            shapeDiv.style.maskRepeat = 'no-repeat';
            shapeDiv.style.webkitMaskPosition = 'center';
            shapeDiv.style.maskPosition = 'center';
        }
        cell.appendChild(shapeDiv);

        const tooltipText = `${reviewCount} reviews on ${date.toLocaleDateString(undefined, { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}`;
        cell.setAttribute('data-tooltip', tooltipText);
        return cell;
    }

    // --- MAIN RENDER FUNCTION ---
    exports.render = function (containerId, data, config) {
        const container = document.getElementById(containerId);
        if (!container) return;

        const preparedData = prepareData(data.calendar);
        const intensityScale = createIntensityScale();

        function draw() {
            const streakHTML = config.heatmapShowStreak ? `<div class="streak-counter">${data.streak} day streak</div>` : '';

            let navHTML = '';
            if (state.view === 'year') {
                navHTML = `
                    <button class="nav-btn" data-nav="-1">◄</button>
                    <span class="nav-title">${state.targetDate.getFullYear()}</span>
                    <button class="nav-btn" data-nav="1">►</button>
                `;
            } else if (state.view === 'month') {
                navHTML = `
                    <button class="nav-btn" data-nav="-1">◄</button>
                    <span class="nav-title">${state.targetDate.toLocaleString('default', { month: 'long', year: 'numeric' })}</span>
                    <button class="nav-btn" data-nav="1">►</button>
                `;
            } else if (state.view === 'week') {
                const startOfWeek = new Date(state.targetDate);
                startOfWeek.setDate(startOfWeek.getDate() - (startOfWeek.getDay() + 6) % 7);
                const endOfWeek = new Date(startOfWeek);
                endOfWeek.setDate(startOfWeek.getDate() + 6);
                navHTML = `
                    <button class="nav-btn" data-nav="-7">◄</button>
                    <span class="nav-title">${startOfWeek.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} - ${endOfWeek.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>
                    <button class="nav-btn" data-nav="7">►</button>
                `;
            }

            container.innerHTML = `
                <div class="onigiri-heatmap-header">
                    <div class="header-left">
                        <h3>Activity</h3>
                        <div class="heatmap-nav">${navHTML}</div>
                    </div>
                    <div class="header-right">
                        ${streakHTML}
                        <div class="heatmap-filters">
                            <button class="filter-btn ${state.view === 'year' ? 'active' : ''}" data-view="year">Year</button>
                            <button class="filter-btn ${state.view === 'month' ? 'active' : ''}" data-view="month">Month</button>
                            <button class="filter-btn ${state.view === 'week' ? 'active' : ''}" data-view="week">Week</button>
                        </div>
                    </div>
                </div>
                <div class="heatmap-grid"></div>
            `;

            const gridContainer = container.querySelector('.heatmap-grid');
            if (state.view === 'year') {
                drawYearView(gridContainer, preparedData, intensityScale, config);
            } else if (state.view === 'month') {
                drawMonthView(gridContainer, preparedData, intensityScale, config);
            } else if (state.view === 'week') {
                drawWeekView(gridContainer, preparedData, intensityScale, config);
            }

            container.querySelector('.heatmap-filters').addEventListener('click', (e) => {
                if (e.target.classList.contains('filter-btn')) {
                    state.view = e.target.dataset.view;
                    state.targetDate = new Date();
                    draw();
                }
            });

            container.querySelector('.heatmap-nav').addEventListener('click', (e) => {
                if (e.target.classList.contains('nav-btn')) {
                    const navAmount = parseInt(e.target.dataset.nav, 10);
                    if (state.view === 'year') {
                        state.targetDate.setFullYear(state.targetDate.getFullYear() + navAmount);
                    } else if (state.view === 'month') {
                        state.targetDate.setMonth(state.targetDate.getMonth() + navAmount);
                    } else if (state.view === 'week') {
                        state.targetDate.setDate(state.targetDate.getDate() + navAmount);
                    }
                    draw();
                }
            });
        }

        draw();
    };

})(window.OnigiriHeatmap);