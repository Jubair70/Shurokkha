#!/usr/bin/env python
# -*- coding: utf-8 -*-
import simplejson
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.db.models import Count, Q
from django.http import (HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response, get_object_or_404, render
from django.forms.formsets import formset_factory
from django.db.models import ProtectedError
from django.db import connection
from onadata.apps.livestock.models import *
import json

from collections import OrderedDict
import pandas as pd
import decimal

import pandas as pd
from onadata.apps.usermodule.models import OrganizationRole, MenuRoleMap, UserRoleMap
from django.contrib.auth.models import User
from django.core.mail import send_mail, BadHeaderError
import smtplib
from datetime import datetime as dt
import time
import os.path
from datetime import date, timedelta, datetime
from pyfcm import FCMNotification
import requests
from django.views.decorators.csrf import csrf_exempt
from onadata.apps.livestock.tasks import prescription_upload

push_service = FCMNotification(
    api_key="AAAA1dBJQYk:APA91bGQf5qjEkdhxxcjnvodj-xMKVWmRPQ2UbBw_qsp4XlxGratkzemLNbF6JYnTIZ1jfRIZ-1e1IaqSZctL_n_i338zF5_5swkRBAiW0PEc4fW_DOl-03jq-aKLKOfOVcHcZMqDLctAXVKOT-kx4XdRRekuIofqg")


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


def makeTableList(tableListQuery):
    cursor = connection.cursor()
    cursor.execute(tableListQuery)
    tableList = list(cursor.fetchall())
    return tableList


##****Json Serialize (Start)**********

def decimal_date_default(obj):
    if isinstance(obj, decimal.Decimal):
        print
        "decimal"
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
        print
        "isoformat"
    else:
        print
        obj
        return obj

    raise TypeError


'''

    MEDICINE::
    ADD,UPLOAD,EDIT,DELETE

'''


@login_required
def medicine_list(request):
    q = "select id,name from medicine_type"
    type_list = makeTableList(q)
    return render(request, "livestock/medicine_list.html", {'type_list': type_list})


def get_medicine_data_table(request):
    q = "select *,(select name from medicine_type where id = medicine.medicine_type limit 1) as m_type from medicine order by id desc"
    dataset = __db_fetch_values_dict(q)
    return render(request, 'livestock/get_medicine_data_table.html',
                  {'dataset': dataset}, status=200)


def add_medicine(request):
    if request.POST:
        medicine_type = request.POST.get('medicine_type')
        medicine_name = request.POST.get('medicine_name')
        pack_size = request.POST.get('pack_size')
        id = request.POST.get('id')
        check_q = "select * from medicine where medicine_type::text like '" + medicine_type + "' and medicine_name like '" + medicine_name + "' and  packsize like '" + pack_size + "' "
        data = __db_fetch_values_dict((check_q))
        if len(data) == 0:
            if id == '':
                q = "INSERT INTO public.medicine(id, medicine_type, medicine_name, packsize, created_at, created_by)VALUES (DEFAULT , '" + medicine_type + "','" + medicine_name + "', '" + pack_size + "', NOW(), " + str(
                    request.user.id) + ");"
            else:
                q = "update public.medicine set medicine_type = " + medicine_type + " ,medicine_name = '" + medicine_name + "',packsize='" + pack_size + "' where id =" + id
            __db_commit_query(q)
        else:
            return HttpResponse(json.dumps(len(data)), content_type="application/json", status=500)

        return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)


def upload_medicine(request):
    des = handle_uploaded_file(request.FILES['ex_file'])
    xlsx = pd.ExcelFile(des)  # open the file
    df = xlsx.parse(0)
    # print pd.__version__
    duplicate_medicine = []
    for index, row in df.iterrows():
        type = row[0]
        type_id = __db_fetch_single_value("select id from medicine_type where name = '" + type + "'")

        name = row[1]
        # single quote replace with double single quote
        if "'" in name:
            name = str(name).replace("'", "''")
        pack_size = row[2]
        check_q = "select * from medicine where medicine_type::text = '" + str(
            type_id) + "' and medicine_name = '" + name + "' and  packsize = '" + pack_size + "' "
        data = __db_fetch_values_dict((check_q))
        if len(data) == 0:
            q = "INSERT INTO public.medicine(id, medicine_type, medicine_name, packsize, created_at, created_by)VALUES (DEFAULT , '" + str(
                type_id) + "','" + name + "', '" + pack_size + "', NOW(), " + str(
                request.user.id) + ");"
            __db_commit_query(q)
        else:
            duplicate_medicine.append(name)
    if len(duplicate_medicine) == 0:
        return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)
    else:
        duplicate_item = ", ".join(str(x) for x in duplicate_medicine)
        duplicate_item = duplicate_item + " already exist."
        return HttpResponse(json.dumps(duplicate_item), content_type="application/json", status=500)


def handle_uploaded_file(file):
    if file:
        filePath = 'onadata/media/' + str(file.name)
        destination = open('onadata/media/' + str(file.name), 'w+')
        for chunk in file.chunks():
            destination.write(chunk)
        destination.close()
    return filePath


def delete_medicine(request, id):
    delete_q = "delete from medicine where id = " + str(id)
    __db_commit_query(delete_q)
    return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)


def edit_medicine(request, id):
    q = "select * from medicine where id =" + str(id)
    dataset = __db_fetch_values_dict(q)
    for temp in dataset:
        data = {
            'med_type': temp['medicine_type'], 'medicine_name': temp['medicine_name'], 'pack_size': temp['packsize']
        }
    return HttpResponse(json.dumps(data), content_type="application/json", status=200)


'''

    FARMER & CATTLE

'''


def send_sms(mobile, sms_text):
    url = "http://api.boom-cast.com/boomcast/WebFramework/boomCastWebService/externalApiSendTextMessage.php?masking=Shurokkha&userName=Shurokkha_mpower&password=982b8ae51fdc7147a9911aa211d1ec21&MsgType=Unicode&"
    try:
        # print url
        urlParameters = "receiver=" + mobile + "&message=" + sms_text;
        print
        "**************************  sending SMS **************************"
        r = requests.get(url + urlParameters)  # data=json.dumps(payload))
        print
        r.status_code
        print
        "**************************  sending SMS  successfull.**************************"
    except Exception, e:
        print
        "sending failed.."
        print
        str(e)
        return


@login_required
def farmer_list(request):
    # send_sms('01840970511','this is test shurokkha sms')
    q = "select (select  id from auth_user where username = mobile) user_id,name from paravet_aitechnician"
    paravet_ai_list = makeTableList(q)
    return render(request, "livestock/farmer_list.html", {'paravet_ai_list': paravet_ai_list})


def get_farmer_table(request):
    user_id = request.POST.get('user_id')
    date_range = request.POST.get('date_range')
    if date_range == '':
        start_date = '01/01/2010'
        end_date = '12/28/2021'
    else:
        dates = get_dates(str(date_range))
        start_date = dates.get('start_date')
        end_date = dates.get('end_date')
    # q = "select *,(select first_name || last_name from auth_user where id= submitted_by ) as user_name from farmer where date(submission_time) between '"+start_date+"' and '"+end_date+"' and submitted_by ::text like '"+str(user_id)+"'"
    q = "with t1 as(select (select mobile from cattle where cattle_system_id = appointment.cattle_system_id) as farmer_mobile,* from appointment),t2 as (select t1.farmer_mobile as farmer_mobile,count(*) num_of_case from t1 group by t1.farmer_mobile),t3 as (select *, (select first_name || last_name from auth_user where id= submitted_by ) as user_name ,(select num_of_case from t2 where farmer_mobile = farmer.mobile) number_cases from farmer where date(submission_time) between '" + start_date + "' and '" + end_date + "' and submitted_by ::text like '" + str(
        user_id) + "') select *,(case when number_cases >0 then number_cases else 0 end) as case_number from t3"
    dataset = __db_fetch_values_dict(q)
    return render(request, "livestock/farmer_table.html", {'dataset': dataset})


@login_required
def approval_list(request):
    q = "with paravet as(select count(*) as paravets from public.approval_queue where status = 0 and role_name ='Paravet'), ai as(select count(*) as ai_techs from public.approval_queue where status = 0 and role_name ='AI Technicians') select paravet.paravets as num_paravet,ai.ai_techs as num_ai_techs from paravet,ai"
    paravet = 0
    ai_tech = 0
    for temp in __db_fetch_values_dict(q):
        paravet = temp['num_paravet']
        ai_tech = temp['num_ai_techs']
    context = {
        'paravet': paravet, 'ai_tech': ai_tech
    }
    return render(request, "livestock/approval_list.html", context)


def get_approval_table(request):
    status = request.POST.get('status')
    q = "select * from approval_queue where  status::text like '" + str(status) + "'"
    dataset = __db_fetch_values_dict(q)
    return render(request, "livestock/approval_table.html", {'dataset': dataset})


def approve(request, id):
    role_name = request.POST.get('role')
    mobile = request.POST.get('mobile')
    name = request.POST.get('name')
    q = "update approval_queue set status = 1,approve_by = " + str(
        request.user.id) + ",approval_date = NOW() where id  =" + str(id)
    __db_commit_query(q)

    __db_commit_query(
        "update usermodule_usermoduleprofile set is_req_para_ai = 0 where user_id=(select id from auth_user where  username='" + mobile + "')")
    role_list = []
    role_list.append(role_name)
    user_roles = OrganizationRole.objects.filter(role__in=role_list)
    user = User.objects.filter(username=mobile).first()
    profile = user.usermoduleprofile
    insert_q = "INSERT INTO public.paravet_aitechnician(id, name, mobile,user_type,submission_time,submitted_by)VALUES (DEFAULT, '" + name + "','" + mobile + "', '" + role_name + "',NOW()," + str(
        user.id) + " );"
    __db_commit_query(insert_q)
    for role in user_roles:
        UserRoleMap(user=profile, role=role).save()
    send_push_message(mobile, 2, 'Paravet/AI Tech approved', 'Please log in again to the app.', '', mobile, '')

    # TO DO ::SMS Notification
    send_mail(
        'Successful Approval',
        'Hi,\n\nWelcome to Shurokkha!!\n\nYou are successfully approved as ' + role_name + '.',
        'mpowersocial2018@gmail.com',
        ['mpowersocialent@gmail.com'],
        fail_silently=False,
    )
    return HttpResponse(json.dumps("Approved Successfully."), content_type="application/json", status=200)


def reject(request, id):
    role = request.POST.get('role')
    mobile = request.POST.get('mobile')
    comment = request.POST.get('comment')
    q = "update approval_queue set status = 2,approve_by = " + str(
        request.user.id) + ",approval_date = NOW(),rejection_cause = '" + comment + "' where id  =" + str(id)
    __db_commit_query(q)
    __db_commit_query(
        "update usermodule_usermoduleprofile set is_req_para_ai = 0 where user_id=(select id from auth_user where  username='" + mobile + "')")

    send_push_message(mobile, 3, 'Paravet/AI Tech rejected', 'Your request has been rejected.', '', mobile, '')
    # TO DO :: SMS Notification
    send_mail(
        'Rejected Approval',
        'Hi,\n\nWelcome to Shurokkha!!\n\nYou are Rejected.',
        'mpowersocial2018@gmail.com',
        ['mpowersocialent@gmail.com'],
        fail_silently=False,
    )
    return HttpResponse(json.dumps("Rejected Successfully."), content_type="application/json", status=200)


def view_ai_paravet_profile(request, id):
    farmer_proupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    farmer_proupdate_form_owner = __db_fetch_single_value(farmer_proupdate_form_owner_q)
    q = "select *,date(submission_time) as s_date, coalesce((select division from vwunion_code where div_code=approval_queue.division limit 1),'') as div_text, coalesce((select district from vwunion_code where dist_code=approval_queue.district limit 1),'')as dist_text, coalesce((select upazila from vwunion_code where up_code=approval_queue.upazila limit 1),'')as up_text from approval_queue where id = " + str(
        id)
    # print q
    dataset = __db_fetch_values_dict(q)
    data_list = []
    age_cattle = 0
    for temp in dataset:
        data_dict = {}
        '''
        if temp['cattle_birth_date'] is not None:
            dob_cattle = temp['cattle_birth_date']
            dob_cf = dt.strptime(temp['cattle_birth_date'], '%Y-%m-%d')
            age_cattle = ((dt.today() - dob_cf).days / 30)
            '''
        data_dict['name'] = temp['name']
        data_dict['mobile'] = temp['mobile']
        data_dict['s_date'] = temp['s_date']
        data_dict['div_text'] = temp['div_text']
        data_dict['dist_text'] = temp['dist_text']
        data_dict['up_text'] = temp['up_text']
        img = ""
        if temp['image'] is not None:
            img = temp['image']
        data_dict['image_url'] = "/media/" + farmer_proupdate_form_owner + "/attachments/" + img
        data_list.append(data_dict.copy())
        data_dict.clear()
    return render(request, 'livestock/ai_paravet_profile.html',
                  {'dataset': data_list})


def farmer_profile(request, id):
    cattle_proupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    cattle_proupdate_form_owner = __db_fetch_single_value(cattle_proupdate_form_owner_q)
    q = "select *,date(submission_time) as regi_date from farmer where id =" + str(id)
    dataset = __db_fetch_values_dict(q)
    return render(request, 'livestock/farmer_profile.html',
                  {'dataset': dataset, 'FARMER_ID': id, 'cattle_proupdate_form_owner': cattle_proupdate_form_owner})


