from django.conf.urls import patterns, include, url
from django.contrib import admin
from . import views

urlpatterns = patterns('',
                       url(r'^medicine_list/$', views.medicine_list, name='medicine_list'),
                        url(r'^get_medicine_data_table/$', views.get_medicine_data_table, name='get_medicine_data_table'),
                        url(r'^add_medicine/$', views.add_medicine, name='add_medicine'),
                        url(r'^upload_medicine/$', views.upload_medicine, name='upload_medicine'),
                        url(r'^delete_medicine/(?P<id>\d+)/$', views.delete_medicine, name='delete_medicine'),
                        url(r'^edit_medicine/(?P<id>\d+)/$', views.edit_medicine, name='edit_medicine'),


                       )
