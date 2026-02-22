database schema
db_name


master schema
sch_master
tb_master_clientinfo
tb_master_exd_bgvinfo
violation_type
violation_decription
violation_attachment_url

sch_client
tb_shortname_user_info
job_title
tb_shortname_user_bgv_info
tb_shortname_user_bgv_results

tb_shortname_user_timesheets
id
user_id(user_info)
project_name
task
type
submited_from_date
submited_to_date
date
submited_hours
approved_hours
rejected_hours
timesheet_attachment_url
timesheet_status sub/pen/ap/den


Requests
tb_shortname_user_requests
id
user_id
request_type
request_description (json)
request_category
request_reasons 
request_from_date
request_to_date
request_from_time
request_to_time
request_attachment_url


tb_shortname_user_violations
violation_type
violation_decription
violation_attachment_url



////////////////////////////////
tb_shortname_company_client_info
tb_shortname_company_vendor_info
tb_shortname_company_project_info
tb_shortname_company_sow_info




#################################################################################

api calls 


User:
    signin
    auth
    bgv
    user_timesheets_submit
    requests
    user_dashboard

Manager:
        signin
        auth
        bgv_results
        timesheets_submit
        timesheets_actions
        create_user
        edit_user
        view_user
        user_status act/ina
        manager_dashboard
        create_client
        edit_client
        view_client
        create_vendor
        edit_vendor
        view_vendor
        create_project
        edit_project
        view_project
        create_sow
        edit_sow
        view_sow
        user_docs
        comapany_docs


Admin:
        signin
        auth
        bgv_results
        bgv_delete
        timesheets_submit
        timesheets_actions
        timesheets_delete
        create_user
        edit_user
        view_user
        user_status act/ina
        user_delete
        admin_dashboard
        create_client
        edit_client
        view_client
        delete_client
        create_vendor
        edit_vendor
        view_vendor
        delete_vendor
        create_project
        edit_project
        view_project
        delete_project
        create_sow
        edit_sow
        view_sow
        user_docs
        delete_user_docs
        comapany_docs
        delete_company_docs
        