def get_cattle_list(request, id):
    cattle_type = request.POST.get('cattle_type')
    cattle_regi_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'cattle_registration'"
    cattle_regi_form_owner = __db_fetch_single_value(cattle_regi_form_owner_q)
    # q = " select *,get_form_option_text(597,'cattle_type',cattle_type) cattle_type_text,get_form_option_text(597,'cattle_origin',cattle_origin) cattle_origin_text from vwcattle_registration where cattle_type::text  like '"+cattle_type+"'"
    q = " select *,date(created_date)::text as register_date ,(select label from vwcattle_type where value =cattle_type ) cattle_type_text,(select label from vwcattle_origin where value =cattle_origin ) cattle_origin_text from cattle where cattle_type::text  like '" + cattle_type + "' and mobile = (select mobile from cattle where id = " + str(
        id) + ")"
    dataset = __db_fetch_values_dict(q)
    data_list = []
    age_cattle = 0
    for temp in dataset:
        data_dict = {}
        if temp['cattle_birth_date'] is not None:
            dob_cattle = temp['cattle_birth_date']
            dob_cf = dt.strptime(temp['cattle_birth_date'], '%Y-%m-%d')
            age_cattle = ((dt.today() - dob_cf).days / 30)
        else:
            age_cattle = temp['cattle_age']
        data_dict['cattle_type_text'] = temp['cattle_type_text']
        data_dict['cattle_age'] = age_cattle
        data_dict['cattle_system_id'] = temp['cattle_system_id']
        img = ""
        if temp['picture'] is not None:
            img = temp['picture']
        data_dict['image_url'] = "/media/" + cattle_regi_form_owner + "/attachments/" + img
        data_list.append(data_dict.copy())
        data_dict.clear()
    return render(request, 'livestock/cattle_list_table.html',
                  {'dataset': data_list, 'cattle_regi_form_owner': cattle_regi_form_owner})


def upload_prescription(request):
    if request.method == 'POST':
        file = request.FILES['ex_file']
        millis = int(round(time.time() * 1000))
        if file:
            filePath = 'onadata/media/prescription/' + str(millis) + '_' + str(file.name)
            destination = open('onadata/media/prescription/' + str(millis) + '_' + str(file.name), 'w+')
            for chunk in file.chunks():
                destination.write(chunk)
            destination.close()
        des = filePath
        xlsx = pd.ExcelFile(des)  # open the file
        df = xlsx.parse(0)  # get the first sheet as an object
        async_result = prescription_upload.delay(df, request.user.id)
        return_value = async_result.get()
        print
        return_value
        '''
        df = df.fillna({'Medicine Type':0,'Type':0,'Advices' :0,'Dose' : 0,'Route' : 0,'Days' :0,'Medine Name' : 0}, inplace=True)

        duplicate_diagnosis = []
        df_1 = df.groupby(['Tentative Diagnosis', 'Type','Body Weight From','Body Weight To']).size().reset_index(name='Freq')
        for index_1,row_1 in df_1.iterrows():
            diagnosis_1 =  row_1[0]
            type_1 = row_1[1].encode('utf-8')
            cattle_type_id = __db_fetch_single_value(
                "select value from vwcattle_type where label = '" + type_1 + "'")
            weight_from_1 = row_1[2]
            weight_to_1 = row_1[3]
            check_q = "select id from diagnosis where diagnosis_name::text like '"+ diagnosis_1 + "' and cattle_type::text like '" + str(cattle_type_id) + "' and  weight_from::text like '" + str(weight_from_1) + "' and  weight_to::text like '" + str(weight_to_1) + "'"
            data = __db_fetch_values_dict((check_q))
            if len(data) != 0:
                delete_duplicate_presciption_diagnosis(data)
            insert_diagnosis_q = "INSERT INTO public.diagnosis(id, diagnosis_name, cattle_type, weight_from, weight_to, created_by, created_date)VALUES (DEFAULT ,'" + diagnosis_1 + "', " + str(
                cattle_type_id) + ", " + str(weight_from_1) + ", " + str(weight_to_1) + ", " + str(
                request.user.id) + ", NOW())  RETURNING id;"
            inserted_id = __db_fetch_single_value(insert_diagnosis_q)
            df_filtered = df[(df['Tentative Diagnosis'] == diagnosis_1) & (df['Body Weight From'] == weight_from_1) & (
            df['Body Weight To'] == weight_to_1)]
            for index, row in df_filtered.iterrows():
                #*** Diagnosis *******#
                diagnosis_name = row[0]
                description_type = row[1]
                if row[2] !=0:
                    cattle_type = row[2].encode('utf-8')
                else:
                    cattle_type = ''

                #print cattle_type_id
                weight_from = row[3]
                weight_to = row[4]

                # *** Medicine *******#
                med_type = row[5]

                if med_type != 0:
                    med_type_id = __db_fetch_single_value("select id from medicine_type where name = '" + med_type + "'")
                else:
                    med_type_id = 0
                #print med_type_id
                #med_name = row[6]
                packsize = row[7]
                qty = row[8]
                #dose = row[9]
                #route = row[10]
                #days = row[11]
                if row[12] != 0:
                    advice = row[12].encode('utf-8')
                else:
                    advice = ''
                if row[9] == 0:
                    dose = ''
                else:
                    dose = row[9]
                if row[10] == 0:
                    route = ''
                else:
                    route = row[10]
                if row[11] == 0:
                    days = ''
                else:
                    days = row[11]

                if row[6] == 0:
                   med_name = ''
                else:
                    med_name = row[6]

                if ((diagnosis_1 == diagnosis_name) and (type_1 == cattle_type) and (weight_from_1 == weight_from) and (weight_to_1 == weight_to )):
                    if description_type == 'M':
                        insert_diagnosis_medicine_q = "INSERT INTO public.diagnosis_medicine(id, diagnosis_id, medicine_type, medicine_name, packsize, quantity, dose, route, days)" \
                                                      "VALUES (DEFAULT, "+str(inserted_id)+", "+str(med_type_id)+", '"+med_name+"', '"+packsize+"', "+str(qty)+", '"+dose+"', '"+route+"', '"+days+"');"
                        __db_commit_query(insert_diagnosis_medicine_q)
                    if description_type == 'A':
                        insert_diagnosis_advice_q = "INSERT INTO public.diagnosis_advice(id, diagnosis_id, advice)VALUES (DEFAULT , "+str(inserted_id)+", '"+advice+"');"
                        __db_commit_query(insert_diagnosis_advice_q)

        if len(duplicate_diagnosis) == 0:
            return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)
        else:
            duplicate_item = ", ".join(x for x in duplicate_diagnosis)
            #duplicate_item = duplicate_item + " already exist."
            return HttpResponse(json.dumps(duplicate_item), content_type="application/json", status=500)
    '''
        if return_value == 1:
            return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)
        else:
            return HttpResponse(json.dumps('Error Occured.'), content_type="application/json", status=500)

    return render(request, 'livestock/upload_prescription.html')


@login_required
def prescription(request):
    q = "select * from vwcattle_type"
    cattle_type_list = makeTableList(q)
    return render(request, 'livestock/prescription.html', {'cattle_type_list': cattle_type_list})


def get_prescription_table(request):
    tentative_diagnosis = request.POST.get('tentative_diagnosis')
    cattle_type = request.POST.get('cattle_type')
    medicine_name = request.POST.get('medicine_name')
    q = "SELECT diagnosis.*,diagnosis_medicine.*,(select name from medicine_type where id =diagnosis_medicine.medicine_type limit 1 ) m_type,(select label from vwcattle_type where value::Integer =diagnosis.cattle_type limit 1)cattle,(select advice from diagnosis_advice where diagnosis_id = diagnosis.id limit 1) advice FROM diagnosis LEFT JOIN diagnosis_medicine ON diagnosis.id = diagnosis_medicine.diagnosis_id where diagnosis.diagnosis_name ~* '" + tentative_diagnosis + "' and cattle_type::text like '" + str(
        cattle_type) + "' and diagnosis_medicine.medicine_name ~* '" + medicine_name + "' order by diagnosis.id"
    dataset = __db_fetch_values_dict(q)
    return render(request, 'livestock/prescription_table.html', {'dataset': dataset})


'''
     CATTLE PROFILE

'''


