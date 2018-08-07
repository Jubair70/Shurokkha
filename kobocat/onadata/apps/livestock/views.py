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
from onadata.apps.usermodule.models import OrganizationRole,MenuRoleMap,UserRoleMap
from django.contrib.auth.models import User
from django.core.mail import send_mail, BadHeaderError
import smtplib
from datetime import datetime as dt
import time

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
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj

    raise TypeError



'''

    MEDICINE::
    ADD,UPLOAD,EDIT,DELETE

'''



@login_required
def medicine_list(request):
    q="select id,name from medicine_type"
    type_list = makeTableList(q)
    return render(request, "livestock/medicine_list.html",{'type_list':type_list})


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
        check_q = "select * from medicine where medicine_type::text like '"+medicine_type+"' and medicine_name like '"+medicine_name+"' and  packsize like '"+pack_size+"' "
        data = __db_fetch_values_dict((check_q))
        if len(data) == 0:
            if id == '':
                q = "INSERT INTO public.medicine(id, medicine_type, medicine_name, packsize, created_at, created_by)VALUES (DEFAULT , '"+medicine_type+"','"+medicine_name+"', '"+pack_size+"', NOW(), "+str(request.user.id)+");"
            else:
                q = "update public.medicine set medicine_type = "+medicine_type+" ,medicine_name = '"+medicine_name+"',packsize='"+pack_size+"' where id ="+id
            __db_commit_query(q)
        else:
            return HttpResponse(json.dumps(len(data)), content_type="application/json", status=500)

        return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)


def upload_medicine(request):
    des = handle_uploaded_file(request.FILES['ex_file'])
    xlsx = pd.ExcelFile(des)        # open the file
    df = xlsx.parse(0)              # get the first sheet as an object
    # print pd.__version__
    duplicate_medicine = []
    for index, row in df.iterrows():
        type = row[0]
        type_id= __db_fetch_single_value("select id from medicine_type where name = '"+type+"'")
        name = row[1]
        pack_size =  row[2]
        check_q = "select * from medicine where medicine_type::text like '" + str(type_id) + "' and medicine_name like '" + name + "' and  packsize like '" + pack_size + "' "
        data = __db_fetch_values_dict((check_q))
        if len(data) == 0:
            q = "INSERT INTO public.medicine(id, medicine_type, medicine_name, packsize, created_at, created_by)VALUES (DEFAULT , '" + str(type_id) + "','" + name + "', '" + pack_size + "', NOW(), " + str(
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
        filePath = 'onadata/media/'+str(file.name)
        destination = open('onadata/media/'+str(file.name), 'w+')
        for chunk in file.chunks():
            destination.write(chunk)
        destination.close()
    return filePath



def delete_medicine(request,id):
    delete_q = "delete from medicine where id = "+str(id)
    __db_commit_query(delete_q)
    return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)


def edit_medicine(request,id):
    q = "select * from medicine where id ="+str(id)
    dataset = __db_fetch_values_dict(q)
    for temp in dataset:
        data = {
            'med_type' : temp['medicine_type'],'medicine_name' : temp['medicine_name'],'pack_size' : temp['packsize']
         }
    return HttpResponse(json.dumps(data), content_type="application/json", status=200)





'''

    FARMER & CATTLE

'''

@login_required
def farmer_list(request):
    return render(request,"livestock/farmer_list.html")


def get_farmer_table(request):
    q = "select * from farmer where deleted_at is null"
    dataset = __db_fetch_values_dict(q)
    return render(request,"livestock/farmer_table.html",{'dataset' : dataset})

@login_required
def approval_list(request):
    q = "with paravet as(select count(*) as paravets from public.approval_queue where status = 0 and role_name ='Paravet'), ai as(select count(*) as ai_techs from public.approval_queue where status = 0 and role_name ='AI Technicians') select paravet.paravets as num_paravet,ai.ai_techs as num_ai_techs from paravet,ai"
    paravet = 0
    ai_tech = 0
    for temp in __db_fetch_values_dict(q):
        paravet = temp['num_paravet']
        ai_tech = temp['num_ai_techs']
    context = {
        'paravet' : paravet,'ai_tech' : ai_tech
    }
    return render(request, "livestock/approval_list.html",context)

def get_approval_table(request):
    status = request.POST.get('status')
    q = "select * from approval_queue where  status::text like '"+str(status)+"'"
    dataset = __db_fetch_values_dict(q)
    return render(request,"livestock/approval_table.html",{'dataset' : dataset})


