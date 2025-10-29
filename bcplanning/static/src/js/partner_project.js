/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";
// import publicWidget from "web.public.widget";

publicWidget.registry.BCPlanningProject = publicWidget.Widget.extend({
    selector: "#project_wrap",
    events: {
        'click .open-project': '_onOpenProject',
    },

    _onOpenProject: function (ev) {
        // Respect user choice for new tab / new window
        if (ev.ctrlKey || ev.metaKey || ev.which === 2) {
            return;
        }
        ev.preventDefault();

        const $btn = $(ev.currentTarget);
        const href = $btn.attr('href') || $btn.data('href');
        if (href) {
            window.location.assign(href);
            return;
        }

        // Fallback (shouldn't be needed because href is provided)
        const jobId = $btn.data('job-id') || $btn.data('job_id') || $btn.attr('data-job-id');
        if (jobId) {
            window.location.assign(`/partner/tasks?job_id=${encodeURIComponent(jobId)}`);
        } else {
            window.alert("Project data not found!");
        }
    },
});