def get_accoridian_dict(cattle_id):
    data = []
    # query = "WITH t AS( SELECT logger_id,rpt_date, question, val FROM get_health_records_web_report('"+str(cattle_id)+"')) ( SELECT logger_id,'feeding_information' AS title, rpt_date, String_agg(question || ': ' || val || '<br><br>','') AS content FROM t WHERE question::text = ANY('{দৈনিক খাওয়ানো সবুজ ঘাসের পরিমান(কেজি),দৈনিক খাওয়ানো শুকনো খড়ের পরিমান (কেজি),দৈনিক খাওয়ানো দানাদার খাদ্যের পরিমান (কেজি),দানাদার খাদ্যের উপকরণ কি কি?,ভুষির পরিমাণ (কেজি),চালের কুঁড়ার পরিমাণ (কেজি),ভুট্টা ভাঙ্গা / আটার পরিমাণ (কেজি),খৈলের পরিমাণ (কেজি),লবণের পরিমাণ (গ্রাম),লালি/চিটাগুড়ের পরিমাণ (কেজি)}') group BY rpt_date,logger_id ORDER BY rpt_date DESC) UNION ALL ( SELECT logger_id,'milk_production' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content FROM t WHERE question::text = ANY('{গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,কত দিন যাবৎ দুধ দোহন করা বন্ধ আছে?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY rpt_date,logger_id ORDER BY rpt_date DESC) UNION ALL ( SELECT logger_id,'deworming_vaccination' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content FROM t WHERE question::text = ANY('{গরুটিকে ক্রিমিমুক্তকরন করা হয়েছে?,কত মাস পূর্বে কৃমিমুক্তকরন করেছিলেন? (সঠিক জানা না থাকলে আনুমানিক),সর্বশেষ ভিজিটের পর থেকে আজ পর্যন্ত এই গরুর জন্য নিম্নের কোন কোন কাজ করা হয়েছে?(তবে এটি প্রথম ভিজিট হলে, গরুটির এযাবৎ কালের সকল কাজের তথ্য দিন),কত মাস পূর্বে তড়কা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে গলাফুলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে ক্ষুরা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে বাদলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক)}') GROUP BY rpt_date,logger_id ORDER BY rpt_date DESC) UNION ALL ( SELECT logger_id,'sickness' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content FROM get_sickness_web_report('"+str(cattle_id)+"') WHERE question::text = ANY('{তাপমাত্রা (ফারেনহাইট),পুর্ববর্তী মোট বাছুরের সংখ্যা,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,গরুটির বর্তমান প্রজনন অবস্থা?,আপনার গরুকে প্রজনন করানো হয়েছে?,প্রজননের ধরন?,প্রজননের তারিখ?,গর্ভবস্থার কোন পর্যায়ে আছে?,গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY rpt_date,logger_id ORDER BY rpt_date DESC) UNION ALL ( SELECT logger_id,'reproduction' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content FROM get_reproduction_web_report('"+str(cattle_id)+"') WHERE question::text = ANY('{প্রজননের তারিখ?,এই প্রজননটির পুর্বে গরুটিকে পরপর কত বার ব্যর্থ কৃত্রিম প্রজনন করা হয়েছে?,কৃত্রিম প্রজননে ব্যবহৃত বীজ-এর ধরণ?,অন্যান্য হলে, লিখুন,ষাঁড় -এর নাম্বার,ষাঁড় -এর বিদেশি জাতের %,বর্তমানে প্রজনন সংক্রান্ত কি সমস্যা আছে?,গরুটির বর্তমান গর্ভবস্থা,গর্ভ পরীক্ষা করিয়েছিলেন?,গর্ভ পরীক্ষার তারিখ,গর্ভের বয়স (মাস),পুর্ববর্তী মোট বাছুরের সংখ্যা,বাছুর প্রসবের তারিখ,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,বাছুরের লিঙ্গ,বাছুরের জন্মকালীন ওজন(কে.জি.),গাভীর কি গর্ভকালীন, বাছুর প্রসব কালীন ও পরবর্তী কি জটিলতা হয়েছিল?,অন্যান্য হলে, লিখুন}') GROUP BY rpt_date,logger_id ORDER BY rpt_date DESC)"
    # query = "WITH t AS( SELECT logger_id, rpt_date, question, val FROM get_health_records_web_report('"+str(cattle_id)+"')) ( SELECT logger_id, 'feeding_information' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images FROM t WHERE question::text = ANY('{দৈনিক খাওয়ানো সবুজ ঘাসের পরিমান(কেজি),দৈনিক খাওয়ানো শুকনো খড়ের পরিমান (কেজি),দৈনিক খাওয়ানো দানাদার খাদ্যের পরিমান (কেজি),দানাদার খাদ্যের উপকরণ কি কি?,ভুষির পরিমাণ (কেজি),চালের কুঁড়ার পরিমাণ (কেজি),ভুট্টা ভাঙ্গা / আটার পরিমাণ (কেজি),খৈলের পরিমাণ (কেজি),লবণের পরিমাণ (গ্রাম),লালি/চিটাগুড়ের পরিমাণ (কেজি)}') GROUP BY rpt_date, logger_id ORDER BY rpt_date DESC) UNION ALL ( SELECT logger_id, 'milk_production' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images FROM t WHERE question::text = ANY('{গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,কত দিন যাবৎ দুধ দোহন করা বন্ধ আছে?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY rpt_date, logger_id ORDER BY rpt_date DESC) UNION ALL ( SELECT logger_id, 'deworming_vaccination' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images FROM t WHERE question::text = ANY('{গরুটিকে ক্রিমিমুক্তকরন করা হয়েছে?,কত মাস পূর্বে কৃমিমুক্তকরন করেছিলেন? (সঠিক জানা না থাকলে আনুমানিক),সর্বশেষ ভিজিটের পর থেকে আজ পর্যন্ত এই গরুর জন্য নিম্নের কোন কোন কাজ করা হয়েছে?(তবে এটি প্রথম ভিজিট হলে, গরুটির এযাবৎ কালের সকল কাজের তথ্য দিন),কত মাস পূর্বে তড়কা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে গলাফুলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে ক্ষুরা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে বাদলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক)}') GROUP BY rpt_date, logger_id ORDER BY rpt_date DESC) UNION ALL ( with sck as( select logger_id,rpt_date,question,val FROM get_sickness_web_report('"+str(cattle_id)+"')), sck1 as ( SELECT logger_id,rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content from sck WHERE question::text = ANY('{তাপমাত্রা (ফারেনহাইট),পুর্ববর্তী মোট বাছুরের সংখ্যা,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,গরুটির বর্তমান প্রজনন অবস্থা?,আপনার গরুকে প্রজনন করানো হয়েছে?,প্রজননের ধরন?,প্রজননের তারিখ?,গর্ভবস্থার কোন পর্যায়ে আছে?,গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার),এই গরুটির চিকিৎসা সেবার জন্য খামারী আপনাকে কত টাকা দিয়েছেন বা দিবেন?}') GROUP BY rpt_date, logger_id), sck2 as ( SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\"  style=\"max-width:230px;max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from sck WHERE question::text = ANY('{রোগের লক্ষণ বোঝাযায় এমন সুনিদিষ্ট ছবি তুলুন}') GROUP BY rpt_date, logger_id )select sck1.logger_id,'sickness' AS title,sck1.rpt_date,content,coalesce(images,'') images from sck1 left join sck2 on sck1.logger_id = sck2.logger_id ) UNION ALL ( SELECT logger_id, 'reproduction' AS title, rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images FROM get_reproduction_web_report('"+str(cattle_id)+"') WHERE question::text = ANY('{প্রজননের তারিখ?,এই প্রজননটির পুর্বে গরুটিকে পরপর কত বার ব্যর্থ কৃত্রিম প্রজনন করা হয়েছে?,কৃত্রিম প্রজননে ব্যবহৃত বীজ-এর ধরণ?,অন্যান্য হলে, লিখুন,ষাঁড় -এর নাম্বার,ষাঁড় -এর বিদেশি জাতের %,বর্তমানে প্রজনন সংক্রান্ত কি সমস্যা আছে?,গরুটির বর্তমান গর্ভবস্থা,গর্ভ পরীক্ষা করিয়েছিলেন?,গর্ভ পরীক্ষার তারিখ,গর্ভের বয়স (মাস),পুর্ববর্তী মোট বাছুরের সংখ্যা,বাছুর প্রসবের তারিখ,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,বাছুরের লিঙ্গ,বাছুরের জন্মকালীন ওজন(কে.জি.),গাভীর কি গর্ভকালীন, বাছুর প্রসব কালীন ও পরবর্তী কি জটিলতা হয়েছিল?,অন্যান্য হলে, লিখুন}') GROUP BY rpt_date, logger_id ORDER BY rpt_date DESC)"
    # query = "WITH t AS( SELECT logger_id, rpt_date, question, val FROM get_health_records_web_report('" + str(
    #     cattle_id) + "')) , health1 as ( SELECT logger_id,rpt_date,string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-width:230px;max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from t WHERE question::text = ANY('{গরুটির একটি পরিপূর্ণ ছবি তুলুন,খাবারের পাত্রসহ গোয়াল ঘরের ছবি তুলুন}') GROUP BY logger_id,rpt_date) ( SELECT t.logger_id, 'feeding_information' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,images FROM t left join health1 on t.logger_id = health1.logger_id WHERE question::text = ANY('{দৈনিক খাওয়ানো সবুজ ঘাসের পরিমান(কেজি),দৈনিক খাওয়ানো শুকনো খড়ের পরিমান (কেজি),দৈনিক খাওয়ানো দানাদার খাদ্যের পরিমান (কেজি),দানাদার খাদ্যের উপকরণ কি কি?,ভুষির পরিমাণ (কেজি),চালের কুঁড়ার পরিমাণ (কেজি),ভুট্টা ভাঙ্গা / আটার পরিমাণ (কেজি),খৈলের পরিমাণ (কেজি),লবণের পরিমাণ (গ্রাম),লালি/চিটাগুড়ের পরিমাণ (কেজি)}') GROUP BY t.rpt_date, t.logger_id,images ORDER BY t.rpt_date DESC) UNION ALL (SELECT t.logger_id, 'milk_production' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,images FROM t left join health1 on t.logger_id = health1.logger_id WHERE question::text = ANY('{গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,কত দিন যাবৎ দুধ দোহন করা বন্ধ আছে?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY t.rpt_date, t.logger_id,images ORDER BY t.rpt_date DESC) UNION ALL ( SELECT t.logger_id, 'deworming_vaccination' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,images FROM t left join health1 on t.logger_id = health1.logger_id WHERE question::text = ANY('{গরুটিকে ক্রিমিমুক্তকরন করা হয়েছে?,কত মাস পূর্বে কৃমিমুক্তকরন করেছিলেন? (সঠিক জানা না থাকলে আনুমানিক),সর্বশেষ ভিজিটের পর থেকে আজ পর্যন্ত এই গরুর জন্য নিম্নের কোন কোন কাজ করা হয়েছে?(তবে এটি প্রথম ভিজিট হলে, গরুটির এযাবৎ কালের সকল কাজের তথ্য দিন),কত মাস পূর্বে তড়কা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে গলাফুলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে ক্ষুরা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে বাদলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক)}') GROUP BY t.rpt_date, t.logger_id,images ORDER BY t.rpt_date DESC) UNION ALL ( with sck as( select logger_id,rpt_date,question,val FROM get_sickness_web_report('" + str(
    #     cattle_id) + "') ), sck1 as ( SELECT logger_id,rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content from sck WHERE question::text = ANY('{তাপমাত্রা (ফারেনহাইট),পুর্ববর্তী মোট বাছুরের সংখ্যা,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,গরুটির বর্তমান প্রজনন অবস্থা?,আপনার গরুকে প্রজনন করানো হয়েছে?,প্রজননের ধরন?,প্রজননের তারিখ?,গর্ভবস্থার কোন পর্যায়ে আছে?,গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY rpt_date, logger_id), sck2 as ( SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-width:230px;max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from sck WHERE question::text = ANY('{রোগের লক্ষণ বোঝাযায় এমন সুনিদিষ্ট ছবি তুলুন,গরুটির পূর্বের কোন প্রেসক্রিপশন থাকলে প্রেসক্রিপশনটির ছবি তুলুন,গরুটির একটি পরিপূর্ণ ছবি তুলুন}') GROUP BY rpt_date, logger_id )select sck1.logger_id,'sickness' AS title,sck1.rpt_date,content,coalesce(images,'') images from sck1 left join sck2 on sck1.logger_id = sck2.logger_id order by sck1.rpt_date desc ) UNION ALL ( with t as ( select logger_id,rpt_date,question,val FROM get_reproduction_web_report('" + str(
    #     cattle_id) + "') ), repro as (SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-width:230px;max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from t WHERE question::text = ANY('{গরুটির একটি পরিপূর্ণ ছবি তুলুন}') GROUP BY rpt_date, logger_id ) SELECT t.logger_id, 'reproduction' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,images FROM t left join health1 on t.logger_id = health1.logger_id WHERE question::text = ANY('{প্রজননের তারিখ?,এই প্রজননটির পুর্বে গরুটিকে পরপর কত বার ব্যর্থ কৃত্রিম প্রজনন করা হয়েছে?,কৃত্রিম প্রজননে ব্যবহৃত বীজ-এর ধরণ?,অন্যান্য হলে, লিখুন,ষাঁড় -এর নাম্বার,ষাঁড় -এর বিদেশি জাতের %,বর্তমানে প্রজনন সংক্রান্ত কি সমস্যা আছে?,গরুটির বর্তমান গর্ভবস্থা,গর্ভ পরীক্ষা করিয়েছিলেন?,গর্ভ পরীক্ষার তারিখ,গর্ভের বয়স (মাস),পুর্ববর্তী মোট বাছুরের সংখ্যা,বাছুর প্রসবের তারিখ,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,বাছুরের লিঙ্গ,বাছুরের জন্মকালীন ওজন(কে.জি.),গাভীর কি গর্ভকালীন, বাছুর প্রসব কালীন ও পরবর্তী কি জটিলতা হয়েছিল?,অন্যান্য হলে, লিখুন}') GROUP BY t.rpt_date, t.logger_id,images ORDER BY t.rpt_date desc )"
    # query = "WITH t AS( SELECT logger_id, rpt_date, question, val FROM get_health_records_web_report('" + str(
    #     cattle_id) + "')) , health1 as ( SELECT logger_id,rpt_date,string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-width:230px;max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from t WHERE question::text = ANY('{গরুটির একটি পরিপূর্ণ ছবি তুলুন,খাবারের পাত্রসহ গোয়াল ঘরের ছবি তুলুন}') GROUP BY logger_id,rpt_date), health2 as ( select logger_id,'<span>' || question || ': ' || val || ' টাকা' || '</span>' as pay from t where question::text = ANY('{এই গরুটির চিকিৎসা বা পরামর্শ সেবার জন্য খামারী আপনাকে কত টাকা দিয়েছেন বা দিবেন?}') ) ( SELECT t.logger_id, 'feeding_information' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,images,pay FROM (t left join health1 on t.logger_id = health1.logger_id) left join health2 on t.logger_id = health2.logger_id WHERE question::text = ANY('{দৈনিক খাওয়ানো সবুজ ঘাসের পরিমান(কেজি),দৈনিক খাওয়ানো শুকনো খড়ের পরিমান (কেজি),দৈনিক খাওয়ানো দানাদার খাদ্যের পরিমান (কেজি),দানাদার খাদ্যের উপকরণ কি কি?,ভুষির পরিমাণ (কেজি),চালের কুঁড়ার পরিমাণ (কেজি),ভুট্টা ভাঙ্গা / আটার পরিমাণ (কেজি),খৈলের পরিমাণ (কেজি),লবণের পরিমাণ (গ্রাম),লালি/চিটাগুড়ের পরিমাণ (কেজি)}') GROUP BY t.rpt_date, t.logger_id,images,pay ORDER BY t.rpt_date DESC) UNION ALL (SELECT t.logger_id, 'milk_production' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images,null as pay FROM t WHERE question::text = ANY('{গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,কত দিন যাবৎ দুধ দোহন করা বন্ধ আছে?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY t.rpt_date, t.logger_id ORDER BY t.rpt_date DESC) UNION ALL ( SELECT t.logger_id, 'deworming_vaccination' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images,null as pay FROM t WHERE question::text = ANY('{গরুটিকে ক্রিমিমুক্তকরন করা হয়েছে?,কত মাস পূর্বে কৃমিমুক্তকরন করেছিলেন? (সঠিক জানা না থাকলে আনুমানিক),সর্বশেষ ভিজিটের পর থেকে আজ পর্যন্ত এই গরুর জন্য নিম্নের কোন কোন কাজ করা হয়েছে?(তবে এটি প্রথম ভিজিট হলে, গরুটির এযাবৎ কালের সকল কাজের তথ্য দিন),কত মাস পূর্বে তড়কা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে গলাফুলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে ক্ষুরা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে বাদলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক)}') GROUP BY t.rpt_date, t.logger_id ORDER BY t.rpt_date DESC) UNION ALL ( with sck as( select logger_id,rpt_date,question,val FROM get_sickness_web_report('" + str(
    #     cattle_id) + "') ), sck1 as ( SELECT logger_id,rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content from sck WHERE question::text = ANY('{তাপমাত্রা (ফারেনহাইট),পুর্ববর্তী মোট বাছুরের সংখ্যা,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,গরুটির বর্তমান প্রজনন অবস্থা?,আপনার গরুকে প্রজনন করানো হয়েছে?,প্রজননের ধরন?,প্রজননের তারিখ?,গর্ভবস্থার কোন পর্যায়ে আছে?,গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY rpt_date, logger_id), sck2 as ( SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-width:230px;max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from sck WHERE question::text = ANY('{রোগের লক্ষণ বোঝাযায় এমন সুনিদিষ্ট ছবি তুলুন,গরুটির পূর্বের কোন প্রেসক্রিপশন থাকলে প্রেসক্রিপশনটির ছবি তুলুন,গরুটির একটি পরিপূর্ণ ছবি তুলুন}') GROUP BY rpt_date, logger_id ) , sck3 as ( select logger_id,'<span>' || question || ': ' || val || ' টাকা' || '</span>' as pay from sck where question::text = ANY('{এই গরুটির চিকিৎসা সেবার জন্য খামারী আপনাকে কত টাকা দিয়েছেন বা দিবেন?}') ) select sck1.logger_id,'sickness' AS title,sck1.rpt_date,content,coalesce(images,'') images,pay from (sck1 left join sck2 on sck1.logger_id = sck2.logger_id)left join sck3 on sck1.logger_id = sck3.logger_id order by sck1.rpt_date desc ) UNION ALL ( with t as ( select logger_id,rpt_date,question,val FROM get_reproduction_web_report('" + str(
    #     cattle_id) + "') ), repro as (SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-width:230px; max-height: 173px;\" alt=\"Not Found\"></div>','') AS images from t WHERE question::text = ANY('{গরুটির একটি পরিপূর্ণ ছবি তুলুন}') GROUP BY rpt_date, logger_id ) SELECT t.logger_id, 'reproduction' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,images,null as pay FROM t left join repro on t.logger_id = repro.logger_id WHERE question::text = ANY('{প্রজননের তারিখ?,এই প্রজননটির পুর্বে গরুটিকে পরপর কত বার ব্যর্থ কৃত্রিম প্রজনন করা হয়েছে?,কৃত্রিম প্রজননে ব্যবহৃত বীজ-এর ধরণ?,অন্যান্য হলে, লিখুন,ষাঁড় -এর নাম্বার,ষাঁড় -এর বিদেশি জাতের %,বর্তমানে প্রজনন সংক্রান্ত কি সমস্যা আছে?,গরুটির বর্তমান গর্ভবস্থা,গর্ভ পরীক্ষা করিয়েছিলেন?,গর্ভ পরীক্ষার তারিখ,গর্ভের বয়স (মাস),পুর্ববর্তী মোট বাছুরের সংখ্যা,বাছুর প্রসবের তারিখ,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,বাছুরের লিঙ্গ,বাছুরের জন্মকালীন ওজন(কে.জি.),গাভীর কি গর্ভকালীন, বাছুর প্রসব কালীন ও পরবর্তী কি জটিলতা হয়েছিল?,অন্যান্য হলে, লিখুন}') GROUP BY t.rpt_date, t.logger_id,images ORDER BY t.rpt_date desc )"
    query = "WITH t AS( SELECT logger_id, rpt_date, question, val FROM get_health_records_web_report('" + str(
        cattle_id) + "')) , health1 as ( SELECT logger_id,rpt_date,string_agg('<div class=\"carousel-item\"><a href=\"/media/sh_admin/attachments/'|| val ||'\" ><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-height: 173px;\" alt=\"Not Found\"></a></div>','') AS images from t WHERE question::text = ANY('{গরুটির একটি পরিপূর্ণ ছবি তুলুন,খাবারের পাত্রসহ গোয়াল ঘরের ছবি তুলুন}') GROUP BY logger_id,rpt_date), health2 as ( select logger_id,'<span>' || question || ': ' || val || ' টাকা' || '</span>' as pay from t where question::text = ANY('{এই গরুটির চিকিৎসা বা পরামর্শ সেবার জন্য খামারী আপনাকে কত টাকা দিয়েছেন বা দিবেন?}') ), health3 as ( select logger_id,'<audio preload=\"metadata\" controls><source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/mp4; codecs=\"mp4a.40.2\"''/> <source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/mpeg; codecs=\"vorbis\"''/> <source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/ogg; codecs=\"vorbis\"''/></audio>' as audio from t where question::text = 'খামারীর প্রধান সমস্যা (গরুটি সম্পর্কে), কথায় রেকর্ড করুণ' )(SELECT t.logger_id, 'feeding_information' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,coalesce(images,'') images, coalesce(pay,'') pay,coalesce(audio,'') audio FROM ((t left join health1 on t.logger_id = health1.logger_id) left join health2 on t.logger_id = health2.logger_id) left join health3 on t.logger_id = health3.logger_id WHERE question::text = ANY('{দৈনিক খাওয়ানো সবুজ ঘাসের পরিমান(কেজি),দৈনিক খাওয়ানো শুকনো খড়ের পরিমান (কেজি),দৈনিক খাওয়ানো দানাদার খাদ্যের পরিমান (কেজি),দানাদার খাদ্যের উপকরণ কি কি?,ভুষির পরিমাণ (কেজি),চালের কুঁড়ার পরিমাণ (কেজি),ভুট্টা ভাঙ্গা / আটার পরিমাণ (কেজি),খৈলের পরিমাণ (কেজি),লবণের পরিমাণ (গ্রাম),লালি/চিটাগুড়ের পরিমাণ (কেজি)}') GROUP BY t.rpt_date, t.logger_id,images,pay,audio ORDER BY t.rpt_date DESC) UNION ALL (SELECT t.logger_id, 'milk_production' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images,null as pay,null as audio FROM t WHERE question::text = ANY('{গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,কত দিন যাবৎ দুধ দোহন করা বন্ধ আছে?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY t.rpt_date, t.logger_id ORDER BY t.rpt_date DESC) UNION ALL ( SELECT t.logger_id, 'deworming_vaccination' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,null as images,null as pay,null as audio FROM t WHERE question::text = ANY('{গরুটিকে ক্রিমিমুক্তকরন করা হয়েছে?,কত মাস পূর্বে কৃমিমুক্তকরন করেছিলেন? (সঠিক জানা না থাকলে আনুমানিক),সর্বশেষ ভিজিটের পর থেকে আজ পর্যন্ত এই গরুর জন্য নিম্নের কোন কোন কাজ করা হয়েছে?(তবে এটি প্রথম ভিজিট হলে, গরুটির এযাবৎ কালের সকল কাজের তথ্য দিন),কত মাস পূর্বে তড়কা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে গলাফুলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে ক্ষুরা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে বাদলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক)}') GROUP BY t.rpt_date, t.logger_id ORDER BY t.rpt_date DESC) UNION ALL ( with sck as( select logger_id,rpt_date,question,val FROM get_sickness_web_report('" + str(
        cattle_id) + "') ), sck1 as ( SELECT logger_id,rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content from sck WHERE question::text = ANY('{তাপমাত্রা (ফারেনহাইট),পুর্ববর্তী মোট বাছুরের সংখ্যা,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,গরুটির বর্তমান প্রজনন অবস্থা?,আপনার গরুকে প্রজনন করানো হয়েছে?,প্রজননের ধরন?,প্রজননের তারিখ?,গর্ভবস্থার কোন পর্যায়ে আছে?,গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') GROUP BY rpt_date, logger_id), sck2 as ( SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><a href=\"/media/sh_admin/attachments/'|| val ||'\" ><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\"max-height: 173px;\" alt=\"Not Found\"></a></div>','') AS images from sck WHERE question::text = ANY('{রোগের লক্ষণ বোঝাযায় এমন সুনিদিষ্ট ছবি তুলুন,গরুটির পূর্বের কোন প্রেসক্রিপশন থাকলে প্রেসক্রিপশনটির ছবি তুলুন,গরুটির একটি পরিপূর্ণ ছবি তুলুন}') GROUP BY rpt_date, logger_id ) , sck3 as ( select logger_id,'<span>' || question || ': ' || val || ' টাকা' || '</span>' as pay from sck where question::text = ANY('{এই গরুটির চিকিৎসা সেবার জন্য খামারী আপনাকে কত টাকা দিয়েছেন বা দিবেন?}') ), sck4 as ( select logger_id,'<audio preload=\"metadata\" controls><source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/mp4; codecs=\"mp4a.40.2\"''/> <source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/mpeg; codecs=\"vorbis\"''/> <source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/ogg; codecs=\"vorbis\"''/></audio>' as audio from sck where question::text = 'খামারীর প্রধান সমস্যা (গরুটি সম্পর্কে), কথায় রেকর্ড করুণ' ) select sck1.logger_id,'sickness' AS title,sck1.rpt_date,content,coalesce(images,'') images,coalesce(pay,'') pay,coalesce(audio,'') audio from ((sck1 left join sck2 on sck1.logger_id = sck2.logger_id)left join sck3 on sck1.logger_id = sck3.logger_id) left join sck4 on sck1.logger_id = sck4.logger_id order by sck1.rpt_date desc ) UNION ALL ( with t as ( select logger_id,rpt_date,question,val FROM get_reproduction_web_report('" + str(
        cattle_id) + "') ), repro as (SELECT logger_id,rpt_date, string_agg('<div class=\"carousel-item\"><a href=\"/media/sh_admin/attachments/'|| val ||'\" ><img src=\"/media/sh_admin/attachments/'|| val ||'\" style=\" max-height: 173px; \" alt=\"Not Found\"></a></div>','') AS images from t WHERE question::text = ANY('{গরুটির একটি পরিপূর্ণ ছবি তুলুন}') GROUP BY rpt_date, logger_id ), repro1 as ( select logger_id,'<audio preload=\"metadata\" controls><source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/mp4; codecs=\"mp4a.40.2\"''/> <source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/mpeg; codecs=\"vorbis\"''/> <source src=\"/media/sh_admin/attachments/' || val || '\" type=''audio/ogg; codecs=\"vorbis\"''/></audio>' as audio from t where question::text = 'খামারীর প্রধান সমস্যা (গরুটি সম্পর্কে), কথায় রেকর্ড করুণ' ) SELECT t.logger_id, 'reproduction' AS title, t.rpt_date, string_agg(question || ': ' || val || '<br><br>','') AS content,coalesce(images,'') images,null as pay,coalesce(audio,'') audio FROM (t left join repro on t.logger_id = repro.logger_id) left join repro1 on t.logger_id = repro1.logger_id WHERE question::text = ANY('{প্রজননের তারিখ?,এই প্রজননটির পুর্বে গরুটিকে পরপর কত বার ব্যর্থ কৃত্রিম প্রজনন করা হয়েছে?,কৃত্রিম প্রজননে ব্যবহৃত বীজ-এর ধরণ?,অন্যান্য হলে, লিখুন,ষাঁড় -এর নাম্বার,ষাঁড় -এর বিদেশি জাতের %,বর্তমানে প্রজনন সংক্রান্ত কি সমস্যা আছে?,গরুটির বর্তমান গর্ভবস্থা,গর্ভ পরীক্ষা করিয়েছিলেন?,গর্ভ পরীক্ষার তারিখ,গর্ভের বয়স (মাস),পুর্ববর্তী মোট বাছুরের সংখ্যা,বাছুর প্রসবের তারিখ,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,বাছুরের লিঙ্গ,বাছুরের জন্মকালীন ওজন(কে.জি.),গাভীর কি গর্ভকালীন, বাছুর প্রসব কালীন ও পরবর্তী কি জটিলতা হয়েছিল?,অন্যান্য হলে, লিখুন}') GROUP BY t.rpt_date, t.logger_id,images,audio ORDER BY t.rpt_date desc )"
    data = json.dumps(__db_fetch_values_dict(query), default=decimal_date_default)
    return data


