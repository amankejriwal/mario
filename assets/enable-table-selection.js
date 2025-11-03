// Force enable text selection in Dash DataTables
// This overrides Dash's default behavior that prevents text selection

(function() {
    console.log('Loading text selection override for DataTables...');
    
    // Function to enable text selection on table elements
    function enableTextSelection() {
        // Find all DataTable containers
        const containers = document.querySelectorAll('.dash-table-container');
        
        if (containers.length === 0) {
            console.log('No DataTables found yet');
            return;
        }
        
        console.log(`Found ${containers.length} DataTable(s), enabling text selection...`);
        
        containers.forEach(container => {
            // Apply styles to container
            container.style.userSelect = 'text';
            container.style.webkitUserSelect = 'text';
            container.style.cursor = 'text';
            
            // Find all cell elements
            const cells = container.querySelectorAll('td, th, .dash-cell, div[role="gridcell"]');
            
            console.log(`  Processing ${cells.length} cells`);
            
            cells.forEach(cell => {
                // Force text selection CSS
                cell.style.userSelect = 'text';
                cell.style.webkitUserSelect = 'text';
                cell.style.mozUserSelect = 'text';
                cell.style.msUserSelect = 'text';
                cell.style.cursor = 'text';
                
                // Also apply to child divs
                const childDivs = cell.querySelectorAll('div');
                childDivs.forEach(div => {
                    div.style.userSelect = 'text';
                    div.style.webkitUserSelect = 'text';
                    div.style.cursor = 'text';
                });
            });
        });
        
        console.log('Text selection enabled for all DataTables');
    }
    
    // Run immediately
    enableTextSelection();
    
    // Run after short delays to catch dynamically loaded content
    setTimeout(enableTextSelection, 500);
    setTimeout(enableTextSelection, 1000);
    setTimeout(enableTextSelection, 2000);
    
    // Watch for DOM changes
    const observer = new MutationObserver(function(mutations) {
        let hasNewTable = false;
        
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType === 1) { // Element
                    if (node.classList && node.classList.contains('dash-table-container')) {
                        hasNewTable = true;
                        break;
                    }
                    if (node.querySelector && node.querySelector('.dash-table-container')) {
                        hasNewTable = true;
                        break;
                    }
                }
            }
            if (hasNewTable) break;
        }
        
        if (hasNewTable) {
            console.log('New DataTable detected, applying text selection...');
            setTimeout(enableTextSelection, 100);
        }
    });
    
    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    console.log('DataTable text selection override loaded and observing');
})();
