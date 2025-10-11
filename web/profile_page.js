document.addEventListener('DOMContentLoaded', () => {
    // --- Element References ---
    const themeBtn = document.getElementById('nav-theme');
    const statsBtn = document.getElementById('nav-stats');
    const themePage = document.getElementById('page-theme');
    const statsPage = document.getElementById('page-stats');
    const exportBtn = document.getElementById('export-btn');

    if (!themeBtn || !statsBtn || !themePage || !statsPage || !exportBtn) {
        return;
    }

    // --- Page Switching Functions ---
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
    showThemePage();
    
    // --- NEW, SIMPLER EXPORT FUNCTION ---
    function exportFullPage() {
        // Target our new top-level container
        const elementToCapture = document.querySelector('.onigiri-profile-page');
        if (!elementToCapture) return;

        const options = {
            useCORS: true,
        };

        html2canvas(elementToCapture, options)
            .then(canvas => {
                const imageData = canvas.toDataURL("image/png");
                pycmd("saveImage:" + imageData);
            })
            .catch(error => {
                alert("Error rendering image: " + error);
            });
    }
    
    exportBtn.addEventListener('click', exportFullPage);
});