def get_clinical_findings(request):
    logger_id = request.POST.get('logger_id')
    query = "select string_agg(question || ': '|| val || '<br><br>','') as content from get_clinical_findings_web_report('" + str(
        logger_id) + "')"
    content = json.dumps(__db_fetch_single_value(query), default=decimal_date_default)
    # print content
    return HttpResponse(content)


@login_required
def cattle_profile(request, cattle_id, appointment_id):
    # If the case is new ,it set to be view  :: status=4
    if appointment_id != 0:
        app_status = __db_fetch_single_value("select status from appointment where id = " + str(appointment_id))
        if app_status == 0:
            __db_commit_query("update appointment set status = 4  where id = " + str(appointment_id))
    division_q = "select distinct division as name, div_code id from vwunion_code"
    div_list = makeTableList(division_q)
    q = "select *,date(created_date)::text c_date from appointment where id=" + str(appointment_id)
    data = __db_fetch_values_dict(q)
    clinical_findings_data = []
    c_date = ''
    appointment_status = 0
    appointment_type = 0
    for temp in data:
        c_date = temp['c_date']
        appointment_status = temp['status']
        appointment_type = temp['appointment_type']
        if ((appointment_type == 2) and (appointment_status == 1)):
            clinical_findings_id = temp['clinical_diagnosis_id']
            clinical_findings_data = __db_fetch_values_dict(
                "select *, string_to_array(wrong_feeding_last_days,',')::int[] wrong_feeding_last_days_arr, string_to_array(sickness_sign,',')::int[] sickness_sign_arr, string_to_array(behavioral_signs,',')::int[] behavioral_signs_arr, string_to_array(mouth_digestion_sign,',')::int[] mouth_digestion_sign_arr, string_to_array(repiratory_sign,',')::int[] repiratory_sign_arr, string_to_array(reproductive_problem,',')::int[] reproductive_problem_arr, string_to_array(milking_problem,',')::int[] milking_problem_arr, string_to_array(male_reproductive_problem,',')::int[] male_reproductive_problem_arr, string_to_array(skin_problem,',')::int[] skin_problem_arr, string_to_array(foot_problem,',')::int[] foot_problem_arr, string_to_array(megot,',')::int[] megot_arr from clinical_findings where id = " + str(
                    clinical_findings_id))
            # print clinical_findings_data
    cattle_info = get_cattle_info(cattle_id)
    farmer_mobile = cattle_info.get('mobile')
    farmer_info = get_farmer_info(farmer_mobile)
    sick_img = []
    if appointment_id != '0':
        sick_img = get_sickness_images(cattle_id, appointment_id)

    option_dict = {
        'div_list': div_list,
        'appointment_id': appointment_id, 'appointment_status': appointment_status,
        'appointment_type': appointment_type, 'cattle_id': cattle_id, 'c_date': c_date,
        'wrong_feeding_last_days': get_option_list('wrong_feeding_last_days'),
        # 'muzzle': get_option_list('muzzle'),'same_sickness_other_cattle' : get_option_list('same_sickness_other_cattle'),
        'sickness_sign': get_option_list('sickness_sign'),
        'behavioral_signs': get_option_list('behavioral_signs'),
        'mouth_digestion_sign': get_option_list('mouth_digestion_sign'),
        'stool_condition': get_option_list('stool_condition'),
        'repiratory_sign': get_option_list('repiratory_sign'),
        'reproductive_problem': get_option_list('reproductive_problem'),
        'milking_problem': get_option_list('milking_problem'),
        'male_reproductive_problem': get_option_list('male_reproductive_problem'),
        'skin_problem': get_option_list('skin_problem'),
        'foot_problem': get_option_list('foot_problem'),
        'megot': get_option_list('megot'),
        'disease_pattern': get_option_list('disease_pattern'),
        'clinical_findings_data': get_clinical_findings_dict(clinical_findings_data),
        'sickness_images': sick_img
    }

    data = {'data': get_accoridian_dict(cattle_id)}
    context = dict(cattle_info.items() + farmer_info.items() + option_dict.items() + data.items())
    # print context
    return render(request, 'livestock/cattle_profile.html', context)


def get_sickness_images(cattle_id, appointment_id):
    healthrecord_sickness_system_id = __db_fetch_single_value(
        "select healthrecord_sickness_system_id from appointment where id =" + str(appointment_id))
    sickness_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'sickness'"
    sickness_form_owner = __db_fetch_single_value(sickness_form_owner_q)
    q = "(select picture_sinckness_sign1 from vwsickness where system_id::text ='" + str(
        cattle_id) + "'  and picture_sinckness_sign1 is not null and id=" + str(
        healthrecord_sickness_system_id) + " order by id desc)union  (select picture_sinckness_sign2 from vwsickness where system_id::text ='" + str(
        cattle_id) + "' and picture_sinckness_sign2 is not null and id=" + str(
        healthrecord_sickness_system_id) + " order by id desc) ;"
    data = __db_fetch_values_dict(q)
    data_list = []
    for temp in data:
        data_dict = {}
        data_dict['picture_sinckness_sign'] = "/media/" + sickness_form_owner + "/attachments/" + temp[
            'picture_sinckness_sign1']
        data_list.append(data_dict.copy())
        data_dict.clear()
    return data_list


