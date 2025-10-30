/**
 * Sidebar resize functionality
 * Allows users to drag the sidebar border to resize it
 */

// Wait for DOM to be ready
if (!window.dash_clientside) {
    window.dash_clientside = {};
}

window.dash_clientside.sidebar = {
    /**
     * Initialize sidebar resize functionality
     */
    initResize: function() {
        // Get elements
        const sidebar = document.getElementById('sidebar');
        const resizeHandle = document.getElementById('sidebar-resize-handle');
        
        if (!sidebar || !resizeHandle) {
            console.log('Sidebar resize: Elements not found yet');
            return window.dash_clientside.no_update;
        }
        
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;
        
        // Minimum and maximum widths
        const minWidth = window.innerWidth * 0.05; // 5% of screen width
        const maxWidth = window.innerWidth * 0.5; // 50% of screen width
        
        // Mouse down on resize handle
        resizeHandle.addEventListener('mousedown', function(e) {
            isResizing = true;
            startX = e.clientX;
            startWidth = parseInt(window.getComputedStyle(sidebar).width, 10);
            
            // Prevent text selection while dragging
            e.preventDefault();
            document.body.style.cursor = 'ew-resize';
            document.body.style.userSelect = 'none';
        });
        
        // Mouse move
        document.addEventListener('mousemove', function(e) {
            if (!isResizing) return;
            
            const delta = e.clientX - startX;
            let newWidth = startWidth + delta;
            
            // Constrain to min/max
            newWidth = Math.max(minWidth, Math.min(newWidth, maxWidth));
            
            sidebar.style.width = newWidth + 'px';
        });
        
        // Mouse up
        document.addEventListener('mouseup', function(e) {
            if (!isResizing) return;
            
            isResizing = false;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
            
            // Store the new width in sidebar-state
            const newWidth = parseInt(window.getComputedStyle(sidebar).width, 10);
            console.log('Sidebar resized to:', newWidth);
        });
        
        console.log('Sidebar resize initialized');
        return window.dash_clientside.no_update;
    }
};

// Initialize when page loads
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(function() {
        window.dash_clientside.sidebar.initResize();
    }, 500);
});
