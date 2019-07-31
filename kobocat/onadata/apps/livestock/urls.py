from django.conf.urls import patterns, include, url
from django.contrib import admin
from . import views,views_api,views_sms

urlpatterns = patterns('',
                       url(r'^medicine_list/$', views.medicine_list, name='medicine_list'),
                        url(r'^get_medicine_data_table/$', views.get_medicine_data_table, name='get_medicine_data_table'),
                        url(r'^add_medicine/$', views.add_medicine, name='add_medicine'),
                        url(r'^upload_medicine/$', views.upload_medicine, name='upload_medicine'),
                        url(r'^delete_medicine/(?P<id>\d+)/$', views.delete_medicine, name='delete_medicine'),
                        url(r'^edit_medicine/(?P<id>\d+)/$', views.edit_medicine, name='edit_medicine'),
                        url(r'^upload_prescription/$', views.upload_prescription, name='upload_prescription'),

                        url(r'^farmer_list/$', views.farmer_list, name='farmer_list'),
                        url(r'^get_farmer_table/$', views.get_farmer_table, name='get_farmer_table'),
                        url(r'^approval_list/$', views.approval_list, name='approval_list'),
                        url(r'^get_approval_table/$', views.get_approval_table, name='get_approval_table'),
                        url(r'^approve/(?P<id>\d+)/$', views.approve, name='approve'),
                        url(r'^reject/(?P<id>\d+)/$', views.reject, name='reject'),
                        url(r'^farmer_profile/(?P<id>\d+)/$', views.farmer_profile, name='farmer_profile'),
                        url(r'^get_cattle_list/(?P<id>\d+)/$', views.get_cattle_list, name='get_cattle_list'),
                        url(r'^cattle_profile/(?P<cattle_id>\d+)/(?P<appointment_id>\d+)$', views.cattle_profile, name='cattle_profile'),
                        url(r'^clinical_findings/(?P<appointment_id>\d+)$', views.clinical_findings, name='clinical_findings'),
                        url(r'^get_diagnosis_name/$', views.get_diagnosis_name, name='get_diagnosis_name'),
                        url(r'^advisory_list/$', views.advisory_list, name='advisory_list'),
                        url(r'^get_advisory_table/$', views.get_advisory_table, name='get_advisory_table'),
                       url(r'^submit_prescription/(?P<appointment_id>\d+)$', views.submit_prescription, name='submit_prescription'),
                        url(r'^get_medicine_name/$', views.get_medicine_name, name='get_medicine_name'),
                        url(r'^get_medicine_type/$', views.get_medicine_type, name='get_medicine_type'),
                        url(r'^get_medicine_packsize/$', views.get_medicine_packsize, name='get_medicine_packsize'),
                        url(r'^get_suggested_prescription/$', views.get_suggested_prescription, name='get_suggested_prescription'),
                        url(r'^get_old_prescription/(?P<logger_id>\d+)/$', views.get_old_prescription, name='get_old_prescription'),
                        url(r'^get_dashboard/$', views.get_dashboard, name='get_dashboard'),
                        url(r'^content_upload/$', views.content_upload, name='content_upload'),
                        url(r'^content_list/$', views.content_list, name='content_list'),
                        url(r'^get_content_table/$', views.get_content_table, name='get_content_table'),
                        url(r'^delete_content/(?P<id>\d+)/$', views.delete_content, name='delete_content'),
                        url(r'^get_district/$', views.get_district, name='get_district'),
                        url(r'^getDistricts/$', views.getDistricts, name='getDistricts'),
                        url(r'^get_upazila/$', views.get_upazila, name='get_upazila'),
                        url(r'^getUpazillas/$', views.getUpazillas, name='getUpazillas'),
                        url(r'^get_dashboard_content/$', views.get_dashboard_content, name='get_dashboard_content'),
                        url(r'^add_location/(?P<farmer_id>\d+)/$', views.add_location, name='add_location'),
                        url(r'^prescription/$', views.prescription, name='prescription'),
                        url(r'^get_prescription_table/$', views.get_prescription_table, name='get_prescription_table'),
                        url(r'^view_ai_pravet_profile/(?P<id>\d+)/$', views.view_ai_paravet_profile, name='view_ai_paravet_profile'),
                        url(r'^send_prescription_sms/$', views.send_prescription_sms, name='send_prescription_sms'),


                        ###****************** Emtiaz work (S) ****************###

                        url(r'^get_sms_dashboard/$', views.get_sms_dashboard, name='get_sms_dashboard'),
                        url(r'^get_sms_dashboard_content/$', views.get_sms_dashboard_content, name='get_sms_dashboard_content'),

                        url(r'^get_para_vet_performance_dashboard/$', views.get_para_vet_performance_dashboard, name='get_para_vet_performance_dashboard'),
                        url(r'^get_para_vet_performance_dashboard_content/$', views.get_para_vet_performance_dashboard_content,
                           name='get_para_vet_performance_dashboard_content'),
                        url(r'^get_paravet_no_case_tat_Dashboard/$', views.get_paravet_no_case_tat_Dashboard,
                           name='get_paravet_no_case_tat_Dashboard'),
                        url(r'^get_para_vet_details/(?P<id>\d+)/(?P<mobile>\d+)/$', views.get_para_vet_details, name='get_para_vet_details'),
                        url(r'^get_paravet_performance_dashboard/$', views.get_paravet_performance_dashboard,
                           name='get_paravet_performance_dashboard'),
                       ###****************** Emtiaz work (E) ****************###

                        #DASHBOARD
                        url(r'^ai_dashboard_content/$', views.ai_dashboard_content, name='ai_dashboard_content'),
                        url(r'^get_percentage_dashboard/$', views.get_ai_percentage_dashboard, name='get_ai_percentage_dashboard'),
                        url(r'^get_percentage_dashboard_new/$', views.get_ai_percentage_dashboard_new, name='get_ai_percentage_dashboard_new'),
                        url(r'^get_individual_ai_data/$', views.get_individual_ai_data, name='get_individual_ai_data'),

                        url(r'^group_performance_dashboard/bull/conception_rate/$', views.get_group_performance_dashboard_bull_conception_rate, name='get_group_performance_dashboard_bull_conception_rate'),
                        url(r'^group_performance_dashboard/bull/service_per_conception/$', views.get_group_performance_dashboard_bull_service_per_conception, name='get_group_performance_dashboard_bull_service_per_conception'),
                        url(r'^individual_performance_dashboard/bull/(?P<bull_id>\d+)/(?P<category_id>\d+)/$', views.get_individual_bull_performance_dashboard, name='get_individual_bull_performance_dashboard'),

                        url(r'^group_performance_dashboard/ai/conception_rate/$', views.get_group_performance_dashboard_ai_conception_rate, name='get_group_performance_dashboard_ai_conception_rate'),
                        url(r'^group_performance_dashboard/ai/service_per_conception/$', views.get_group_performance_dashboard_ai_service_per_conception, name='get_group_performance_dashboard_ai_service_per_conception'),
                        url(r'^individual_performance_dashboard/ai/(?P<ai_id>\d+)/(?P<category_id>\d+)/$', views.get_individual_ai_performance_dashboard, name='get_individual_ai_performance_dashboard'),


                        url(r'^set_target/(?P<id>\d+)/$', views.set_target, name='set_target'),
                        url(r'^targetCreate/$', views.targetCreate, name="targetCreate"),
                        url(r'^targetEdit/$', views.targetEdit, name="targetEdit"),
                        url(r'^bull_list/$', views.bull_list, name='bull_list'),
                        url(r'^add_bull_form/$', views.add_bull_form, name='add_bull_form'),
                        url(r'^insert_bull_form/$', views.insert_bull_form, name='insert_bull_form'),
                        url(r'^edit_bull_form/(?P<id>\d+)/$', views.edit_bull_form,name='edit_bull_form'),
                        url(r'^update_bull_form/$', views.update_bull_form, name='update_bull_form'),
                        url(r'^delete_bull_form/(?P<id>\d+)/$', views.delete_bull_form,name='delete_bull_form'),


                        url(r'^sms_details/$', views_sms.sms_details, name='sms_details'),
                        url(r'^view_individual_sms/(?P<sms_id>\d+)/$', views_sms.view_individual_sms,name='view_individual_sms'),
                        url(r'^list_sms/$', views_sms.list_sms, name='list_sms'),
                        url(r'^get_district_list/$', views_sms.get_district_list, name='get_district_list'),
                        url(r'^get_upazila_list/$', views_sms.get_upazila_list, name='get_upazila_list'),
                        url(r'^get_union_list/$', views_sms.get_union_list, name='get_union_list'),

                       ##############################

                       url(r'^getAdvisoryData/$', views.getAdvisoryData, name='getAdvisoryData'),
                       url(r'^sickness_list/$', views.sickness_list, name='sickness_list'),
                       url(r'^getSicknessData/$', views.getSicknessData, name='getSicknessData'),
                       url(r'^get_clinical_findings/$', views.get_clinical_findings, name='get_clinical_findings'),
                       url(r'^update_cattle_type/$', views.update_cattle_type, name='update_cattle_type'),


                       #******************   MOBILE API     ***********************************#
                        url(r"^get/user_info/$", views_api.login_verify, name='user_verify'),
                        url(r"^save_user/$", views_api.save_user, name='save_user'),
                        url(r"^get_farmer_list/$", views_api.get_farmer_list, name='get_farmer_list'),
                        url(r"^get_cattle_list/$", views_api.get_cattle_list, name='get_cattle_list'),
                        url(r"^delete_farmer/$", views_api.delete_farmer, name='delete_farmer'),
                        url(r"^search_farmer/$", views_api.search_farmer, name='search_farmer'),
                       url(r"^cattle_info$", views_api.cattle_info, name='cattle_info'),
                       url(r"^get_prescription_list/(?P<username>\d+)/$", views_api.get_prescription_list,
                           name='get_prescription_list'),
                       url(r"^get_prescription_details/(?P<prescription_id>\d+)/$", views_api.get_prescription_details,
                           name='get_prescription_details'),

                       url(r"^(?P<username>\w+)/get/user_contentlist/$", views_api.get_content_list,
                           name='get_content_list'),
                        url(r"^assign_farmer/$", views_api.assign_farmer, name='assign_farmer'),
                        url(r"^update_token/$", views.update_token, name='update_token'),
                        url(r"^get_cattle_info$", views_api.get_cattle_info, name='get_cattle_info'),
                        url(r"^cattle_prescription_list/(?P<cattle_id>\d+)/$", views_api.cattle_prescription_list, name='cattle_prescription_list'),
                        url(r"^get_cattle_general_info/$", views_api.get_cattle_general_info, name='get_cattle_general_info'),



                       )