def get_clinical_findings_dict(list_data):
    dict = {}
    for temp in list_data:
        dict = {
            'id': temp['id'],
            'complain_details': temp['complain_details'],
            'treatment_history': temp['treatment_history'],
            'same_sickness_other_cattle': temp['same_sickness_other_cattle'],
            'sick_cattle_affected_or_died': temp['sick_cattle_affected_or_died'],
            'deworming_history': temp['deworming_history'],
            'feeding_history': temp['feeding_history'],
            'wrong_feeding_last_days': temp['wrong_feeding_last_days_arr'],
            'rumination': temp['rumination'],
            'lacrimation': temp['lacrimation'],
            'muzzle': temp['muzzle'],
            'sickness_sign': temp['sickness_sign_arr'],
            'behavioral_signs': temp['behavioral_signs_arr'],
            'mouth_digestion_sign': temp['mouth_digestion_sign_arr'],
            'stool_condition': temp['stool_condition'],
            'repiratory_sign': temp['repiratory_sign_arr'],
            'reproductive_problem': temp['reproductive_problem_arr'],
            'milking_problem': temp['milking_problem_arr'],
            'male_reproductive_problem': temp['male_reproductive_problem_arr'],
            'skin_problem': temp['skin_problem_arr'],
            'foot_problem': temp['foot_problem_arr'],
            'megot': temp['megot_arr'],
            'disease_pattern': temp['disease_pattern'],
            'tentative_diagnosis': temp['tentative_diagnosis']
        }

    return dict


def get_cattle_info(id):
    cattle_regi_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'cattle_registration'"
    cattle_regi_form_owner = __db_fetch_single_value(cattle_regi_form_owner_q)
    img = ""
    # q = "select picture,mobile,cattle_type,coalesce(round(cattle_weight::numeric,2)::text,'') cattleweight,COALESCE (AGE(current_date ,date(cattle_birth_date))::text,cattle_age||' months') cattle_age,coalesce(cattle_name,'') cattle_name,(select label from vwcattle_type where value = cattle_type limit 1) as cattletype,coalesce(calf_birth_weight,'') calf_birth_weight from cattle where cattle_system_id = " + str(id)
    # print q
    q = " with t1 as(select picture from cattle_images where cattle_system_id = " + str(
        id) + " order by created_date desc) ,t2 as(select string_to_array((string_agg(picture,',')),',') cattle_images from t1) select picture,mobile,cattle_type,coalesce(round(cattle_weight::numeric,2)::text,'') cattleweight, COALESCE (AGE(current_date ,date(cattle_birth_date))::text,cattle_age||' months') cattle_age, coalesce(cattle_name,'') cattle_name,(select label from vwcattle_type where value = cattle_type limit 1) as cattletype,coalesce(calf_birth_weight,'') calf_birth_weight ,(select cattle_images from t2) cattle_images from cattle where cattle_system_id = " + str(
        id)
    dataset = __db_fetch_values_dict(q)
    cattle_dict = {}
    cattle_img_list = []
    for temp in dataset:
        if temp['picture'] is not None:
            img = temp['picture']
        img = "/media/" + cattle_regi_form_owner + "/attachments/" + img
        if temp['cattle_images'] is not None:
            for tmp in temp['cattle_images']:
                image = "/media/" + cattle_regi_form_owner + "/attachments/" + tmp
                cattle_img_list.append(image)
        cattle_dict = {'cattle_type': temp['cattle_type'], 'cattle_img': img, 'mobile': temp['mobile'],
                       'cattle_name': temp['cattle_name'], 'cattle_weight': temp['cattleweight'],
                       'cattle_age': temp['cattle_age'], 'cattle_type_text': temp['cattletype'],
                       'calf_birth_weight': temp['calf_birth_weight'], 'cattle_img_list': cattle_img_list}
    return cattle_dict


def get_farmer_info(mobile):
    farmerprofileupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    farmerprofileupdate_form_owner = __db_fetch_single_value(farmerprofileupdate_form_owner_q)
    q = "select id, coalesce(farmer_name,'') farmer_name,mobile,date(submission_time)::text registration_date,image,division,district,upazila from farmer where mobile = '" + mobile + "'"
    dataset = __db_fetch_values_dict(q)
    farmer_dict = {}
    img_path = ''
    stat = 1
    for temp in dataset:
        if temp['image'] is not None:
            img = temp['image']

            img_path = "/media/" + farmerprofileupdate_form_owner + "/attachments/" + img
        if temp['division'] == None:
            stat = 0

        farmer_dict = {'id': temp['id'], 'farmer_name': temp['farmer_name'], 'mobile': temp['mobile'],
                       'registration_date': temp['registration_date'], 'image_url': img_path,
                       'div_id': temp['division'], 'dist_id': temp['district'], 'upz_id': temp['upazila'], 'stat': stat}

    return farmer_dict


def get_option_list(fieldname):
    q = "select value_text as val,value_label as label from xform_extracted where xform_id = 604 and field_name = '" + fieldname + "'"
    dataset = makeTableList(q)
    return dataset


def add_location(request, farmer_id):
    if request.method == 'GET':
        division = request.GET.get('division')
        district = request.GET.get('district')
        upazila = request.GET.get('upazila')
        q = "update farmer set division = '" + division + "',district = '" + district + "',upazila = '" + upazila + "' where id = " + str(
            farmer_id)
        __db_commit_query(q)
        print
        q
    return HttpResponse(json.dumps("Location added"), content_type="application/json", status=200)


def clinical_findings(request, appointment_id):
    q = ""
    if request.method == 'POST':
        edit_id = request.POST.get('clinical_findings_id')
        complain_details = request.POST.get('complain_details')
        treatment_history = request.POST.get('treatment_history')
        # same_sickness_other_cattle = request.POST.get('same_sickness_other_cattle')
        # sick_cattle_affected_or_died = request.POST.get('sick_cattle_affected_or_died')
        deworming_history = request.POST.get('deworming_history')
        feeding_history = request.POST.get('feeding_history')
        wrong_feeding_last_days = get_multiple_input_string(request.POST.getlist('wrong_feeding_last_days[]'))
        rumination = request.POST.get('rumination')
        # lacrimation = request.POST.get('lacrimation')
        # muzzle = request.POST.get('muzzle')
        sickness_sign = get_multiple_input_string(request.POST.getlist('sickness_sign[]'))
        behavioral_signs = get_multiple_input_string(request.POST.getlist('behavioral_signs[]'))
        mouth_digestion_sign = get_multiple_input_string(request.POST.getlist('mouth_digestion_sign[]'))
        stool_condition = request.POST.get('stool_condition')
        repiratory_sign = get_multiple_input_string(request.POST.getlist('repiratory_sign[]'))
        reproductive_problem = get_multiple_input_string(request.POST.getlist('reproductive_problem[]'))
        milking_problem = get_multiple_input_string(request.POST.getlist('milking_problem[]'))
        male_reproductive_problem = get_multiple_input_string(request.POST.getlist('male_reproductive_problem[]'))
        skin_problem = get_multiple_input_string(request.POST.getlist('skin_problem[]'))
        foot_problem = get_multiple_input_string(request.POST.getlist('foot_problem[]'))
        megot = get_multiple_input_string(request.POST.getlist('megot[]'))
        disease_pattern = request.POST.get('disease_pattern')
        tentative_diagnosis = request.POST.get('tentative_diagnosis')
        if edit_id:
            q = "update public.clinical_findings set complain_details = '" + complain_details + "', treatment_history='" + treatment_history + "', deworming_history='" + deworming_history + "', feeding_history='" + feeding_history + "', wrong_feeding_last_days='" + wrong_feeding_last_days + "', rumination='" + rumination + "',  sickness_sign='" + sickness_sign + "', behavioral_signs='" + behavioral_signs + "', mouth_digestion_sign='" + mouth_digestion_sign + "', stool_condition='" + stool_condition + "', repiratory_sign='" + repiratory_sign + "', reproductive_problem='" + reproductive_problem + "', milking_problem='" + milking_problem + "', male_reproductive_problem='" + male_reproductive_problem + "', skin_problem='" + skin_problem + "', foot_problem='" + foot_problem + "', megot='" + megot + "', disease_pattern='" + disease_pattern + "', tentative_diagnosis='" + tentative_diagnosis + "',updated_by=" + str(
                request.user.id) + ",updated_date=NOW()"
            __db_commit_query(q)
        else:
            q = "INSERT INTO public.clinical_findings(id, appointment_id, complain_details,  treatment_history, deworming_history, feeding_history, wrong_feeding_last_days, rumination,  sickness_sign, behavioral_signs, mouth_digestion_sign, stool_condition, repiratory_sign, reproductive_problem, milking_problem, male_reproductive_problem, skin_problem, foot_problem, megot, disease_pattern, tentative_diagnosis, created_by, created_date)VALUES (DEFAULT , " + str(
                appointment_id) + ",'" + complain_details + "', '" + treatment_history + "', '" + deworming_history + "', '" + feeding_history + "', '" + wrong_feeding_last_days + "', '" + rumination + "', '" + sickness_sign + "', '" + behavioral_signs + "', '" + mouth_digestion_sign + "', '" + stool_condition + "','" + repiratory_sign + "','" + reproductive_problem + "', '" + milking_problem + "', '" + male_reproductive_problem + "', '" + skin_problem + "', '" + foot_problem + "', '" + megot + "','" + disease_pattern + "', '" + tentative_diagnosis + "', " + str(
                request.user.id) + ", NOW()) RETURNING id"
            clinical_dignosis_id = __db_fetch_single_value(q)
            update_q = "update appointment set status =1,clinical_diagnosis_id = " + str(
                clinical_dignosis_id) + " where id =" + str(appointment_id)
            __db_commit_query(update_q)
    # print q
    return HttpResponse(json.dumps("Clinical findings added"), content_type="application/json", status=200)


def get_multiple_input_string(data_list):
    input_str = ""
    #  check the list is empty
    if list(data_list):
        # list converts to comma seperated string
        input_str = ' , '.join(str(x) for x in list(data_list))
    return input_str


def get_diagnosis_name(request):
    diagnosis_name = request.POST.get("diagnosis_name");
    q = "select distinct diagnosis_name from diagnosis where diagnosis_name  ~* '" + diagnosis_name + "'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)


def advisory_list(request):
    return render(request, 'livestock/advisory_list.html')


def get_advisory_table(request):
    q = "select * from appointment"
    dataset = __db_fetch_values_dict(q)
    return render(request, 'livestock/advisory_table.html', {'dataset': dataset})


'''
def submit_prescription(request,appointment_id):
    if request.method == 'POST':
        if(request.POST.get('clinical_findings_id_prescription')):
            clinical_findings_id = request.POST.get('clinical_findings_id_prescription')
        else:
            clinical_findings_id =0
        med_part_1 = request.POST.getlist('med_part_1[]')
        med_part_2 = request.POST.getlist('med_part_2[]')
        revisit = request.POST.get('revisit')
        advice = request.POST.get('advice')

        pres_q = "INSERT INTO public.prescription(id, appointment_id, clinical_findings_id, advice, created_by, created_date, next_appointment_after)VALUES (DEFAULT , "+str(appointment_id)+","+str(clinical_findings_id)+", '"+advice+"',"+str(request.user.id)+", NOW(), "+str(revisit)+") returning id;"
        prescription_id = __db_fetch_single_value(pres_q)
        for index, elem in enumerate(med_part_1):
            pres_detail_q = "INSERT INTO public.prescription_details(id, prescription_id, medicine_part_1, medicine_part_2)VALUES (DEFAULT, " + str(
                prescription_id) + ", '"+med_part_1[index]+"','"+med_part_2[index]+"');"
            __db_commit_query(pres_detail_q)
        __db_commit_query("update appointment set status = 2,prescription_id="+str(prescription_id)+" where id = "+str(appointment_id)+"")
        pres_html = get_prescription(prescription_id)
        q = "select cattle_system_id,(select mobile from cattle where cattle_system_id = appointment.cattle_system_id) as mobile from appointment where id = "+str(appointment_id)+" "
        d = __db_fetch_values_dict(q)
        for temp in d:
            cattle_id = temp['cattle_system_id']
            farmer_id = temp['mobile']
        get_paravet_mobile = __db_fetch_single_value("select(json->>'_submitted_by') user_mobile from logger_instance where id =(select healthrecord_sickness_system_id from appointment where id = "+str(appointment_id)+")")
        if get_paravet_mobile == farmer_id:
            print "Sending Push notification to " + farmer_id + " ****__________________________________________________________________________________________"

            send_push_message(farmer_id, 1, 'Prescription', 'There is a prescription.', cattle_id, farmer_id,
                              prescription_id)
            print "End push noti ****__________________________________________________________________________________________end"
        else:
            print "Sending Push notification to "+ farmer_id+" ****__________________________________________________________________________________________"
            send_push_message(farmer_id, 1, 'Prescription', 'There is a prescription.', cattle_id, farmer_id,
                              prescription_id)
            print "End push noti ****__________________________________________________________________________________________end"

            print "Sending Push notification to " + get_paravet_mobile + " ****__________________________________________________________________________________________"

            send_push_message(get_paravet_mobile, 1, 'Prescription', 'There is a prescription.', cattle_id, farmer_id,
                              prescription_id)
            print "End push noti ****__________________________________________________________________________________________end"

        #SENDING Prescription SMS to farmer  AND/OR Paravet/AI Technician ###

        sms_text = request.POST.get("sms_text")
        send_other = request.POST.get("send_other")
        f_id = request.POST.get("f_id")
        print "farmer mobile is:::" + str(f_id)
        if send_other == '1':
            mobile_num_list = __db_fetch_single_value(
                "with t1 as(select user_id,(select username from auth_user where id =(select user_id from usermodule_usermoduleprofile where id =user_farmer_map.user_id)) para_ai_mobile from user_farmer_map where farmer_id=(select id from farmer where mobile = '" + f_id + "')) select string_to_array((string_agg(para_ai_mobile,',')),',') mobile_list from t1 ")
            if mobile_num_list:
                for temp in mobile_num_list:
                    send_sms(temp, sms_text)
        else:
            send_sms(f_id, sms_text)
        data={
            'farmerid' : f_id,'pres_html' : ''
        }
    return HttpResponse(json.dumps(data), content_type="application/json", status=200)
'''


