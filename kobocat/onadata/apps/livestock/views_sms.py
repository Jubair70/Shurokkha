#!/usr/bin/env python
# -*- coding: utf-8 -*-
import json
from collections import OrderedDict
from datetime import datetime
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.http import (HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response, get_object_or_404, render
from django.core.files.storage import FileSystemStorage

final_list = {}

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


def __db_insert_query(query):
    cursor = connection.cursor()
    cursor.execute(query)
    # connection.commit()
    fetch_val = cursor.fetchone()
    cursor.close()
    return fetch_val[0]



def get_district_list(request):
    division_id = request.POST.getlist('division_id[]')
    print [str(x) for x in division_id]
    division_id = "'" + "', '".join(str(x) for x in division_id) + "'"
    district_list = __db_fetch_values_dict("select div_code || dist_code as id, district as name from vwdistrict where div_code in (" + str(division_id) + ")")
    return HttpResponse(json.dumps(district_list))


def get_upazila_list(request):
    district_id = request.POST.getlist('district_id[]')
    district_id = "'" + "', '".join(str(x)[-2:] for x in district_id) + "'"
    print "select div_code || dist_code || upazila_code as id, upazila as name from vwupazila where dist_code in (" + str(district_id) + ")"
    upazila_list = __db_fetch_values_dict("select div_code || dist_code || upazila_code as id, upazila as name from vwupazila where dist_code in (" + str(district_id) + ")")
    return HttpResponse(json.dumps(upazila_list))


def list_sms(request):
    sms_data = __db_fetch_values_dict("select id,lpad(id::text,4,'0') as sms_id,sms_text,decode_url_part(replace(voice_clip_loc,'/media/','')) as voice_clip, case sms_type when 1 then 'General' when 2 then 'Promotinal' when 3 then 'Event Based' end as sms_type, case event_id when 0 then 'N/A' else (select outcome_name from form_outcomes where id = event_id) end as event_id from sms_details")
    return render(request, "livestock/list_sms.html",{
        'sms_data':sms_data
    })

def delete_sms(request):
    sms_id = request.POST.get('sms_id')
    try:
        __db_commit_query("delete from sms_details where id = "+str(sms_id))
        return HttpResponse("ok")
    except Exception, e:
        return HttpResponse("error")
    



def sms_details(request):
    divisions = __db_fetch_values_dict("select div_code as id,division as name from vwdivision")
    events = __db_fetch_values_dict("select id,outcome_name from form_outcomes")
    
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
            where_clause = ' where 1 = 1'
            recepient_json['division_id'] = division_id
            recepient_json['district_id'] = district_id
            recepient_json['upazila_id'] = upazila_id
            recepient_json['user_type'] = user_type
            recepient_json['cattle_type'] = cattle_type
            recepient_json['age_range_start'] = age_range_start
            recepient_json['age_range_end'] = age_range_end

            if len(division_id) > 0:
                division_id = "'"+"', '".join(division_id)+"'"
                where_clause += ' and t.division  = any(array['+str(division_id)+'])'
            
            if len(district_id) > 0:
                district_id = "'"+"', '".join(district_id)+"'"
                where_clause += ' and t.district  = any(array['+str(district_id)+'])'

            if len(upazila_id) > 0:
                upazila_id = "'"+"', '".join(upazila_id)+"'"
                where_clause += ' and t.upazila  = any(array['+str(upazila_id)+'])'
            
            if len(cattle_type) > 0:
                cattle_type = "'"+"', '".join(cattle_type)+"'"
                where_clause += ' and t.cattle_type  = any(array['+str(cattle_type)+'])'
            
            if len(user_type) > 0:
                user_type = "'"+"', '".join(user_type)+"'"
                where_clause += ' and t.user_type  = any(array['+str(user_type)+'])'
            
            if age_range_start and age_range_end:
                where_clause += ' and t.c_age::int between symmetric '+str(age_range_start)+' and '+str(age_range_end)

            if where_clause != ' where 1 = 1':
                qry = "with t as(select shurokkha_users.username,shurokkha_users.division,shurokkha_users.district,shurokkha_users.upazila,case shurokkha_users.user_type when 'Paravet' then '2' when 'AI Technicians' then '3' when 'Farmer' then '1' end as user_type,cattle.cattle_type,coalesce(cattle.cattle_age,cattle.calf_age) as c_age from shurokkha_users left join cattle on cattle.mobile = shurokkha_users.username) select DISTINCT username from t " + where_clause
                selected_users = __db_fetch_values_dict(qry)
                schedule_time = schedule_date + ' ' + convert24(trigger_time) + ':00'
                print schedule_time
                for su in selected_users:
                    __db_commit_query("INSERT INTO public.shurokkha_sms_queue (sms_text, voice_sms_file_path, sms_sent_type, dest_no, schedule_time, status, tx_id, sms_type) VALUES('"+str(sms_text)+"', '"+str(uploaded_file_url)+"', "+str(sms_sent_type)+", '"+str(su['username'])+"', '"+str(schedule_time)+"', 0, NULL, "+str(sms_type)+")")

                

        recepient_final = json.dumps(recepient_json)

        __db_commit_query("INSERT INTO public.sms_details (sms_text, voice_clip_loc, sms_sent_type, sms_type, schedule_date, trigger_time, event_id, interval_time, recepient_json) VALUES('"+str(sms_text)+"', '"+str(uploaded_file_url)+"', "+str(sms_sent_type)+", "+str(sms_type)+", '"+str(schedule_date)+"', '"+str(trigger_time)+"', "+str(event_id)+", "+str(interval_time)+", '"+str(recepient_final)+"')")
        
        return HttpResponseRedirect('/livestock/list_sms/')

    return render(request, "livestock/sms_details.html",
    {
        'divisions':divisions,
        'events': events
    })


def convert24(str1):
	if str1[-2:] == "AM" and str1[:2] == "12": 
		return "00" + str1[2:-2]
	elif str1[-2:] == "AM": 
		return str1[:-2] 
	elif str1[-2:] == "PM" and str1[:2] == "12": 
		return str1[:-2] 
	else: 
		return str(int(str1[:2]) + 12) + str1[2:5]
    


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
            value = value[-2:]
            return __db_fetch_single_value("select district from vwdistrict where dist_code='"+str(value)+"'")
        elif type == 3:
            value = value[-2:]
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



def get_recepients_count(request):
    division_id = request.POST.getlist('division_id[]')
    district_id = request.POST.getlist('district_id[]')
    upazila_id = request.POST.getlist('upazila_id[]')
    user_type = request.POST.getlist('user_type[]')
    cattle_type = request.POST.getlist('cattle_type[]')
    age_range_start = request.POST.get('age_range_start')
    age_range_end = request.POST.get('age_range_end')

    where_clause = 'where 1 = 1'

    if division_id:
        division_id = "'"+"', '".join(division_id)+"'"
        where_clause += ' and t.division  = any(array['+str(division_id)+'])'
    
    if district_id:
        district_id = "'"+"', '".join(district_id)+"'"
        where_clause += ' and t.district  = any(array['+str(district_id)+'])'

    if upazila_id:
        upazila_id = "'"+"', '".join(upazila_id)+"'"
        where_clause += ' and t.upazila  = any(array['+str(upazila_id)+'])'
    
    if cattle_type:
        cattle_type = "'"+"', '".join(cattle_type)+"'"
        where_clause += ' and t.cattle_type  = any(array['+str(cattle_type)+'])'
    
    if user_type:
        user_type = "'"+"', '".join(user_type)+"'"
        where_clause += ' and t.user_type  = any(array['+str(user_type)+'])'
    
    if age_range_start and age_range_end:
        where_clause += ' and t.c_age::int between symmetric '+str(age_range_start)+' and '+str(age_range_end)
    
    qry = "with t as(select shurokkha_users.username,shurokkha_users.division,shurokkha_users.district,shurokkha_users.upazila,case shurokkha_users.user_type when 'Paravet' then '2' when 'AI Technicians' then '3' when 'Farmer' then '1' end as user_type,cattle.cattle_type,coalesce(cattle.cattle_age,cattle.calf_age) as c_age from shurokkha_users left join cattle on cattle.mobile = shurokkha_users.username) select count(DISTINCT username) from t " + where_clause
    no_of_selected_users = __db_fetch_single_value(qry)

    return HttpResponse(no_of_selected_users)


def sms_schedule(request):
    #XFORMID = __db_fetch_single_value("select id from logger_xform where id_string= '" + str(id_string) + "'")
    outcomes = __db_fetch_values_dict("select * from form_outcomes")
    # variables = __db_fetch_values_dict(
    #     "select distinct on (field_name) field_name,field_type from xform_extracted where xform_id = " + str(
    #         XFORMID) + " and field_name not in ('username','meta','start','end','meta/instanceID') and field_type not in ('note','repeat','group','hidden','gps','photo','geopoint','date','dateTime')")

    other_forms = __db_fetch_values_dict("select id,title from logger_xform")
    #trigger_types = __db_fetch_values_dict("select id,start_point_name from start_point_def")
    #event_types = __db_fetch_values_dict("select id,event_name from event_def")
    #logics = __db_fetch_values_dict("select id,(select event_name from event_def where id = event_id) as event_name,(select outcome_name from form_outcomes where id = condition_id) as outcome_name, (select title from logger_xform where id = scheduled_form) as scheduled_form, case shedule_applicable_for_id when 1 then 'Woman' when '2' then 'Child' end as participant_type, case sheduled_role_id when 1 then 'FD' when '2' then 'TLI' end as scheduled_role from logic where form_id = " + str(XFORMID))
    #logics = __db_fetch_values_dict(
    #    "select id,(select event_name from event_def where id = event_id) as event_name,(select outcome_name from form_outcomes where id = condition_id) as outcome_name, (select title from logger_xform where id = scheduled_form) as scheduled_form, case shedule_applicable_for_id when 1 then 'Woman' when '3' then 'Household' when '2' then 'Child' else '' end as participant_type, (case sheduled_role_id when 1 then 'admin' when 9 then 'FS' when 10 then 'AC' when 11 then 'TLI' when 12 then 'FD' else '' end)  scheduled_role from logic where form_id = " + str(
    #        XFORMID))
    #roles = __db_fetch_values_dict("select id,role from usermodule_organizationrole")
    return render(request, 'livestock/sms_schedule.html', {
        #'variables': json.dumps(variables),
        #'xformid': XFORMID,
        'outcomes': outcomes,
        'outcomes_json': json.dumps(outcomes),
        'other_forms': json.dumps(other_forms),
        #'trigger_types': trigger_types,
        #'event_types': event_types,
        #'logics': logics,
        #'roles': roles
    })

def get_form_variables_list(request):
    form_id = request.POST.get('form_id')
    variables = __db_fetch_values_dict(
        "select distinct on (field_name) field_name,field_type from xform_extracted where xform_id = " + str(
            form_id) + " and field_name not in ('username','meta','start','end','meta/instanceID') and field_type not in ('note','repeat','group','hidden','gps','photo','geopoint','date','dateTime')")
    return HttpResponse(json.dumps(variables))


def get_form_variable_type(request):
    form_id = request.POST.get('form_id')
    field_name = request.POST.get('field_name')
    field_details = __db_fetch_values_dict(
        "select field_type,value_text,value_label as label_bengali from xform_extracted where xform_id = " + str(
            form_id) + " and field_name = '" + str(field_name) + "'")
    return HttpResponse(json.dumps(field_details))


def insert_form_schedules(request):
    user = request.user.id
    logic_json = request.POST.get('logic_json')
    form_json = request.POST.get('form_json')
    xformid = 0
    outcome_name = request.POST.get('outcome_name')
    outcome_id = request.POST.get('outcome_id')
    if outcome_id != '':
        related_elements = __db_fetch_values_dict(
            "select related_elements from form_outcomes where id = " + str(outcome_id))
        for key, value in related_elements[0]['related_elements'].iteritems():
            if value == 'comparator':
                __db_commit_query("delete from logic_comparator where id =" + str(key))
            elif value == 'block':
                __db_commit_query("delete from logic_block where id =" + str(key))

        __db_commit_query("delete from form_outcomes where id=" + str(outcome_id))

    logic_list = json.loads(logic_json)
    processed_blocks = []
    global final_list
    final_list = {}
    operator = ''
    prev_block = (-1, 'xyz')
    for lg in logic_list:
        operator = lg[0]
        if len(lg) == 1:
            block_id = create_tertiary_block(processed_blocks[-1], processed_blocks[-2], operator, user)
            final_list[block_id] = 'block'
            processed_blocks.append(block_id)
        elif len(lg) == 2:
            c1 = create_comparator(lg[1], user)
            final_list[c1] = 'comparator'
            block_id = create_secondary_block(c1, prev_block[0], operator, user)
            final_list[block_id] = 'block'
            prev_block = (block_id, operator)
            processed_blocks.append(block_id)
        elif len(lg) > 2:
            block_id = process_logic_data(lg, user)
            final_list[block_id] = 'block'
            processed_blocks.append(block_id)
            prev_block = (block_id, operator)

    if len(logic_list[-1]) != 1 and len(processed_blocks) > 1:
        block_id = create_tertiary_block(processed_blocks[-1], processed_blocks[-2], operator, user)
        final_list[block_id] = 'block'

    new_outcome_id = create_outcome(block_id, outcome_name, xformid, logic_json, form_json, json.dumps(final_list))

    return HttpResponse(new_outcome_id)


def process_logic_data(logic_data, user):
    global final_list
    operator = logic_data[0]
    comparators = []
    for i in range(1, len(logic_data), 1):
        c1 = create_comparator(logic_data[i], user)
        final_list[c1] = 'comparator'
        comparators.append(c1)
        if len(comparators) > 2:
            b1 = create_secondary_block(comparators[-1], comparators[-2], operator, user)
            final_list[b1] = 'block'
            comparators.append(b1)
        elif len(comparators) > 1 and len(comparators) < 3:
            b1 = create_primary_block(comparators[-1], comparators[-2], operator, user)
            final_list[b1] = 'block'
            comparators.append(b1)

    return comparators[-1]


def create_outcome(block_id, outcome_name, xformid, logic_json, form_json, related_elements):
    outcome_id = __db_insert_query(
        "INSERT INTO public.form_outcomes (block_id, outcome_name, xformid,logic_json,form_json,related_elements) VALUES(" + str(
            block_id) + ", '" + str(outcome_name) + "', " + str(xformid) + ", '" + str(logic_json) + "', '" + str(
            form_json) + "','" + str(related_elements) + "') returning id")
    return outcome_id


def create_primary_block(c1, c2, operator, user):
    # print "primary"
    block_id = __db_insert_query(
        "INSERT INTO public.logic_block (block_id_1, block_id_2, is_block_1, is_block_2, function_operator, created_by, created_at) VALUES(" + str(
            c1) + ", " + str(c2) + ", 0, 0, '" + str(operator) + "', " + str(user) + ", now()) returning id")
    return block_id


def create_secondary_block(b1, c2, operator, user):
    # print "secondary"
    block_id = __db_insert_query(
        "INSERT INTO public.logic_block (block_id_1, block_id_2, is_block_1, is_block_2, function_operator, created_by, created_at) VALUES(" + str(
            b1) + ", " + str(c2) + ", 0, 1, '" + str(operator) + "', " + str(user) + ", now()) returning id")
    return block_id


def create_tertiary_block(b1, b2, operator, user):
    # print "tertiary"
    block_id = __db_insert_query(
        "INSERT INTO public.logic_block (block_id_1, block_id_2, is_block_1, is_block_2, function_operator, created_by, created_at) VALUES(" + str(
            b1) + ", " + str(b2) + ", 1, 1, '" + str(operator) + "', " + str(user) + ", now()) returning id")
    return block_id


def create_comparator(single_comparator, user):
    if 'source' in single_comparator:
        source = single_comparator['source']
    else:
        source = None

    if 'study_id' in single_comparator:
        study_id = single_comparator['study_id']
    else:
        study_id = None

    if 'form_id' in single_comparator:
        form_id = single_comparator['form_id']
    else:
        form_id = None

    if 'variable_type' in single_comparator:
        variable_type = single_comparator['variable_type']
    else:
        variable_type = None

    if 'variable_name' in single_comparator:
        variable_name = single_comparator['variable_name']
    else:
        variable_name = None

    if 'comparator' in single_comparator:
        comparator = single_comparator['comparator']
        print ("COMPARATOR: "+str(comparator))
        comparator = __db_fetch_single_value(
            "select id from comparator_def where comparator_text = '" + str(comparator) + "'")
    else:
        comparator = None

    if 'value1' in single_comparator:
        value1 = single_comparator['value1']
    else:
        value1 = None

    if 'value2' in single_comparator:
        value2 = single_comparator['value2']
    else:
        value2 = None

    if 'submission_type' in single_comparator:
        submission_type = single_comparator['submission_type']
    else:
        submission_type = None

    cursor = connection.cursor()
    cursor.execute(
        """INSERT INTO public.logic_comparator (variable_source, study_id, form_id, submission_type, variable_name, variable_type, comparator_id, val_1, val_2, created_by, created_at) VALUES(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) returning id""",
        (source, study_id, form_id, submission_type, variable_name, variable_type, comparator, value1, value2, user,
         datetime.now()))

    fetchVal = cursor.fetchone()
    cursor.close()
    comparator_id = fetchVal[0]
    return comparator_id