def approve(request,id):
    role_name = request.POST.get('role')
    mobile = request.POST.get('mobile')
    q = "update approval_queue set status = 1,approve_by = "+str(request.user.id)+",approval_date = NOW() where id  ="+str(id)
    __db_commit_query(q)
    role_list = []
    role_list.append(role_name)
    user_roles = OrganizationRole.objects.filter(role__in=role_list)
    user = User.objects.filter(username=mobile).first()
    profile = user.usermoduleprofile
    for role in user_roles:
        UserRoleMap(user=profile, role=role).save()

    # TO DO ::SMS Notification
    send_mail(
        'Successful Approval',
        'Hi,\n\nWelcome to Shurokkha!!\n\nYou are successfully approved as ' + role_name + '.',
        'mpowersocial2018@gmail.com',
        ['mpowersocialent@gmail.com'],
        fail_silently=False,
    )
    return HttpResponse(json.dumps("Approved Successfully."), content_type="application/json", status=200)


def reject(request,id):
    role = request.POST.get('role')
    mobile = request.POST.get('mobile')
    comment = request.POST.get('comment')
    q = "update approval_queue set status = 2,approve_by = "+str(request.user.id)+",approval_date = NOW(),rejection_cause = '"+comment+"' where id  ="+str(id)
    __db_commit_query(q)
    # TO DO :: SMS Notification
    send_mail(
        'Rejected Approval',
        'Hi,\n\nWelcome to Shurokkha!!\n\nYou are Rejected.',
        'mpowersocial2018@gmail.com',
        ['mpowersocialent@gmail.com'],
        fail_silently=False,
    )
    return HttpResponse(json.dumps("Rejected Successfully."), content_type="application/json", status=200)


def farmer_profile(request,id):
    cattle_proupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    cattle_proupdate_form_owner = __db_fetch_single_value(cattle_proupdate_form_owner_q)
    q = "select *,date(submission_time) as regi_date from farmer where id ="+str(id)
    dataset = __db_fetch_values_dict(q)
    return render(request,'livestock/farmer_profile.html',{'dataset' : dataset,'FARMER_ID' : id,'cattle_proupdate_form_owner' : cattle_proupdate_form_owner})


def get_cattle_list(request,id):
    cattle_type = request.POST.get('cattle_type')
    cattle_regi_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'cattle_registration'"
    cattle_regi_form_owner = __db_fetch_single_value(cattle_regi_form_owner_q)
    #q = " select *,get_form_option_text(597,'cattle_type',cattle_type) cattle_type_text,get_form_option_text(597,'cattle_origin',cattle_origin) cattle_origin_text from vwcattle_registration where cattle_type::text  like '"+cattle_type+"'"
    q = " select *,date(created_date)::text as register_date ,(select label from vwcattle_type where value =cattle_type ) cattle_type_text,(select label from vwcattle_origin where value =cattle_origin ) cattle_origin_text from cattle where cattle_type::text  like '"+cattle_type+"'"
    dataset = __db_fetch_values_dict(q)
    data_list = []
    age_cattle = 0
    for temp in dataset:
        data_dict = {}
        if temp['cattle_birth_date'] is not None:
            dob_cattle = temp['cattle_birth_date']
            dob_cf = dt.strptime(temp['cattle_birth_date'], '%Y-%m-%d')
            age_cattle = ((dt.today() - dob_cf).days / 30)
        data_dict['cattle_type_text'] = temp['cattle_type_text']
        data_dict['cattle_age'] = age_cattle
        img = ""
        if temp['picture'] is not None:
            img = temp['picture']
        data_dict['image_url'] = "/media/" + cattle_regi_form_owner + "/attachments/" + img
        data_list.append(data_dict.copy())
        data_dict.clear()
    return render(request,'livestock/cattle_list_table.html',{'dataset' : data_list,'cattle_regi_form_owner' :cattle_regi_form_owner})


