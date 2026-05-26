/** @odoo-module **/

function fsrpEnableDashboardScroll() {
    const selectors = [
        '.fsrp-manager-panel',
        '.fsrp-simple-screen',
        '.fsrp-exec-dashboard',
        '.fsrp-dashboard-page',
        '.fsrp-fmcg-dashboard',
        '.fsrp-route-dashboard',
        '.fsrp-manager-control-panel',
    ];
    if (!document.querySelector(selectors.join(','))) {
        return;
    }
    const nodes = [
        document.querySelector('.o_action_manager'),
        document.querySelector('.o_action_manager .o_action'),
        document.querySelector('.o_action_manager .o_content'),
        document.querySelector('.o_action_manager .o_component'),
    ].filter(Boolean);
    for (const node of nodes) {
        node.style.overflowY = 'auto';
        node.style.overflowX = 'hidden';
        node.style.maxHeight = 'none';
    }
    for (const node of document.querySelectorAll(selectors.join(','))) {
        node.style.height = 'auto';
        node.style.maxHeight = 'none';
        node.style.overflowY = 'visible';
        node.style.paddingBottom = '56px';
    }
}

setInterval(fsrpEnableDashboardScroll, 1200);
document.addEventListener('DOMContentLoaded', fsrpEnableDashboardScroll);