def submit_prescription(request, appointment_id):
    if request.method == 'POST':
        if (request.POST.get('clinical_findings_id_prescription')):
            clinical_findings_id = request.POST.get('clinical_findings_id_prescription')
        else:
            clinical_findings_id = 0
        med_part_1 = request.POST.getlist('med_part_1[]')
        med_part_2 = request.POST.getlist('med_part_2[]')
        revisit = request.POST.get('revisit')
        advice = request.POST.get('advice')

        # check the duplicate prescription of corresponding appointment
        no_prescription_q = "select count(*) from prescription where appointment_id  = " + str(appointment_id)
        no_prescription = __db_fetch_single_value(no_prescription_q)
        if no_prescription > 0:
            return HttpResponse(json.dumps('Duplicate Prescription.'), content_type="application/json", status=500)

        pres_q = "INSERT INTO public.prescription(id, appointment_id, clinical_findings_id, advice, created_by, created_date, next_appointment_after)VALUES (DEFAULT , " + str(
            appointment_id) + "," + str(clinical_findings_id) + ", '" + advice + "'," + str(
            request.user.id) + ", NOW()::timestamp, " + str(revisit) + ") returning id;"
        prescription_id = __db_fetch_single_value(pres_q)
        for index, elem in enumerate(med_part_1):
            pres_detail_q = "INSERT INTO public.prescription_details(id, prescription_id, medicine_part_1, medicine_part_2)VALUES (DEFAULT, " + str(
                prescription_id) + ", '" + med_part_1[index] + "','" + med_part_2[index] + "');"
            __db_commit_query(pres_detail_q)
        __db_commit_query(
            "update appointment set status = 2,prescription_id=" + str(prescription_id) + " where id = " + str(
                appointment_id) + "")
        pres_html = get_prescription(prescription_id)
        q = "select cattle_system_id,(select mobile from cattle where cattle_system_id = appointment.cattle_system_id) as mobile from appointment where id = " + str(
            appointment_id) + " "
        d = __db_fetch_values_dict(q)
        for temp in d:
            cattle_id = temp['cattle_system_id']
            farmer_id = temp['mobile']
        get_paravet_mobile = __db_fetch_single_value(
            "select(json->>'_submitted_by') user_mobile from logger_instance where id =(select healthrecord_sickness_system_id from appointment where id = " + str(
                appointment_id) + ")")
        if get_paravet_mobile == farmer_id:
            print
            "Sending Push notification to " + farmer_id + " ****__________________________________________________________________________________________"

            send_push_message(farmer_id, 1, 'Prescription', 'There is a prescription.', cattle_id, farmer_id,
                              prescription_id)
            print
            "End push noti ****__________________________________________________________________________________________end"
        else:
            print
            "Sending Push notification to " + farmer_id + " ****__________________________________________________________________________________________"
            send_push_message(farmer_id, 1, 'Prescription', 'There is a prescription.', cattle_id, farmer_id,
                              prescription_id)
            print
            "End push noti ****__________________________________________________________________________________________end"

            print
            "Sending Push notification to " + get_paravet_mobile + " ****__________________________________________________________________________________________"

            send_push_message(get_paravet_mobile, 1, 'Prescription', 'There is a prescription.', cattle_id, farmer_id,
                              prescription_id)
            print
            "End push noti ****__________________________________________________________________________________________end"

        # SENDING Prescription SMS to farmer  AND/OR Paravet/AI Technician ###

        sms_text = request.POST.get("sms_text")
        send_other = request.POST.get("send_other")
        f_id = request.POST.get("f_id")
        print
        "farmer mobile is:::" + str(f_id)
        if send_other == '1':
            mobile_num_list = __db_fetch_single_value(
                "with t1 as(select user_id,(select username from auth_user where id =(select user_id from usermodule_usermoduleprofile where id =user_farmer_map.user_id)) para_ai_mobile from user_farmer_map where farmer_id=(select id from farmer where mobile = '" + f_id + "')) select string_to_array((string_agg(para_ai_mobile,',')),',') mobile_list from t1 ")
            if mobile_num_list:
                for temp in mobile_num_list:
                    send_sms(temp, sms_text)
        else:
            send_sms(f_id, sms_text)
        data = {
            'farmerid': f_id, 'pres_html': ''
        }
    return HttpResponse(json.dumps(data), content_type="application/json", status=200)


def get_prescription(prescription_id):
    st = datetime.fromtimestamp(time.time()).strftime('%Y_%m_%d_%H_%M_%S')
    prescription_data = __db_fetch_values_dict(
        "with t as(select(select value_label from xform_extracted where xform_id = 597 and field_name = 'cattle_type' and value_text = c.cattle_type) as cattle_type,cattle_system_id,(select farmer_name from farmer where mobile = c.mobile) as farmer_name,cattle_birth_date,cattle_age,created_date as create_date,mobile, case when cattle_age is NOT NULL then(with t1 as (select age(Current_date, Date(created_date)) as c_age) SELECT (EXTRACT(year FROM c_age)* 12 + EXTRACT(MONTH FROM c_age)) + cattle_age::Integer as age_month from t1) else 0 END as age_in_month, case when cattle_birth_date is not null then EXTRACT(year from age(now()::date,cattle_birth_date::date))::text else cattle_age end as age_year, case when cattle_birth_date is not null then EXTRACT(month from age(now()::date,cattle_birth_date::date))::text else 0::text end as age_month, case when cattle_birth_date is not null then EXTRACT(day from age(now()::date,cattle_birth_date::date))::text else 0::text end as age_day from cattle c), n as(with m as(select p.id as prescription_id,a.cattle_system_id,p.advice,p.next_appointment_after,pd.medicine_part_1,pd.medicine_part_2,p.created_by,p.created_date from prescription p left join prescription_details pd on pd.prescription_id = p.id left join appointment a on a.id = p.appointment_id) select m.created_date,m.prescription_id,m.created_by,m.cattle_system_id,m.advice,m.next_appointment_after,string_agg(medicine_part_1 || '@@' ||medicine_part_2, '|| ') as rx from m group by m.advice,m.next_appointment_after,m.cattle_system_id,m.created_by,m.prescription_id,m.created_date) select t.cattle_type,t.cattle_system_id,t.farmer_name,t.mobile,t.age_year,t.age_month,t.age_day,t.cattle_birth_date,t.age_in_month,t.cattle_age,t.create_date,to_char(n.created_date,'DD/MM/YYYY') as created_date,n.prescription_id,n.created_by,n.cattle_system_id,n.advice,n.next_appointment_after,n.rx, (select first_name || last_name from auth_user where id = created_by) as prescribey_by, (select signature_img from users_additional_info where user_id = 288) as signature_img from t,n where t.cattle_system_id = n.cattle_system_id and n.prescription_id = " + str(
            prescription_id))

    farmer_name = prescription_data[0]['farmer_name']
    created_date = prescription_data[0]['created_date']
    cattle_type = prescription_data[0]['cattle_type']
    age_year = 0
    age_month = 0
    age_day = 0
    if prescription_data[0]['cattle_birth_date'] is not None:
        age_year = prescription_data[0]['age_year']
        age_month = prescription_data[0]['age_month']
        age_day = prescription_data[0]['age_day']
    else:
        if prescription_data[0]['cattle_age'] is not None:
            age_in_month = prescription_data[0]['age_in_month']
            age_year = int(age_in_month / 12)
            age_month = int(age_in_month % 12)
            age_day = 0

    advice = prescription_data[0]['advice']
    next_appointment_after = prescription_data[0]['next_appointment_after']
    prescribey_by = prescription_data[0]['prescribey_by']
    signature_img = prescription_data[0]['signature_img'].split('/')[-1]
    medicine_str = ''
    medicines = prescription_data[0]['rx'].split('|| ')

    c = 1
    for m in medicines:
        m = m.split('@@')
        mstr = str(c) + '. ' + m[0] + ' ' + m[1] + '\n'
        c = c + 1
        medicine_str = medicine_str + mstr
    '''
    prescription_html = ' <h3>Prescription:</h3>\n <p>খামারী : ' + str(farmer_name.encode('utf-8')) + ', তারিখ: ' + str(
        created_date.encode('utf-8')) + '</p>\n<p>গরু: ' + str(cattle_type.encode('utf-8')) + ', ' + str(
        age_year.encode('utf-8')) + ' বছর ' + str(age_month.encode('utf-8')) + ' মাস ' + str(
        age_day.encode('utf-8')) + ' দিন</p>\n<h3>Rx:</h3> ' + str(
        medicine_str.encode('utf-8')) + ' \n<h3>Advice:</h3> <p>' + str(advice.encode('utf-8')) + '</p>\n<h4>' + str(
        next_appointment_after) + ' দিন পর পুনরায় তথ্য পাঠিয়ে ডাক্তারের সাথে যোগাযোগ করুন</h4> <img src="' + str(
        signature_img) + '" width="200" height="74"> <br>' + str(
        prescribey_by.encode('utf-8')) + ' \n জরুরী প্রয়জনে ০১২৪৫৮৭৯৬৫২ নাম্বারে যোগাযোগ করুন '
    '''
    prescription_html = str(created_date.encode('utf-8')) + '\n' + str(farmer_name.encode('utf-8')) + '\n' + str(
        cattle_type.encode('utf-8')) + '\n' + str(
        age_year) + ' বছর ' + str(age_month) + ' মাস ' + str(
        age_day) + ' দিন \n' + str(
        medicine_str.encode('utf-8')) + '\n' + str(advice.encode('utf-8'))
    return prescription_html


def get_medicine_name(request):
    m_name = "%" + request.POST.get("m_name") + "%"
    m_type = "%" + request.POST.get("m_type") + "%"
    packsize = "%" + request.POST.get("packsize") + "%"
    q = "select medicine_name from vwmedicine where medicine_name like '" + m_name + "' and m_type like '" + m_type + "' and packsize like '" + packsize + "'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)


def get_medicine_type(request):
    m_name = "%" + request.POST.get("m_name") + "%"
    m_type = "%" + request.POST.get("m_type") + "%"
    packsize = "%" + request.POST.get("packsize") + "%"
    q = "select DISTINCT m_type from vwmedicine where medicine_name like '" + m_name + "' and m_type like '" + m_type + "' and packsize like '" + packsize + "'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)


def get_medicine_packsize(request):
    m_name = "%" + request.POST.get("m_name") + "%"
    m_type = "%" + request.POST.get("m_type") + "%"
    packsize = "%" + request.POST.get("packsize") + "%"
    q = "select DISTINCT packsize from vwmedicine where medicine_name like '" + m_name + "' and m_type like '" + m_type + "' and packsize like '" + packsize + "'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)


def get_suggested_prescription(request):
    cattle_type = request.POST.get("cattle_type")
    weight = request.POST.get("weight")
    diagnosis = request.POST.get("diagnosis")
    q = "select * from diagnosis where cattle_type = " + str(
        cattle_type) + " and diagnosis_name = '" + diagnosis + "' and weight_from <= " + str(
        weight) + " and weight_to >= " + str(weight)
    dataset = __db_fetch_values_dict(q)
    med_data = []
    advice = ''
    data = ''
    if dataset:
        for temp in dataset:
            diagnosis_id = temp['id']
            diagnosis_medi_q = "select ( name || ' ' || medicine_name || ' ' ||packsize || ' x ' || quantity ) as mpart_1,( dose || ' ' || route || ' ' ||days  ) as mpart_2 from  vwdiagnosis_medicine where diagnosis_id=" + str(
                diagnosis_id)
            medicine_data = __db_fetch_values_dict(diagnosis_medi_q)
            for tmp in medicine_data:
                data_dict = {}
                data_dict['mpart_1'] = tmp['mpart_1']
                data_dict['mpart_2'] = tmp['mpart_2']
                med_data.append(data_dict.copy())
                data_dict.clear()
            advice = __db_fetch_single_value(
                "select advice from diagnosis_advice where diagnosis_id =" + str(diagnosis_id) + " limit 1")
        data = {
            'm_data': med_data, 'a_data': advice
        }

    return HttpResponse(json.dumps(data, default=decimal_date_default), content_type="application/json",
                        status=200)