def upload_prescription(request):
    if request.method == 'POST':
        file = request.FILES['ex_file']
        millis = int(round(time.time() * 1000))
        if file:
            filePath = 'onadata/media/prescription/'+str(millis)+'_'+str(file.name)
            destination = open('onadata/media/prescription/'+str(millis)+'_'+str(file.name), 'w+')
            for chunk in file.chunks():
                destination.write(chunk)
            destination.close()
        des = filePath
        xlsx = pd.ExcelFile(des)  # open the file
        df = xlsx.parse(0)  # get the first sheet as an object
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
                #duplicate_item_str = "Diagnosis "+diagnosis_1 +" of cattle  type "+ unicode(type_1, 'utf-8') +" with weight range from  "+str(weight_from_1)+" to "+str(weight_to_1) + " is already existed."
                #duplicate_diagnosis.append(duplicate_item_str)
                #continue
            #else:
            insert_diagnosis_q = "INSERT INTO public.diagnosis(id, diagnosis_name, cattle_type, weight_from, weight_to, created_by, created_date)VALUES (DEFAULT ,'" + diagnosis_1 + "', " + str(
                cattle_type_id) + ", " + str(weight_from_1) + ", " + str(weight_to_1) + ", " + str(
                request.user.id) + ", NOW())  RETURNING id;"
            inserted_id = __db_fetch_single_value(insert_diagnosis_q)
            for index, row in df.iterrows():
                #*** Diagnosis *******#
                diagnosis_name = row[0]
                description_type = row[1]
                cattle_type = row[2].encode('utf-8')

                #print cattle_type_id
                weight_from = row[3]
                weight_to = row[4]

                # *** Medicine *******#
                med_type = row[5]
                med_type_id = __db_fetch_single_value("select id from medicine_type where name = '" + med_type + "'")
                #print med_type_id
                med_name = row[6]
                packsize = row[7]
                qty = row[8]
                dose = row[9]
                route = row[10]
                days = row[11]

                advice = row[12]
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

    return render(request,'livestock/upload_prescription.html')



def delete_duplicate_presciption_diagnosis(data):
    for tmp in data:
        delete_advice_q = "delete from diagnosis_advice where diagnosis_id = " + str(tmp['id'])
        __db_commit_query(delete_advice_q)
        delete_medicine_q = "delete from diagnosis_medicine where diagnosis_id = " + str(tmp['id'])
        __db_commit_query(delete_medicine_q)
        delete_q = "delete from diagnosis where id = "+str(tmp['id'])
        __db_commit_query(delete_q)
    return "1"



'''
     CATTLE PROFILE

'''

def cattle_profile(request,cattle_id,appointment_id):
    q = "select * from appointment where id="+str(appointment_id)
    data = __db_fetch_values_dict(q)
    clinical_findings_data = []
    for temp in data:
        appointment_status = temp['status']
        appointment_type = temp['appointment_type']
        if ((appointment_type == 2) and (appointment_status == 1)):
            clinical_findings_id = temp['clinical_diagnosis_id']
            clinical_findings_data = __db_fetch_values_dict("select *, string_to_array(wrong_feeding_last_days,',')::int[] wrong_feeding_last_days_arr, string_to_array(sickness_sign,',')::int[] sickness_sign_arr, string_to_array(behavioral_signs,',')::int[] behavioral_signs_arr, string_to_array(mouth_digestion_sign,',')::int[] mouth_digestion_sign_arr, string_to_array(repiratory_sign,',')::int[] repiratory_sign_arr, string_to_array(reproductive_problem,',')::int[] reproductive_problem_arr, string_to_array(milking_problem,',')::int[] milking_problem_arr, string_to_array(male_reproductive_problem,',')::int[] male_reproductive_problem_arr, string_to_array(skin_problem,',')::int[] skin_problem_arr, string_to_array(foot_problem,',')::int[] foot_problem_arr, string_to_array(megot,',')::int[] megot_arr from clinical_findings where id = "+str(clinical_findings_id))
            #print clinical_findings_data
    cattle_info = get_cattle_info(cattle_id)
    farmer_mobile = cattle_info.get('mobile')
    farmer_info= get_farmer_info(farmer_mobile)

    option_dict = {
        'appointment_id' : appointment_id,'appointment_status' : appointment_status,'appointment_type' : appointment_type,
        'wrong_feeding_last_days' : get_option_list('wrong_feeding_last_days'),
        'muzzle': get_option_list('muzzle'),'same_sickness_other_cattle' : get_option_list('same_sickness_other_cattle'),
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
        'test_data' : [1,2,3],'clinical_findings_data' : get_clinical_findings_dict(clinical_findings_data)
    }

    context = dict(cattle_info.items() + farmer_info.items() +option_dict.items())

    return render(request,'livestock/cattle_profile.html',context)

