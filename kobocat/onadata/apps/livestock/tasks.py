import re
import sys
from celery import task
from django.db import transaction
from django.conf import settings
from django.db import connection
from collections import OrderedDict
from onadata.apps.livestock.views import *


@task()
def prescription_upload(df,user_id):
    try:
        df = df.fillna({'Medicine Type': 0, 'Type': 0, 'Advices': 0, 'Dose': 0, 'Route': 0, 'Days': 0, 'Medine Name': 0},
                       inplace=True)

        duplicate_diagnosis = []
        df_1 = df.groupby(['Tentative Diagnosis', 'Type', 'Body Weight From', 'Body Weight To']).size().reset_index(
            name='Freq')
        for index_1, row_1 in df_1.iterrows():
            diagnosis_1 = row_1[0]
            type_1 = row_1[1].encode('utf-8')
            cattle_type_id = __db_fetch_single_value(
                "select value from vwcattle_type where label = '" + type_1 + "'")
            weight_from_1 = row_1[2]
            weight_to_1 = row_1[3]
            check_q = "select id from diagnosis where diagnosis_name::text like '" + diagnosis_1 + "' and cattle_type::text like '" + str(
                cattle_type_id) + "' and  weight_from::text like '" + str(
                weight_from_1) + "' and  weight_to::text like '" + str(weight_to_1) + "'"
            data = __db_fetch_values_dict((check_q))
            if len(data) != 0:
                delete_duplicate_presciption_diagnosis(data)
            insert_diagnosis_q = "INSERT INTO public.diagnosis(id, diagnosis_name, cattle_type, weight_from, weight_to, created_by, created_date)VALUES (DEFAULT ,'" + diagnosis_1 + "', " + str(
                cattle_type_id) + ", " + str(weight_from_1) + ", " + str(weight_to_1) + ", " + str(
                user_id) + ", NOW())  RETURNING id;"
            inserted_id = __db_fetch_single_value(insert_diagnosis_q)
            df_filtered = df[(df['Tentative Diagnosis'] == diagnosis_1) & (df['Body Weight From'] == weight_from_1) & (
                df['Body Weight To'] == weight_to_1)]
            for index, row in df_filtered.iterrows():
                # *** Diagnosis *******#
                diagnosis_name = row[0]
                description_type = row[1]
                if row[2] != 0:
                    cattle_type = row[2].encode('utf-8')
                else:
                    cattle_type = ''

                # print cattle_type_id
                weight_from = row[3]
                weight_to = row[4]

                # *** Medicine *******#
                med_type = row[5]

                if med_type != 0:
                    med_type_id = __db_fetch_single_value("select id from medicine_type where name = '" + med_type + "'")
                else:
                    med_type_id = 0
                # print med_type_id
                # med_name = row[6]
                packsize = row[7]
                qty = row[8]
                # dose = row[9]
                # route = row[10]
                # days = row[11]
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

                if ((diagnosis_1 == diagnosis_name) and (type_1 == cattle_type) and (weight_from_1 == weight_from) and (
                    weight_to_1 == weight_to)):
                    if description_type == 'M':
                        insert_diagnosis_medicine_q = "INSERT INTO public.diagnosis_medicine(id, diagnosis_id, medicine_type, medicine_name, packsize, quantity, dose, route, days)" \
                                                      "VALUES (DEFAULT, " + str(inserted_id) + ", " + str(
                            med_type_id) + ", '" + med_name + "', '" + packsize + "', " + str(
                            qty) + ", '" + dose + "', '" + route + "', '" + days + "');"
                        __db_commit_query(insert_diagnosis_medicine_q)
                    if description_type == 'A':
                        insert_diagnosis_advice_q = "INSERT INTO public.diagnosis_advice(id, diagnosis_id, advice)VALUES (DEFAULT , " + str(
                            inserted_id) + ", '" + advice + "');"
                        __db_commit_query(insert_diagnosis_advice_q)
        if len(duplicate_diagnosis) == 0:
            #return HttpResponse(json.dumps('ok'), content_type="application/json", status=200)
            #print "OK"
            tag =  1
        else:
            duplicate_item = ", ".join(x for x in duplicate_diagnosis)
            duplicate_item = duplicate_item + " already exist."
            #return HttpResponse(json.dumps(duplicate_item), content_type="application/json", status=500)
            print duplicate_item
            tag = 0
        return 1
    except Exception as e:
        print e
        return -1



def delete_duplicate_presciption_diagnosis(data):
    for tmp in data:
        delete_advice_q = "delete from diagnosis_advice where diagnosis_id = " + str(tmp['id'])
        __db_commit_query(delete_advice_q)
        delete_medicine_q = "delete from diagnosis_medicine where diagnosis_id = " + str(tmp['id'])
        __db_commit_query(delete_medicine_q)
        delete_q = "delete from diagnosis where id = "+str(tmp['id'])
        __db_commit_query(delete_q)
    return "1"



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


