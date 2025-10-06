/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
publicWidget.registry.MaterialRequest = publicWidget.Widget.extend({
    selector: "#wrap",
    events: {        
        'click .open_project_planning_line': '_onClick_open_project_planning_line', // Maps click event to handler
    },
   
     _onClick_open_project_planning_line: function(ev) {
        ev.preventDefault();

        // Find the closest td and required spans
        const td = $(ev.currentTarget).closest('td');
        const projectIdSpan = td.find('.data_project_id');
        const projectNoSpan = td.find('.data_project_no');
        const projectNameSpan = td.find('.data_project_desc');

        // Check if projectIdSpan exists before reading
        if (projectIdSpan.length) {
            const job_id = projectIdSpan.text().trim();
            const job_no = projectNoSpan.text().trim();
            const job_name = projectNameSpan.text().trim();
            const url = `/partner/tasks?job_id=${encodeURIComponent(job_id)}&job_no=${encodeURIComponent(job_no)}&job_name=${encodeURIComponent(job_name)}`;
            window.location.href = url;
        } else {
            alert("Project data not found!");
        }
    },

})

// document.addEventListener("DOMContentLoaded", () => {
//     document.querySelectorAll(".open_project_planning_line").forEach((btn) => {
//         btn.addEventListener("click", (ev) => {
//             ev.preventDefault();
//             const job_id = btn.dataset.job_id;
//             const job_no = btn.dataset.job_no;
//             const job_name = btn.dataset.job_name;
//             const url = `/partner/tasks?job_id=${encodeURIComponent(job_id)}&job_no=${encodeURIComponent(job_no)}&job_name=${encodeURIComponent(job_name)}`;
//             window.location.href = url;
//         });
//     });
// });

// document.addEventListener("DOMContentLoaded", () => {
//     document.querySelectorAll(".open_project_planning_line").forEach((btn) => {
//         btn.addEventListener("click", (ev) => {
//             ev.preventDefault();
//             const td = btn.closest('td');
//             const projectIdSpan = td.querySelector('.data_project_id');
//             const projectNoSpan = td.querySelector('.data_project_no');
//             const projectNameSpan = td.querySelector('.data_project_desc');
            
//             // Check if spans exist before reading
//             if (projectIdSpan) {
//                 const job_id = projectIdSpan.textContent.trim();
//                 const job_no = projectNoSpan.textContent.trim();
//                 const job_name = projectNameSpan.textContent.trim();
//                 const url = `/partner/tasks?job_id=${encodeURIComponent(job_id)}&job_no=${encodeURIComponent(job_no)}&job_name=${encodeURIComponent(job_name)}`;
//                 window.location.href = url;
//             } else {
//                 alert("Project data not found!");
//             }
//         });
//     });
// });

// $(document).ready(function(){
//     $('.open_project_planning_line').on('click', function(ev){
//         ev.preventDefault();
//         var td = $(this).closest('td');
//         var job_id = td.find('.data_project_id').text().trim();
//         var job_no = td.find('.data_project_no').text().trim();
//         var job_name = td.find('.data_project_desc').text().trim();
//         if (job_id) {
//             var url = `/partner/tasks?job_id=${encodeURIComponent(job_id)}&job_no=${encodeURIComponent(job_no)}&job_name=${encodeURIComponent(job_name)}`;
//             window.location.href = url;
//         } else {
//             alert("Project data not found!");
//         }
//     });
// });