def get_clinical_findings_dict(list_data):
    dict = {}
    for temp in list_data:
        dict= {
            'id' : temp['id'],
            'complain_details' : temp['complain_details'],
            'treatment_history' : temp['treatment_history'],
            'same_sickness_other_cattle' : temp['same_sickness_other_cattle'],
            'sick_cattle_affected_or_died' : temp['sick_cattle_affected_or_died'],
            'deworming_history' : temp['deworming_history'],
            'feeding_history' : temp['feeding_history'],
            'wrong_feeding_last_days': temp['wrong_feeding_last_days_arr'],
            'rumination' : temp['rumination'],
            'lacrimation' : temp['lacrimation'],
            'muzzle': temp['muzzle'],
            'sickness_sign': temp['sickness_sign_arr'],
            'behavioral_signs' : temp['behavioral_signs_arr'],
            'mouth_digestion_sign' : temp['mouth_digestion_sign_arr'],
            'stool_condition' : temp['stool_condition'],
            'repiratory_sign' : temp['repiratory_sign_arr'],
            'reproductive_problem' : temp['reproductive_problem_arr'],
            'milking_problem' : temp['milking_problem_arr'],
            'male_reproductive_problem' : temp['male_reproductive_problem_arr'],
            'skin_problem' : temp['skin_problem_arr'],
            'foot_problem': temp['foot_problem_arr'],
            'megot' : temp['megot_arr'],
            'disease_pattern': temp['disease_pattern'],
            'tentative_diagnosis': temp['tentative_diagnosis']
        }

    return dict

def get_cattle_info(id):
    q = "select mobile,cattle_type,coalesce(round(cattle_weight::numeric,2)::text,'') cattleweight,AGE(current_date ,date(cattle_birth_date))::text cattle_age,coalesce(cattle_name,'') cattle_name,(select label from vwcattle_type where value = cattle_type limit 1) as cattletype,coalesce(calf_birth_weight,'') calf_birth_weight from cattle where cattle_system_id = " + str(id)
    dataset = __db_fetch_values_dict(q)
    cattle_dict = {}
    for temp in dataset:
        cattle_dict = {'cattle_type' : temp['cattle_type'],'mobile' : temp['mobile'],'cattle_name' : temp['cattle_name'],'cattle_weight' : temp['cattleweight'],'cattle_age' : temp['cattle_age'],'cattle_type_text': temp['cattletype'], 'calf_birth_weight' : temp['calf_birth_weight']}
    return cattle_dict


def get_farmer_info(mobile):
    farmerprofileupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    farmerprofileupdate_form_owner = __db_fetch_single_value(farmerprofileupdate_form_owner_q)
    q = "select id, coalesce(farmer_name,'') farmer_name,mobile,date(submission_time)::text registration_date,image from farmer where mobile = '"+mobile+"'"
    dataset = __db_fetch_values_dict(q)
    farmer_dict = {}
    img_path = ''
    for temp in dataset:
        if temp['image'] is not None:
            img = temp['image']
            img_path = "media/" + farmerprofileupdate_form_owner + "/attachments/" + img
        farmer_dict = { 'id' : temp['id'],'farmer_name' : temp['farmer_name'], 'mobile' : temp['mobile'], 'registration_date' : temp['registration_date'],  'image_url' :  img_path
        }
    return farmer_dict


def get_option_list(fieldname):
    q = "select value_text as val,value_label as label from xform_extracted where xform_id = 604 and field_name = '"+fieldname+"'"
    dataset = makeTableList(q)
    return dataset


