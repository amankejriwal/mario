// Auto-focus Mario game iframe when it appears
const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        mutation.addedNodes.forEach((node) => {
            if (node.nodeType === 1) {
                const marioIframe = node.querySelector('#mario-game-iframe') || 
                                   (node.id === 'mario-game-iframe' ? node : null);
                
                if (marioIframe && !marioIframe.dataset.focused) {
                    marioIframe.dataset.focused = 'true';
                    
                    // Add load event listener
                    marioIframe.addEventListener('load', function() {
                        setTimeout(() => {
                            // Scroll into view
                            marioIframe.scrollIntoView({behavior: 'smooth', block: 'center'});
                            
                            // Focus the iframe itself
                            marioIframe.setAttribute('tabindex', '0');
                            marioIframe.focus();
                        }, 300);
                    });
                }
            }
        });
    });
});

// Start observing when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', startObserver);
} else {
    startObserver();
}

function startObserver() {
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
        observer.observe(chatMessages, { childList: true, subtree: true });
    }
}
