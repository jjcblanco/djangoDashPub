document.addEventListener('DOMContentLoaded', function() {
    // Elementos del DOM
    const sidebar = document.getElementById('sidebar');
    const mainContent = document.getElementById('mainContent');
    const toggleSidebarBtn = document.getElementById('toggleSidebar');
    const closeSidebarBtn = document.getElementById('closeSidebar');
    const mobileSidebarToggler = document.getElementById('mobileSidebarToggler');
    
    // Estado del sidebar
    let sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    
    // Inicializar
    initializeSidebar();
    
    // Event Listeners
    function initializeSidebar() {
        // Aplicar estado inicial
        updateSidebarState();
        
        // Toggle sidebar en desktop
        if (toggleSidebarBtn) {
            toggleSidebarBtn.addEventListener('click', toggleSidebar);
        }
        
        // Cerrar sidebar con botón X
        if (closeSidebarBtn) {
            closeSidebarBtn.addEventListener('click', closeSidebar);
        }
        
        // Toggle sidebar en móvil
        if (mobileSidebarToggler) {
            mobileSidebarToggler.addEventListener('click', toggleMobileSidebar);
        }
        
        // Cerrar sidebar en móvil al hacer clic fuera
        document.addEventListener('click', closeMobileSidebarOnClickOutside);
        
        // Ajustar en resize de ventana
        window.addEventListener('resize', handleResize);
    }
    
    // Funciones
    function toggleSidebar() {
        sidebarCollapsed = !sidebarCollapsed;
        localStorage.setItem('sidebarCollapsed', sidebarCollapsed);
        updateSidebarState();
    }
    
    function closeSidebar() {
        sidebarCollapsed = true;
        localStorage.setItem('sidebarCollapsed', sidebarCollapsed);
        updateSidebarState();
    }
    
    function toggleMobileSidebar() {
        sidebar.classList.toggle('show-mobile');
    }
    
    function closeMobileSidebarOnClickOutside(event) {
        if (window.innerWidth <= 768) {
            const isClickInsideSidebar = sidebar.contains(event.target);
            const isClickOnMobileToggler = mobileSidebarToggler.contains(event.target);
            
            if (!isClickInsideSidebar && !isClickOnMobileToggler && sidebar.classList.contains('show-mobile')) {
                sidebar.classList.remove('show-mobile');
            }
        }
    }
    
    function updateSidebarState() {
        if (window.innerWidth > 768) {
            if (sidebarCollapsed) {
                sidebar.classList.add('collapsed');
                mainContent.classList.add('expanded');
                if (toggleSidebarBtn) {
                    toggleSidebarBtn.innerHTML = '<i class="fas fa-bars"></i>';
                }
            } else {
                sidebar.classList.remove('collapsed');
                mainContent.classList.remove('expanded');
                if (toggleSidebarBtn) {
                    toggleSidebarBtn.innerHTML = '<i class="fas fa-times"></i>';
                }
            }
        }
    }
    
    function handleResize() {
        if (window.innerWidth <= 768) {
            sidebar.classList.remove('collapsed');
            mainContent.classList.remove('expanded');
        } else {
            updateSidebarState();
        }
    }
});