def get_prescription_data(id):
    q = "with t as(select cattle_system_id,(select farmer_name from farmer where mobile = c.mobile) as farmer_name,cattle_birth_date,cattle_age,created_date as create_date,mobile, case when cattle_age is NOT NULL then(with t1 as (select age(Current_date, Date(created_date)) as c_age) SELECT (EXTRACT(year FROM c_age)* 12 + EXTRACT(MONTH FROM c_age)) + cattle_age::Integer as age_month from t1) else 0 END as age_in_month, case when cattle_birth_date is not null then EXTRACT(year from age(now()::date,cattle_birth_date::date))::text else cattle_age end as age_year, case when cattle_birth_date is not null then EXTRACT(month from age(now()::date,cattle_birth_date::date))::text else 0::text end as age_month, case when cattle_birth_date is not null then EXTRACT(day from age(now()::date,cattle_birth_date::date))::text else 0::text end as age_day from cattle c), n as(with m as(select p.id as prescription_id,a.cattle_system_id,p.advice,p.next_appointment_after,pd.medicine_part_1,pd.medicine_part_2,p.created_by,p.created_date from prescription p left join prescription_details pd on pd.prescription_id = p.id left join appointment a on a.id = p.appointment_id) select m.created_date,m.prescription_id,m.created_by,m.cattle_system_id,m.advice,m.next_appointment_after,string_agg(medicine_part_1 || '@@' ||medicine_part_2, '|| ') AS rx from m group by m.advice,m.next_appointment_after,m.cattle_system_id,m.created_by,m.prescription_id,m.created_date) select t.cattle_system_id,(select label from vwcattle_type where value =(select cattle_type from cattle where cattle_system_id =  t.cattle_system_id)) as cattle_type,t.farmer_name,t.mobile,t.age_year,t.age_month,t.age_day,t.cattle_birth_date,t.age_in_month,t.cattle_age,t.create_date,n.created_date::date,n.prescription_id,n.created_by,n.cattle_system_id,n.advice,n.next_appointment_after,n.rx,(select first_name || last_name from auth_user where id = created_by) as prescribey_by, (select substring(signature_img from 8) from users_additional_info where user_id = (select created_by from prescription where id =" + str(
        id) + ")) as signature_img from t,n where t.cattle_system_id = n.cattle_system_id and n.prescription_id = " + str(
        id) + ""
    # q = "with t as(select cattle_system_id,(select farmer_name from farmer where mobile = c.mobile) as farmer_name,mobile, case when cattle_birth_date is not null then EXTRACT(year from age(now()::date,cattle_birth_date::date))::text else cattle_age end as age_year, case when cattle_birth_date is not null then EXTRACT(month from age(now()::date,cattle_birth_date::date))::text else 0::text end as age_month, case when cattle_birth_date is not null then EXTRACT(day from age(now()::date,cattle_birth_date::date))::text else 0::text end as age_day from cattle c), n as(with m as(select p.id as prescription_id,a.cattle_system_id,p.advice,p.next_appointment_after,pd.medicine_part_1,pd.medicine_part_2,p.created_by,p.created_date from prescription p left join prescription_details pd on pd.prescription_id = p.id left join appointment a on a.id = p.appointment_id) select m.created_date,m.prescription_id,m.created_by,m.cattle_system_id,m.advice,m.next_appointment_after,string_agg(medicine_part_1 || '\n' ||medicine_part_2, ';') as rx from m group by m.advice,m.next_appointment_after,m.cattle_system_id,m.created_by,m.prescription_id,m.created_date) select t.cattle_system_id,(select label from vwcattle_type where value =(select cattle_type from cattle where cattle_system_id =  t.cattle_system_id)) as cattle_type,t.farmer_name,t.mobile,t.age_year,t.age_month,t.age_day,n.created_date,n.prescription_id,n.created_by,n.cattle_system_id,n.advice,n.next_appointment_after,n.rx,(select first_name || last_name from auth_user where id = created_by) as prescribey_by, (select signature_img from users_additional_info where user_id = (select created_by from prescription where id ="+str(id)+")) as signature_img from t,n where t.cattle_system_id = n.cattle_system_id and n.prescription_id = "+str(id)+""
    data = __db_fetch_values_dict(q)
    dict = {}
    for temp in data:
        age_year = 0
        age_month = 0
        age_day = 0
        if temp['cattle_birth_date'] is not None:
            print("prescription_data[0]['cattle_birth_date']_________________________" + temp['cattle_birth_date'])
            age_year = temp['age_year']
            age_month = temp['age_month']
            age_day = temp['age_day']
        else:
            if temp['cattle_age'] is not None:
                print
                str(temp['age_in_month'])
                age_in_month = temp['age_in_month']
                age_year = int(age_in_month / 12)
                age_month = int(age_in_month % 12)
                age_day = 0
        medicines = temp['rx'].split('||')
        c = 1
        mstr = ''
        medicine_str = ''
        for m in medicines:
            m = m.split('@@')
            mstr = str(c) + '. ' + m[0] + ': ' + m[1] + '<br>'
            c = c + 1
            medicine_str = medicine_str + mstr
        dict = {
            'farmer_name': temp['farmer_name'], 'mp_1': medicine_str, 'signature_img': temp['signature_img'],
            'created_date': temp['created_date'], 'advice': temp['advice'], 'cattle_type': temp['cattle_type'],
            'age_year': age_year, 'age_month': age_month, 'age_day': age_day,
            'next_appointment_after': temp['next_appointment_after'], 'prescribey_by': temp['prescribey_by'],
        }
    return dict


def get_old_prescription(request, logger_id):
    # q = "with t1 as(select prescription_id,(select created_date from prescription where id =prescription_id) c_date from appointment where prescription_id is not null and cattle_system_id =" + str(
    #     cattle_id) + ") select prescription_id from t1 order by c_date desc"
    # q="select prescription_id from appointment   where prescription_id is not null and cattle_system_id ="+str(cattle_id)+" order by id desc"
    q = "WITH t1 AS(SELECT prescription_id, (SELECT created_date FROM prescription WHERE id = prescription_id) c_date FROM appointment WHERE prescription_id IS NOT NULL AND healthrecord_sickness_system_id = " + str(
        logger_id) + ") SELECT prescription_id FROM t1 ORDER BY c_date DESC "
    data = __db_fetch_values_dict(q)
    data_list = []
    for temp in data:
        dict = {
            'prescription': get_prescription_data(temp['prescription_id'])
        }
        data_list.append(dict.copy())
        dict.clear()
    # print "ata_list___________________________________________________________________---------"
    # print data_list
    return render(request, 'livestock/old_prescription.html', {'prescription_data_list': data_list}, status=200)


'''
    Content Upload
'''


@login_required
def content_upload(request):
    if request.method == 'POST':
        content_role = request.POST.getlist("content_role")
        content_type = request.POST.get("content_type")
        file_type = request.POST.get("file_type")
        if content_type == '1':
            content_type_text = 'user_instruction'
        if content_type == '2':
            content_type_text = 'training_manual'
        des = upload_shared_file(request.FILES['shared_file'], content_type_text)
        insert_q = "INSERT INTO public.content(id, content_type, file_type, file_name, submitted_by, submission_time)VALUES (DEFAULT , '" + str(
            content_type) + "', '" + str(file_type) + "', '" + des + "', " + str(
            request.user.id) + ",NOW()) RETURNING id;"
        content_id = __db_fetch_single_value(insert_q)
        if content_role:
            for temp in content_role:
                role_id = temp
                q = "INSERT INTO public.role_content_map(id, content_id, role_id)VALUES (DEFAULT ," + str(
                    content_id) + ", " + str(role_id) + ");"
                __db_commit_query(q)
        return HttpResponse(simplejson.dumps("ok"), content_type="application/json")
    return render(request, "livestock/content_upload.html")


def upload_shared_file(file, title):
    if file:
        # get file extention from file name
        file_extention = os.path.splitext(file.name)[1]
        millis = int(round(time.time() * 1000))
        # filePath = title+'_'+str(millis)+file_extention
        filePath = file.name
        destination = open('onadata/media/content/' + filePath, 'w+')
        for chunk in file.chunks():
            destination.write(chunk)
        destination.close()

    return filePath


@login_required
def content_list(request):
    return render(request, "livestock/content_list.html")


def get_content_table(request):
    q = "with t1 as(select content_id,(select role from usermodule_organizationrole where id = role_id)as role from role_content_map), t2 as(select content_id,string_agg(role,',') role_name from t1 group by content_id) select id,file_name,(case when content_type='1' then 'User Instruction' when content_type='2' then 'Training Manual' else '' end) as content_type_name,(select role_name from t2 where content_id = content.id) as role from content order by id desc "
    data = __db_fetch_values_dict(q)
    return render(request, "livestock/content_table.html", {'dataset': data})


@login_required
def delete_content(request, id):
    content_del_q = "delete from public.content where id = " + str(id)
    map_del_q = "delete from public.role_content_map where content_id = " + str(id)
    __db_commit_query(map_del_q)
    __db_commit_query(content_del_q)
    return HttpResponse(simplejson.dumps('ok'), content_type="application/json")


#######################################################################
#######################################################################
#######################################################################
import pandas


def advisory_list(request):
    query = "select count(*) num from appointment where status = ANY('{0,4}') and appointment_type =1"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    num = df.num.tolist()[0]
    query = "with t as( select (select user_id from usermodule_usermoduleprofile where id = p.user_id)user_id from usermodule_userrolemap p where role_id = any('{50}')) select (select username from auth_user where id = user_id)ai_paravet_id,(select first_name || ' '|| last_name from auth_user where id = user_id)ai_paravet_name from t"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    ai_paravet_id = df.ai_paravet_id.tolist()
    ai_paravet_name = df.ai_paravet_name.tolist()
    ai_paravets = zip(ai_paravet_id, ai_paravet_name)
    query = "WITH t AS( SELECT id, to_char(created_date, 'MM-DD-YYYY HH24:MI:SS') created_date, ( SELECT created_date FROM prescription WHERE appointment_id = appointment.id limit 1) prescription_date, cattle_system_id, ( select cattle_type from cattle where cattle_system_id = appointment.cattle_system_id limit 1), ( SELECT (json->>'mobile') mobile FROM logger_instance WHERE id = healthrecord_sickness_system_id limit 1), ( SELECT (json->>'_submitted_by') submitted_by FROM logger_instance WHERE id = healthrecord_sickness_system_id limit 1), status FROM appointment WHERE appointment_type = any('{1,3}') ORDER BY id DESC) SELECT id, created_date, cattle_system_id, ( SELECT first_name || ' ' || last_name FROM auth_user WHERE username = t.mobile limit 1) farmer_name, mobile, ( SELECT label FROM vwcattle_type WHERE value = t.cattle_type limit 1) cattle_type, ( SELECT CASE WHEN cattle_birth_date IS NULL THEN cattle_age ELSE age(CURRENT_DATE ,date(cattle_birth_date))::text END cattle_age FROM cattle WHERE cattle_system_id = t.cattle_system_id limit 1), COALESCE(substring(prescription_date::text FROM 0 FOR 20),'') prescription_date, ( SELECT first_name || ' ' || last_name FROM auth_user WHERE username = t.submitted_by limit 1)ai_paravet_name, submitted_by, status FROM t WHERE status = ANY('{0,2,4}')"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    advisory_list = json.dumps(__db_fetch_values_dict(query), default=decimal_date_default)
    return render(request, 'livestock/advisory_list.html',
                  {'advisory_list': advisory_list, 'ai_paravets': ai_paravets, 'num': num})


def getAdvisoryData(request):
    from_date = request.POST.get('from_date')
    to_date = request.POST.get('to_date')
    ai_paravet = request.POST.get('ai_paravet')
    status = request.POST.get('status')
    filter_query = ""
    if from_date != "" and to_date != "":
        filter_query += "and created_date::date between '" + str(from_date) + "' and '" + str(to_date) + "' "
    if status != "":
        filter_query += "and status = " + str(status) + " "
    if ai_paravet != "":
        filter_query += "and submitted_by = '" + str(ai_paravet) + "' and submitted_by != mobile"
    query = "WITH t AS( SELECT id,to_char(created_date, 'MM-DD-YYYY HH24:MI:SS') created_date, ( SELECT created_date FROM prescription WHERE appointment_id = appointment.id limit 1) prescription_date, cattle_system_id, ( select cattle_type from cattle where cattle_system_id = appointment.cattle_system_id limit 1), ( SELECT (json->>'mobile') mobile FROM logger_instance WHERE id = healthrecord_sickness_system_id limit 1), ( SELECT (json->>'_submitted_by') submitted_by FROM logger_instance WHERE id = healthrecord_sickness_system_id limit 1), status FROM appointment WHERE appointment_type = any('{1,3}')  order by id desc) SELECT id, created_date,cattle_system_id, ( SELECT first_name || ' ' || last_name FROM auth_user WHERE username = t.mobile limit 1) farmer_name, mobile, ( SELECT label FROM vwcattle_type WHERE value = t.cattle_type limit 1) cattle_type, ( SELECT CASE WHEN cattle_birth_date IS NULL THEN cattle_age ELSE age(CURRENT_DATE ,date(cattle_birth_date))::text END cattle_age FROM cattle WHERE cattle_system_id = t.cattle_system_id limit 1), COALESCE(substring(prescription_date::text FROM 0 FOR 20),'') prescription_date, ( SELECT first_name || ' ' || last_name FROM auth_user WHERE username = t.submitted_by limit 1)ai_paravet_name, submitted_by, status FROM t WHERE status = ANY('{0,2,4}') " + str(
        filter_query)
    data = json.dumps(__db_fetch_values_dict(query), default=decimal_date_default)
    return HttpResponse(data)


def sickness_list(request):
    query = "select count(*) num from appointment where status = ANY('{0,1,4}') and appointment_type =2 "
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    num = df.num.tolist()[0]
    query = "with t as( select (select user_id from usermodule_usermoduleprofile where id = p.user_id)user_id from usermodule_userrolemap p where role_id = any('{50}')) select distinct (select username from auth_user where id = user_id)ai_paravet_id,(select first_name || ' '|| last_name from auth_user where id = user_id)ai_paravet_name from t"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    ai_paravet_id = df.ai_paravet_id.tolist()
    ai_paravet_name = df.ai_paravet_name.tolist()
    ai_paravets = zip(ai_paravet_id, ai_paravet_name)
    query = "with t as( select id,to_char(created_date, 'YYYY-MM-DD HH24:MI:SS') created_date,( select created_date from prescription where appointment_id = appointment.id limit 1) prescription_date, cattle_system_id, ( select cattle_type from cattle where cattle_system_id = appointment.cattle_system_id limit 1), ( select ( json ->>'mobile' ) mobile from logger_instance where id = healthrecord_sickness_system_id limit 1), ( select ( json ->>'_submitted_by' ) submitted_by from logger_instance where id = healthrecord_sickness_system_id limit 1), status from appointment where appointment_type = 2 order by id desc) select id, created_date,cattle_system_id, ( select first_name || ' ' || last_name from auth_user where username = t.mobile ) farmer_name, mobile, ( select label from vwcattle_type where value = t.cattle_type limit 1) cattle_type, ( select case when cattle_birth_date is null then cattle_age else AGE( current_date , date( cattle_birth_date ))::text end cattle_age from cattle where cattle_system_id = t.cattle_system_id limit 1), coalesce( substring( prescription_date::text from 0 for 20 ), '' ) prescription_date, ( select first_name || ' ' || last_name from auth_user where username = t.submitted_by limit 1) ai_paravet_name, submitted_by, status from t where status = any( '{0,1,2,4}' )"
    sickness_list = json.dumps(__db_fetch_values_dict(query), default=decimal_date_default)
    return render(request, 'livestock/sickness_list.html',
                  {'sickness_list': sickness_list, 'ai_paravets': ai_paravets, 'num': num})


