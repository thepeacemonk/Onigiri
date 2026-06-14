window.OnigiriProfilePage = (function () {
    function init(root) {
        const scope = root || document;
        const themeBtn = scope.querySelector('#nav-theme');
        const statsBtn = scope.querySelector('#nav-stats');
        const themePage = scope.querySelector('#page-theme');
        const statsPage = scope.querySelector('#page-stats');

        if (!themeBtn || !statsBtn || !themePage || !statsPage) {
            return;
        }

        function showThemePage() {
            themePage.style.display = 'block';
            statsPage.style.display = 'none';
            themeBtn.classList.add('active');
            statsBtn.classList.remove('active');
        }

        function showStatsPage() {
            themePage.style.display = 'none';
            statsPage.style.display = 'block';
            themeBtn.classList.remove('active');
            statsBtn.classList.add('active');
        }

        if (!themeBtn.dataset.profileBound) {
            themeBtn.dataset.profileBound = 'true';
            themeBtn.addEventListener('click', showThemePage);
        }
        if (!statsBtn.dataset.profileBound) {
            statsBtn.dataset.profileBound = 'true';
            statsBtn.addEventListener('click', showStatsPage);
        }
        showThemePage();
    }

    document.addEventListener('DOMContentLoaded', () => init(document));

    return { init };
})();
