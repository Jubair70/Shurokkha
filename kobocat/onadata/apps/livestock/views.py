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
from django.forms.models import inlineformset_factory
from collections import OrderedDict
import pandas as pd
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime as dt
import dateutil.parser
from django.core.files.storage import FileSystemStorage
from xml.etree import ElementTree as ET
import requests
import os
import time
import sys
from django.contrib.auth.models import User
from onadata.apps.usermodule.models import UserModuleProfile, Organizations

import pandas as pd

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
        check_q = "select * from medicine where medicine_type::text like '"+medicine_type+"' and medicine_name like '"+medicine_name+"' and  packsize like '"+pack_size+"' "
        data = __db_fetch_values_dict((check_q))
        print len(data)
        if len(data) == 0:
            q = "INSERT INTO public.medicine(id, medicine_type, medicine_name, packsize, created_at, created_by)VALUES (DEFAULT , '"+medicine_type+"','"+medicine_name+"', '"+pack_size+"', NOW(), "+str(request.user.id)+");"
            __db_commit_query(q)
        else:
            return HttpResponse(json.dumps(len(data)), content_type="application/json", status=500)

        return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)


def upload_medicine(request):
    des = handle_uploaded_file(request.FILES['ex_file'])
    # open the file
    xlsx = pd.ExcelFile(des)
    # get the first sheet as an object
    df = xlsx.parse(0)
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
        #print destination
        #destination = open('/tmp', 'wb+')
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