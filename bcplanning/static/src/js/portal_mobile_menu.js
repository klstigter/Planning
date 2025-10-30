/** @odoo-module **/
/*
 Clone desktop portal links into the mobile menu container used by the theme.
 Safe approach: no QWeb xpath changes; works with most Odoo 19 themes.
*/

(function () {
    'use strict';

    function insertPortalLinks() {
        try {
            var $desktop = $('#bcplanning-portal-menu');
            if (!$desktop.length) {
                return; // nothing to clone
            }

            // Candidate mobile containers (ordered). Add selectors if your theme uses different wrapper.
            var mobileSelectors = [
                '.navbar-collapse',     // standard bootstrap collapse
                '.offcanvas-body',      // offcanvas/body used by some themes
                '#o_mobile_menu',       // common custom id
                '.o_mobile_menu',
                '.o_offcanvas_body',
                '.o_offcanvas_menu',
                '.o_main_nav'           // fallback
            ];

            var $mobile = null;
            for (var i = 0; i < mobileSelectors.length; i++) {
                var sel = mobileSelectors[i];
                var $c = $(sel).first();
                if ($c && $c.length) {
                    $mobile = $c;
                    break;
                }
            }

            // If no mobile container found, create a simple mobile container at the end of body
            if (!$mobile || !$mobile.length) {
                if ($('#bcplanning-portal-menu-mobile').length === 0) {
                    $('body').append('<div id="bcplanning-portal-menu-mobile" class="d-block d-lg-none p-3"></div>');
                }
                $mobile = $('#bcplanning-portal-menu-mobile');
            }

            // Avoid duplicating insertion
            if ($mobile.find('#bcplanning-portal-menu-clone').length) {
                return;
            }

            // Clone the UL (links) and adapt markup for vertical mobile layout
            var $ul = $desktop.find('ul').first().clone(true);
            $ul.removeClass('nav-pills').addClass('nav flex-column');
            $ul.find('li').each(function () {
                var $li = $(this);
                $li.removeClass('nav-item me-2').addClass('nav-item mb-1');
                $li.find('a').removeClass('nav-link p-1').addClass('nav-link');
            });

            var $wrapper = $('<div id="bcplanning-portal-menu-clone" class="bcplanning-mobile-links"></div>');
            $wrapper.append($ul);

            // Insert into mobile container (prepend for visibility in offcanvas/collapse)
            if ($mobile.hasClass('offcanvas-body') || $mobile.is('.navbar-collapse')) {
                $mobile.prepend($wrapper);
            } else {
                $mobile.append($wrapper);
            }
        } catch (err) {
            console.error('portal_mobile_menu insert error', err);
        }
    }

    // Run on DOM ready
    $(document).ready(function () {
        insertPortalLinks();
    });

    // Also attempt again after short delay (themes sometimes build offcanvas later)
    setTimeout(insertPortalLinks, 500);
    setTimeout(insertPortalLinks, 1500);

    // Re-apply on window resize (in case menu switches)
    $(window).on('resize.bcplanning', function () {
        insertPortalLinks();
    });

    // Also listen for offcanvas shown event (Bootstrap) to ensure presence
    $(document).on('shown.bs.offcanvas', function () {
        insertPortalLinks();
    });

})();