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
    q = "select * from farmer"
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
        'zinia@mpower-social.com',
        [mobile],
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
        'zinia@mpower-social.com',
        [mobile],
        fail_silently=False,
    )
    return HttpResponse(json.dumps("Rejected Successfully."), content_type="application/json", status=200)