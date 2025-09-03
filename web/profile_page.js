document.addEventListener('DOMContentLoaded', () => {
    const themeBtn = document.getElementById('nav-theme');
    const statsBtn = document.getElementById('nav-stats');
    const themePage = document.getElementById('page-theme');
    const statsPage = document.getElementById('page-stats');

    if (!themeBtn || !statsBtn || !themePage || !statsPage) return;

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

    themeBtn.addEventListener('click', showThemePage);
    statsBtn.addEventListener('click', showStatsPage);

    // Show the theme page by default
    showThemePage();
});

