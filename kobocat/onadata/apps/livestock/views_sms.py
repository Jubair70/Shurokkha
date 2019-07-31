#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from collections import OrderedDict
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.http import (HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response, get_object_or_404, render
from django.core.files.storage import FileSystemStorage


def __db_fetch_values(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchall()
    cursor.close()
    return fetchVal


def __db_fetch_single_value(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    cursor.close()
    return fetchVal[0]


def __db_commit_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    connection.commit()
    cursor.close()


def __db_fetch_values_dict(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = dictfetchall(cursor)
    cursor.close()
    return fetchVal


def dictfetchall(cursor):
    desc = cursor.description
    return [
        OrderedDict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()]



def get_district_list(request):
    division_id = request.POST.getlist('division_id[]')
    division_id = "'" + "', '".join(str(x) for x in division_id) + "'"
    district_list = __db_fetch_values_dict("select dist_code as id, district as name from vwdistrict where div_code in (" + str(division_id) + ")")
    return HttpResponse(json.dumps(district_list))


def get_upazila_list(request):
    district_id = request.POST.getlist('district_id[]')
    district_id = "'" + "', '".join(str(x) for x in district_id) + "'"
    upazila_list = __db_fetch_values_dict("select upazila_code as id, upazila as name from vwupazila where dist_code in (" + str(district_id) + ")")
    return HttpResponse(json.dumps(upazila_list))


def get_union_list(request):
    upazila_id = request.POST.getlist('upazila_id[]')
    upazila_id = "'" + "', '".join(str(x) for x in upazila_id) + "'"
    union_list = __db_fetch_values_dict("select id,name from geo_union where geo_upazilla_id in (" + str(upazila_id) + ")")
    return HttpResponse(json.dumps(union_list))


def list_sms(request):
    sms_data = __db_fetch_values_dict("select id,lpad(id::text,4,'0') as sms_id,sms_text,decode_url_part(replace(voice_clip_loc,'/media/','')) as voice_clip, case sms_type when 1 then 'General' when 2 then 'Promotinal' when 3 then 'Event Based' end as sms_type, event_id from sms_details")
    return render(request, "livestock/list_sms.html",{
        'sms_data':sms_data
    })


def sms_details(request):
    divisions = __db_fetch_values_dict("select div_code as id,division as name from vwdivision")
    #cattle_types = __db_fetch_values_dict("select value,label from vwcattle_type")
    
    if request.method == 'POST':
        print request.POST
        if request.FILES['voice_clip_loc']:
            myfile = request.FILES['voice_clip_loc']
            fs = FileSystemStorage()
            filename = fs.save(myfile.name, myfile)
            uploaded_file_url = fs.url(filename)
        else:
            uploaded_file_url = ''
        
        sms_text = request.POST.get('sms_text')
        sms_sent_type = request.POST.get('sms_sent_type')
        sms_type = request.POST.get('sms_type')
        if 'schedule_date' in request.POST:
            schedule_date = request.POST.get('schedule_date')
        else:
            schedule_date = 'n/a'
        trigger_time = request.POST.get('trigger_time')
        
        if 'event_id' in request.POST:
            event_id = request.POST.get('event_id')
        else:
            event_id = -1
        
        if 'interval_time' in request.POST:
            interval_time = request.POST.get('interval_time')
            if interval_time == '':
                interval_time = -1
        else:
            interval_time = -1
        
        division_id = request.POST.getlist('division_id')
        district_id = request.POST.getlist('district_id')
        upazila_id = request.POST.getlist('upazila_id')
        user_type = request.POST.getlist('user_type')
        cattle_type = request.POST.getlist('cattle_type')
        age_range_start = request.POST.get('age_range_start')
        age_range_end = request.POST.get('age_range_end')

        recepient_json = {}
        if sms_type == '1' or sms_type == '2':
            recepient_json['division_id'] = division_id
            recepient_json['district_id'] = district_id
            recepient_json['upazila_id'] = upazila_id
            recepient_json['user_type'] = user_type
            recepient_json['cattle_type'] = cattle_type
            recepient_json['age_range_start'] = age_range_start
            recepient_json['age_range_end'] = age_range_end

        recepient_final = json.dumps(recepient_json)

        __db_commit_query("INSERT INTO public.sms_details (sms_text, voice_clip_loc, sms_sent_type, sms_type, schedule_date, trigger_time, event_id, interval_time, recepient_json) VALUES('"+str(sms_text)+"', '"+str(uploaded_file_url)+"', "+str(sms_sent_type)+", "+str(sms_type)+", '"+str(schedule_date)+"', '"+str(trigger_time)+"', "+str(event_id)+", "+str(interval_time)+", '"+str(recepient_final)+"')")
        return HttpResponseRedirect('/livestock/list_sms/')

    return render(request, "livestock/sms_details.html",
    {
        'divisions':divisions
    })


def get_label_name(value,type):
    users_dict = {
        '1':'Farmer',
        '2':'Paravet',
        '3':'AI Technician'
    }

    cattle_dict = {
        '1':'Cow',
        '2':'Heifer',
        '3':'Bull',
        '4':'Calf'
    }

    if value is not None:
        if type == 1:
            return __db_fetch_single_value("select division from vwdivision where div_code='"+str(value)+"'")
        elif type == 2:
            return __db_fetch_single_value("select district from vwdistrict where dist_code='"+str(value)+"'")
        elif type == 3:
            return __db_fetch_single_value("select upazila from vwupazila where upazila_code='"+str(value)+"'")
        elif type == 4:
            return users_dict[value]
        elif type == 5:
            return cattle_dict[value]


def view_individual_sms(request,sms_id):
    sms_data = __db_fetch_values_dict("select sms_text, decode_url_part(replace(voice_clip_loc,'/media/','')) as voice_clip, case sms_sent_type when 1 then 'Text' when 2 then 'Voice Clip' when 3 then 'Both(Text & Voice Clip)' end as sms_sent_type, case sms_type when 1 then 'General' when 2 then 'Promotinal' when 3 then 'Event Based' end as sms_type, schedule_date, trigger_time, case event_id when 0 then 'N/A' else event_id::text end as event_id, case interval_time when -1 then 'N/A' else interval_time::text || ' day/s' end as interval_time, recepient_json->>'division_id' as division_id, recepient_json->>'district_id' as district_id, recepient_json->>'upazila_id' as upazila_id, recepient_json->>'user_type' as user_type, recepient_json->>'cattle_type' as cattle_type, recepient_json->>'age_range_start' as age_range_start, recepient_json->>'age_range_end' as age_range_end from sms_details where id = "+str(sms_id))
    divisions = ''
    districts = ''
    upazilas = ''
    users = ''
    cattle_types = ''
    no_of_selected_users = 'N/A'

    where_clause = 'where 1 = 1'

    if sms_data[0]['division_id']:
        division_id = eval(sms_data[0]['division_id'])
        divisions = ', '.join([get_label_name(x,1) for x in division_id])
        div_whr = str(sms_data[0]['division_id']).replace('"','\'')
        if div_whr != '[]':
            where_clause += ' and t.division  = any(array['+str(div_whr)+'])'

    if sms_data[0]['district_id']:
        district_id = eval(sms_data[0]['district_id'])
        districts = ', '.join([get_label_name(x,2) for x in district_id])
        dis_whr = str(sms_data[0]['district_id']).replace('"','\'')
        if dis_whr:
            where_clause += ' and t.district  = any(array['+str(dis_whr)+'])'
    
    if sms_data[0]['upazila_id']:
        upazila_id = eval(sms_data[0]['upazila_id'])
        upazilas = ', '.join([get_label_name(x,3) for x in upazila_id])
        upz_whr = str(sms_data[0]['upazila_id']).replace('"','\'')
        if upz_whr != '[]':
            where_clause += ' and t.upazila = any(array['+str(upz_whr)+'])'

    if sms_data[0]['user_type']:
        user_type = eval(sms_data[0]['user_type'])
        users = ', '.join([get_label_name(x,4) for x in user_type])
        user_whr = str(sms_data[0]['user_type']).replace('"','\'')
        if user_whr != '[]':
            where_clause += ' and t.user_type = any(array['+str(user_whr)+'])'

    if sms_data[0]['cattle_type']:
        cattle_type = eval(sms_data[0]['cattle_type'])
        cattle_types = ', '.join([get_label_name(x,5) for x in cattle_type])
        cattle_whr = str(sms_data[0]['cattle_type']).replace('"','\'')
        if cattle_whr != '[]':
            where_clause += ' and t.cattle_type = any(array['+str(cattle_whr)+'])'
        
    
    if sms_data[0]['age_range_end'] and sms_data[0]['age_range_start']:
        age_range = sms_data[0]['age_range_start'] + ' ~ ' + sms_data[0]['age_range_end']
        where_clause += ' and t.c_age::int between symmetric '+str(sms_data[0]['age_range_start'])+' and '+str(sms_data[0]['age_range_end'])
    else:
        age_range = ''

    if sms_data[0]['sms_type'] != 3:
        qry = "with t as(select shurokkha_users.username,shurokkha_users.division,shurokkha_users.district,shurokkha_users.upazila,case shurokkha_users.user_type when 'Paravet' then '2' when 'AI Technicians' then '3' when 'Farmer' then '1' end as user_type,cattle.cattle_type,coalesce(cattle.cattle_age,cattle.calf_age) as c_age from shurokkha_users left join cattle on cattle.mobile = shurokkha_users.username) select count(DISTINCT username) from t "+where_clause
        no_of_selected_users = __db_fetch_single_value(qry)

    
    return render(request, "livestock/view_individual_sms.html",{
        'divisions':divisions,
        'districts':districts,
        'upazilas':upazilas,
        'sms_sent_type':sms_data[0]['sms_sent_type'],
        'sms_text':sms_data[0]['sms_text'],
        'voice_clip':sms_data[0]['voice_clip'],
        'sms_type':sms_data[0]['sms_type'],
        'trigger_time':sms_data[0]['trigger_time'],
        'schedule_date':sms_data[0]['schedule_date'],
        'event_id':sms_data[0]['event_id'],
        'interval_time':sms_data[0]['interval_time'],
        'age_range':age_range,
        'users':users,
        'cattle_types':cattle_types,
        'no_of_selected_users':no_of_selected_users
    })