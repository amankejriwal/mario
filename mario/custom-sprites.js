/**
 * Custom sprite loader for external images (like Heineken bottle)
 * This overrides the default pixel-based rendering for specific sprites
 */

(function() {
    console.log('Loading custom sprites...');
    
    // Load Heineken bottle image
    var heinekenImage = new Image();
    heinekenImage.src = 'assets/hnk_bot.png';
    
    heinekenImage.onload = function() {
        console.log('Heineken sprite loaded successfully!', heinekenImage.width + 'x' + heinekenImage.height);
    };
    
    heinekenImage.onerror = function() {
        console.error('Failed to load hnk_bot.png from assets/');
    };
    
    // Hook into game after it starts
    var checkInterval = setInterval(function() {
        // Wait for UserWrapper and game to be created
        if (typeof window.FSM !== 'undefined' && window.FSM && window.FSM.PixelDrawer) {
            clearInterval(checkInterval);
            injectCustomSprite();
        } else if (typeof UserWrapper !== 'undefined' && UserWrapper && UserWrapper.GameStarter) {
            clearInterval(checkInterval);
            window.FSM = UserWrapper.GameStarter;
            injectCustomSprite();
        }
    }, 100);
    
    // Timeout after 10 seconds
    setTimeout(function() {
        clearInterval(checkInterval);
    }, 10000);
    
    function injectCustomSprite() {
        try {
            var FSM = window.FSM;
            
            if (!FSM || !FSM.PixelDrawer) {
                console.error('FSM or PixelDrawer not found');
                return;
            }
            
            console.log('Found game instance, injecting custom sprite...');
            console.log('Available PixelDrawer methods:', Object.keys(FSM.PixelDrawer));
            
            // Try hooking into drawThingOnContext (main canvas drawing)
            var originalDrawThing = FSM.PixelDrawer.drawThingOnContext;
            
            if (!originalDrawThing) {
                console.error('drawThingOnContext not found');
                return;
            }
            
            var drewOnce = false;
            
            // Override the main drawing function
            FSM.PixelDrawer.drawThingOnContext = function(context, thing) {
                // Check if this is a Mushroom
                if (thing && (thing.title === 'Mushroom' || thing.constructor && thing.constructor.name === 'Mushroom')) {
                    
                    if (!drewOnce) {
                        console.log('🍺 Mushroom detected! Drawing on main canvas');
                        console.log('Thing position:', thing.left, thing.top);
                        console.log('Thing size:', thing.width, thing.height);
                        console.log('Image:', heinekenImage.width, 'x', heinekenImage.height);
                        drewOnce = true;
                    }
                    
                    // Draw Heineken bottle instead of pixel sprite
                    if (heinekenImage.complete) {
                        try {
                            var unitsize = FSM.unitsize || 4;
                            var maxWidth = thing.width * unitsize;
                            var maxHeight = thing.height * unitsize;
                            
                            // Calculate proper aspect ratio (bottle is tall: 372x1454)
                            var imgRatio = heinekenImage.width / heinekenImage.height;
                            
                            // Fit to height, adjust width to maintain aspect ratio, then scale 1.5x
                            var drawHeight = maxHeight * 1.5;
                            var drawWidth = drawHeight * imgRatio * 1.3;  // Make bottle 30% wider
                            
                            // Center horizontally and vertically
                            var drawX = thing.left + (maxWidth - drawWidth) / 2;
                            var drawY = thing.top - (drawHeight - maxHeight) / 2;
                            
                            // Draw the Heineken bottle image at thing's position
                            context.drawImage(
                                heinekenImage,
                                0, 0,  // Source X, Y
                                heinekenImage.width, heinekenImage.height,  // Full source image
                                drawX, drawY,  // Centered position
                                drawWidth, drawHeight  // Properly scaled size
                            );
                            
                            return;  // Skip original rendering
                        } catch (e) {
                            console.error('Error drawing Heineken:', e);
                        }
                    } else {
                        console.warn('Heineken image not loaded yet');
                    }
                }
                
                // For all other things, use original rendering
                originalDrawThing.call(this, context, thing);
            };
            
            console.log('✅ Custom Mushroom sprite injected successfully!');
        } catch (e) {
            console.error('Error injecting custom sprite:', e);
        }
    }
})();
