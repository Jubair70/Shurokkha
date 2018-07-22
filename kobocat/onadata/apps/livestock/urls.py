from django.conf.urls import patterns, include, url
from django.contrib import admin
from . import views,views_api

urlpatterns = patterns('',
                       url(r'^medicine_list/$', views.medicine_list, name='medicine_list'),
                        url(r'^get_medicine_data_table/$', views.get_medicine_data_table, name='get_medicine_data_table'),
                        url(r'^add_medicine/$', views.add_medicine, name='add_medicine'),
                        url(r'^upload_medicine/$', views.upload_medicine, name='upload_medicine'),
                        url(r'^delete_medicine/(?P<id>\d+)/$', views.delete_medicine, name='delete_medicine'),
                        url(r'^edit_medicine/(?P<id>\d+)/$', views.edit_medicine, name='edit_medicine'),

                        url(r'^farmer_list/$', views.farmer_list, name='farmer_list'),
                        url(r'^get_farmer_table/$', views.get_farmer_table, name='get_farmer_table'),
                        url(r'^approval_list/$', views.approval_list, name='approval_list'),
                        url(r'^get_approval_table/$', views.get_approval_table, name='get_approval_table'),
                        url(r'^approve/(?P<id>\d+)/$', views.approve, name='approve'),
                        url(r'^reject/(?P<id>\d+)/$', views.reject, name='reject'),



                       #******************   MOBILE API     ***********************************#
                        url(r"^get/user_info/$", views_api.login_verify, name='user_verify'),
                        url(r"^save_user/$", views_api.save_user, name='save_user'),
                        url(r"^get_farmer_list/$", views_api.get_farmer_list, name='get_farmer_list'),
                        url(r"^get_cattle_list/$", views_api.get_cattle_list, name='get_cattle_list')


                       )