def getSicknessData(request):
    from_date = request.POST.get('from_date')
    to_date = request.POST.get('to_date')
    ai_paravet = request.POST.get('ai_paravet')
    status = request.POST.get('status')
    filter_query = ""
    if from_date != "" and to_date != "":
        filter_query += "and created_date::date between '" + str(from_date) + "' and '" + str(to_date) + "' "
    if status != "":
        if status == '4':
            filter_query += "and status = ANY('{1,4}') "
        else:
            filter_query += "and status = " + str(status) + " "
    if ai_paravet != "":
        filter_query += "and submitted_by = '" + str(ai_paravet) + "' and submitted_by != mobile"
    query = "WITH t AS( SELECT id,to_char(created_date, 'YYYY-MM-DD HH24:MI:SS') created_date, ( SELECT created_date FROM prescription WHERE appointment_id = appointment.id limit 1) prescription_date, cattle_system_id, ( select cattle_type from cattle where cattle_system_id = appointment.cattle_system_id limit 1), ( SELECT (json->>'mobile') mobile FROM logger_instance WHERE id = healthrecord_sickness_system_id limit 1), ( SELECT (json->>'_submitted_by') submitted_by FROM logger_instance WHERE id = healthrecord_sickness_system_id limit 1), status FROM appointment WHERE appointment_type = 2) SELECT id,created_date, cattle_system_id,  ( SELECT first_name || ' ' || last_name FROM auth_user WHERE username = t.mobile limit 1) farmer_name, mobile, ( SELECT label FROM vwcattle_type WHERE value = t.cattle_type limit 1) cattle_type, ( SELECT CASE WHEN cattle_birth_date IS NULL THEN cattle_age ELSE age(CURRENT_DATE ,date(cattle_birth_date))::text END cattle_age FROM cattle WHERE cattle_system_id = t.cattle_system_id limit 1), COALESCE(substring(prescription_date::text FROM 0 FOR 20),'') prescription_date, ( SELECT first_name || ' ' || last_name FROM auth_user WHERE username = t.submitted_by limit 1)ai_paravet_name, submitted_by, status FROM t WHERE status = ANY('{0,1,2,4}') " + str(
        filter_query)
    data = json.dumps(__db_fetch_values_dict(query), default=decimal_date_default)
    return HttpResponse(data)


'''
Dashboard

'''


@login_required
def get_dashboard(request):
    division_query = "select distinct division as name, div_code id from vwunion_code"
    division_dict = __db_fetch_values_dict(division_query)
    farmer_query = "select count (*) from vwuser_org_role where role = 'Farmer'"
    paravet_query = "select count(*)from vwuser_org_role where role = 'Paravet'"
    ai_query = "select count(*) from vwuser_org_role where role = 'AI Technicians'"
    vet_query = "select count(*) from vwuser_org_role where role = 'Veterinary'"
    cattle_query = "select count(*) from cattle"
    sickness_query = "select count (*) from appointment where appointment_type ='2' "
    husbandry_query = "select count (*) from appointment where appointment_type ='1' or appointment_type ='3'"
    filter_query = ""
    if request.method == 'POST':
        from_date = request.POST.get('from_date')
        to_date = request.POST.get('to_date')
        division = request.POST.get('division')
        district = request.POST.get('district')
        upazila = request.POST.get('upazila')

        if from_date != "" and to_date != "":
            filter_query += "and appointment_date::date between '" + str(from_date) + "' and '" + str(to_date) + "' "

    farmer_count = __db_fetch_single_value(farmer_query + filter_query)
    paravet_count = __db_fetch_single_value(paravet_query + filter_query)
    ai_count = __db_fetch_single_value(ai_query + filter_query)
    vet_count = __db_fetch_single_value(vet_query + filter_query)
    cattle_count = __db_fetch_single_value(cattle_query + filter_query)
    sickness_count = __db_fetch_single_value(sickness_query + filter_query)
    husbandry_count = __db_fetch_single_value(husbandry_query + filter_query)

    return render(request, 'livestock/dashboard.html',
                  {'division': division_dict, 'farmer_count': farmer_count, 'paravet_count': paravet_count,
                   'ai_count': ai_count, 'vet_count': vet_count, 'cattle_count': cattle_count,
                   'sickness_count': sickness_count, 'husbandry_count': husbandry_count})


def get_dashboard_content(request):
    date_range = request.POST.get('date_range')
    if date_range == '':
        start_date = '01/01/2010'
        end_date = '12/28/2021'
    else:
        dates = get_dates(str(date_range))
        start_date = dates.get('start_date')
        end_date = dates.get('end_date')
    division = request.POST.get('division')
    district = request.POST.get('district')
    upazila = request.POST.get('upazila')
    farmer_query = "select count (*) from farmer  where coalesce(division::text,'') like '" + division + "' and coalesce(district::text,'') like '" + district + "' and  coalesce(upazila::text,'') like '" + upazila + "' and date(submission_time) BETWEEN '" + start_date + "' and '" + end_date + "'"
    paravet_query = "select count(*)from paravet_aitechnician where user_type = 'Paravet' and coalesce(division::text,'') like '" + division + "' and coalesce(district::text,'') like '" + district + "' and  coalesce(upazila::text,'') like '" + upazila + "' and date(submission_time) BETWEEN '" + start_date + "' and '" + end_date + "'"
    ai_query = "select count(*) from paravet_aitechnician where user_type = 'AI Technicians' and coalesce(division::text,'') like '" + division + "' and coalesce(district::text,'') like '" + district + "' and  coalesce(upazila::text,'') like '" + upazila + "' and date(submission_time) BETWEEN '" + start_date + "' and '" + end_date + "'"
    vet_query = "select count(*) from vwuser_org_role where role = 'Veterinary'"
    cattle_query = "select count(*) from vwcattle_farmer where coalesce(division::text,'') like '" + division + "' and coalesce(district::text,'') like '" + district + "' and  coalesce(upazila::text,'') like '" + upazila + "' and  date(created_date) BETWEEN '" + start_date + "' and '" + end_date + "'"
    sickness_query = "select count (*) from vwcattle_appointment where  coalesce(division::text,'') like '" + division + "' and coalesce(district::text,'') like '" + district + "' and  coalesce(upazila::text,'') like '" + upazila + "' and appointment_type ='2' and date(created_date) BETWEEN '" + start_date + "' and '" + end_date + "'"
    husbandry_query = "select count (*) from vwcattle_appointment where  coalesce(division::text,'') like '" + division + "' and coalesce(district::text,'') like '" + district + "' and  coalesce(upazila::text,'') like '" + upazila + "' and appointment_type ='1' or appointment_type ='3'  and date(created_date) BETWEEN '" + start_date + "' and '" + end_date + "'"

    farmer_count = __db_fetch_single_value(farmer_query)
    paravet_count = __db_fetch_single_value(paravet_query)
    ai_count = __db_fetch_single_value(ai_query)
    vet_count = __db_fetch_single_value(vet_query)
    cattle_count = __db_fetch_single_value(cattle_query)
    sickness_count = __db_fetch_single_value(sickness_query)
    husbandry_count = __db_fetch_single_value(husbandry_query)

    return render(request, 'livestock/dashboard_content.html',
                  {'farmer_count': farmer_count, 'paravet_count': paravet_count,
                   'ai_count': ai_count, 'vet_count': vet_count, 'cattle_count': cattle_count,
                   'sickness_count': sickness_count, 'husbandry_count': husbandry_count})


def get_district(request):
    div_code = request.POST.get('div_code')
    q = "select distinct district,dist_code from vwunion_code where div_code = '" + div_code + "'"
    dist_list = makeTableList(q)
    json_dist_list = json.dumps({'dist_list': dist_list}, default=decimal_date_default)
    return HttpResponse(json_dist_list)


def get_upazila(request):
    dist_code = request.POST.get('dist_code')
    q = "select distinct upazila,up_code from vwunion_code where dist_code = '" + dist_code + "'"
    upz_list = makeTableList(q)
    json_upz_list = json.dumps({'upz_list': upz_list}, default=decimal_date_default)
    return HttpResponse(json_upz_list)


def cascade_filter(request):
    division = request.POST.get('division')
    district = request.POST.get('district')
    upazila = request.POST.get('upazila')
    filter_query = ''
    division_query = "select distinct division as name, div_code id from vwunion_code"
    district_query = "select distinct district as name, dist_code id from vwunion_code "
    upazila_query = "select distinct upazila as name, up_code id from vwunion_code"
    division_dict = __db_fetch_values_dict(division_query)
    district_dict = __db_fetch_values_dict(district_query)
    upazila_dict = __db_fetch_values_dict(upazila_query)

    context = {'division': division_dict, 'district': district_dict, 'upazila': upazila_dict}

    return HttpResponse(json.dumps(data, default=decimal_date_default), content_type="application/json", status=200)


def get_dates(daterange):
    date_list = daterange.split('-')
    data = {
        'start_date': date_list[0], 'end_date': date_list[1]
    }
    return data


@csrf_exempt
def update_token(request):
    json_string = request.body
    data = json.loads(json_string)
    username = data['username']
    token = data['token']
    profile_id = __db_fetch_single_value(
        "select id from  usermodule_usermoduleprofile where user_id = (select id from auth_user where username = '" + username + "')")
    search_query = "select count(*)::text from user_device_map where profile_id = " + str(profile_id)
    entry_count = __db_fetch_single_value(search_query)
    if entry_count == '0':
        update_query = "INSERT INTO public.user_device_map( profile_id, firebase_token, created_at, username) VALUES ( " + str(
            profile_id) + ", '" + token + "', now(), '" + username + "'); "
    else:

        update_query = "update user_device_map set firebase_token='" + token + "', updated_at = now() where username = '" + username + "'"
    cur = connection.cursor()

    # execute the UPDATE  statement

    cur.execute(update_query)
    return HttpResponse(json.dumps('Token updated'), status=200)


def update_user_device(data, user_information, profile_id):
    search_query = "select count(*)::text from user_device_map where profile_id = " + str(profile_id) + ""
    entry_count = __db_fetch_single_value(search_query)
    if entry_count == '0':
        update_query = "INSERT INTO public.user_device_map( profile_id, firebase_token, created_at, username) VALUES ( " + str(
            profile_id) + ", '" + data['firebase_token'] + "', now(), '" + user_information['username'] + "'); "
    else:

        update_query = "update user_device_map set firebase_token='" + data[
            'firebase_token'] + "', updated_at = now() where username = '" + user_information['username'] + "'"
    cur = connection.cursor()

    # execute the UPDATE  statement

    cur.execute(update_query)


def send_push_message(username, notification_type, title, content, cattle_id, farmer_id, prescription_id):
    firebase_query = "select firebase_token from user_device_map where username = '" + username + "'"
    print
    firebase_query

    firebase_token = None

    cursor = connection.cursor()

    cursor.execute(firebase_query)

    fetchVal = cursor.fetchone()

    if fetchVal:
        firebase_token = fetchVal[0]

    cursor.close()
    print
    "firebase_token---------------------------------------------------------"
    print
    firebase_token
    data_message = {}
    success = '0'
    if firebase_token:
        # unique firebase token for the user

        registration_id = []

        registration_id.append(firebase_token)

        message_title = title

        message_body = content

        user = User.objects.filter(username=username).first()

        user_profile = user.usermoduleprofile
        user_role = UserRoleMap.objects.filter(user_id=user_profile.id)
        roles = [u.role.role for u in user_role]
        user_information = {

        }
        user_information['Name'] = user.first_name + " " + user.last_name
        user_information['Email'] = user.email
        user_information['is_superuser'] = str(user.is_superuser)
        user_information['is_staff'] = str(user.is_staff)
        user_information['IsAdmin'] = str(user_profile.admin)
        user_information['Role'] = roles
        user_information["farm_id"] = ''
        user_information["username"] = username
        user_information["paravet_flag"] = user_profile.is_req_para_ai
        user_image = get_user_image(user.id)
        user_information["user_image"] = user_image

        data_message = {
            "notif_type": notification_type,
            "title": title,
            "content": content,
            "cattle_id": cattle_id,
            "farmer_id": farmer_id,
            "prescription_id": prescription_id,
            "user": user_information

        }

        print
        "firebase_token-before service--------------------------------------------------------"
        result = push_service.notify_multiple_devices(registration_ids=registration_id, message_title=message_title,

                                                      message_body=message_body, data_message=data_message)
        print
        "firebase_token serviceend --------------------------------------------------------"
        print
        result
        if result['success']:
            success = str(result['success'])
        if data_message:
            data_message = str(data_message)
    else:
        firebase_token = 'Not Found'
    print
    "__________________________ start________________________"
    print
    username
    print
    firebase_token
    print
    title
    print
    content
    print
    success

    print
    "__________________________ end________________________"

    q = "INSERT INTO public.mobile_push_notification_track(id, mobile, firebase_token, msg_title, msg_body, success,created_date)VALUES (DEFAULT, '" + username + "', '" + firebase_token + "', '" + title + "', '" + content + "','" + success + "',NOW())"

    __db_commit_query(q)
    return 0


# This method is not using currently
def send_prescription_sms(request):
    if request.method == 'POST':
        sms_text = request.POST.get("sms_text")
        send_other = request.POST.get("send_other")
        f_id = request.POST.get("f_id")
        print
        "farmer mobile is:::" + str(f_id)
        if send_other == '1':
            mobile_num_list = __db_fetch_single_value(
                "with t1 as(select user_id,(select username from auth_user where id =(select user_id from usermodule_usermoduleprofile where id =user_farmer_map.user_id)) para_ai_mobile from user_farmer_map where farmer_id=(select id from farmer where mobile = '" + f_id + "')) select string_to_array((string_agg(para_ai_mobile,',')),',') mobile_list from t1 ")
            if mobile_num_list:
                for temp in mobile_num_list:
                    send_sms(temp, sms_text)
        else:
            send_sms(f_id, sms_text)
        return HttpResponse(json.dumps('ok', default=decimal_date_default), content_type="application/json", status=200)


def update_cattle_type(request):
    query = "select update_cattle_type()"
    __db_commit_query(query)
    return HttpResponse('')


def get_user_image(user_id):
    query = "select coalesce(user_img,'') from users_additional_info  where user_id = " + str(user_id) + " limit 1 "
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = cursor.fetchone()
    img = ''
    if fetchVal:
        img = fetchVal[0]
    cursor.close()
    return img