def clinical_findings(request,appointment_id):
    print "trigger clinical_findings"
    q = ""
    if request.method == 'POST':
        edit_id = request.POST.get('clinical_findings_id')
        complain_details = request.POST.get('complain_details')
        treatment_history = request.POST.get('treatment_history')
        same_sickness_other_cattle = request.POST.get('same_sickness_other_cattle')
        sick_cattle_affected_or_died = request.POST.get('sick_cattle_affected_or_died')
        deworming_history = request.POST.get('deworming_history')
        feeding_history = request.POST.get('feeding_history')
        wrong_feeding_last_days = get_multiple_input_string(request.POST.getlist('wrong_feeding_last_days[]'))
        rumination = request.POST.get('rumination')
        lacrimation = request.POST.get('lacrimation')
        muzzle = request.POST.get('muzzle')
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
            q="update public.clinical_findings set complain_details = '"+complain_details+"',sick_cattle_affected_or_died = "+str(sick_cattle_affected_or_died)+",same_sickness_other_cattle = "+str(same_sickness_other_cattle)+", treatment_history='"+treatment_history+"', deworming_history='"+deworming_history+"', feeding_history='"+feeding_history+"', wrong_feeding_last_days='"+wrong_feeding_last_days+"', rumination='"+rumination+"', lacrimation='"+lacrimation+"', muzzle='"+muzzle+"', sickness_sign='"+sickness_sign+"', behavioral_signs='"+behavioral_signs+"', mouth_digestion_sign='"+mouth_digestion_sign+"', stool_condition='"+stool_condition+"', repiratory_sign='"+repiratory_sign+"', reproductive_problem='"+reproductive_problem+"', milking_problem='"+milking_problem+"', male_reproductive_problem='"+male_reproductive_problem+"', skin_problem='"+skin_problem+"', foot_problem='"+foot_problem+"', megot='"+megot+"', disease_pattern='"+disease_pattern+"', tentative_diagnosis='"+tentative_diagnosis+"',updated_by="+str(request.user.id)+",updated_date=NOW()"
            __db_commit_query(q)
        else:
            q = "INSERT INTO public.clinical_findings(id, appointment_id, complain_details, sick_cattle_affected_or_died, same_sickness_other_cattle, treatment_history, deworming_history, feeding_history, wrong_feeding_last_days, rumination, lacrimation, muzzle, sickness_sign, behavioral_signs, mouth_digestion_sign, stool_condition, repiratory_sign, reproductive_problem, milking_problem, male_reproductive_problem, skin_problem, foot_problem, megot, disease_pattern, tentative_diagnosis, created_by, created_date)VALUES (DEFAULT , "+str(appointment_id)+",'"+complain_details+"', "+str(sick_cattle_affected_or_died)+", "+str(same_sickness_other_cattle)+", '"+treatment_history+"', '"+deworming_history+"', '"+feeding_history+"', '"+wrong_feeding_last_days+"', '"+rumination+"', '"+lacrimation+"', "+muzzle+", '"+sickness_sign+"', '"+behavioral_signs+"', '"+mouth_digestion_sign+"', '"+stool_condition+"','"+repiratory_sign+"','"+reproductive_problem+"', '"+milking_problem+"', '"+male_reproductive_problem+"', '"+skin_problem+"', '"+foot_problem+"', '"+megot+"','"+disease_pattern+"', '"+tentative_diagnosis+"', "+str(request.user.id)+", NOW()) RETURNING id"
            clinical_dignosis_id = __db_fetch_single_value(q)
            update_q = "update appointment set status =1,clinical_diagnosis_id = "+str(clinical_dignosis_id)+" where id ="+str(appointment_id)
            __db_commit_query(update_q)
    #print q
    return HttpResponse(json.dumps("Clinical findings added"), content_type="application/json", status=200)




def get_multiple_input_string(data_list):
    input_str = ""
    #  check the list is empty
    if list(data_list):
        # list converts to comma seperated string
        input_str = ' , '.join(str(x) for x in list(data_list))
    return input_str


def get_diagnosis_name(request):
    diagnosis_name = "%" + request.POST.get("diagnosis_name") + "%";
    q = "select * from diagnosis where diagnosis_name like '"+diagnosis_name+"'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json", status=200)


def advisory_list(request):
    return render(request, 'livestock/advisory_list.html')


def get_advisory_table(request):
    q = "select * from appointment"
    dataset = __db_fetch_values_dict(q)
    return render(request, 'livestock/advisory_table.html',{'dataset': dataset})


def submit_prescription(request,appointment_id):
    if request.method == 'POST':
        clinical_findings_id = request.POST.get('clinical_findings_id_prescription')
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

    return HttpResponse(json.dumps("Prescription added"), content_type="application/json", status=200)


def get_medicine_name(request):
    m_name = "%" + request.POST.get("m_name") + "%"
    m_type = "%" + request.POST.get("m_type") + "%"
    packsize = "%" + request.POST.get("packsize") + "%"
    q = "select medicine_name from vwmedicine where medicine_name like '" + m_name + "' and m_type like '"+m_type+"' and packsize like '"+packsize+"'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)

def get_medicine_type(request):
    m_name = "%" + request.POST.get("m_name") + "%"
    m_type = "%" + request.POST.get("m_type") + "%"
    packsize = "%" + request.POST.get("packsize") + "%"
    q = "select DISTINCT m_type from vwmedicine where medicine_name like '" + m_name + "' and m_type like '"+m_type+"' and packsize like '"+packsize+"'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)


def get_medicine_packsize(request):
    m_name = "%" + request.POST.get("m_name") + "%"
    m_type = "%" + request.POST.get("m_type") + "%"
    packsize = "%" + request.POST.get("packsize") + "%"
    q = "select DISTINCT packsize from vwmedicine where medicine_name like '" + m_name + "' and m_type like '"+m_type+"' and packsize like '"+packsize+"'"
    data_list = __db_fetch_values_dict(q)
    return HttpResponse(json.dumps(data_list, default=decimal_date_default), content_type="application/json",
                        status=200)
