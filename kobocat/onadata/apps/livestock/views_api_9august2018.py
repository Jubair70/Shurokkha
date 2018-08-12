#!/usr/bin/env python
# -*- coding: utf-8 -*-
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.hashers import make_password
from django.contrib import messages
from django.db.models import Count,Q
from django.http import (
    HttpResponseRedirect, HttpResponse)
from django.shortcuts import render_to_response, get_object_or_404
from django.template import RequestContext,loader
from django.contrib.auth.models import User
from datetime import date, timedelta, datetime
# from django.utils import simplejson
import json

from django.db import (IntegrityError,transaction)
from django.db.models import ProtectedError
from django.shortcuts import redirect
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.usermodule.forms import UserForm, UserProfileForm, ChangePasswordForm, UserEditForm,OrganizationForm,OrganizationDataAccessForm,ResetPasswordForm
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory, UserFailedLogin,Organizations,OrganizationDataAccess

from onadata.apps.usermodule.models import OrganizationRole,MenuRoleMap,UserRoleMap

from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import pandas
from django.shortcuts import render
from collections import OrderedDict

from django.core.files.storage import FileSystemStorage
import string
import random


from django.core.mail import send_mail, BadHeaderError
import smtplib
from onadata.apps.livestock import views




def get_farm_id(auth_user_id):
    farm_id = 0
    query = "select organisation_name_id from usermodule_usermoduleprofile where user_id ="+str(auth_user_id)+" limit 1"
    farm_id = views.__db_fetch_single_value(query)
    print ("Farm ID ::"+str(farm_id))
    return farm_id
# mobile login verify

@csrf_exempt
def login_verify(request):
    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
        print "check1"
        print request.body
        json_string = request.POST.get('data')
        print "check2" + json_string
        data = json.loads(json_string)
        print "check3 "
        username = data['phone']
        password = data['verification_code']
        # Use Django's machinery to attempt to see if the username/password
        # combination is valid - a User object is returned if it is.
        user = authenticate(username=username, password=password)

        # If we have a User object, the details are correct.
        # If None (Python's way of representing the absence of a value), no user
        # with matching credentials was found.

        if user:

            # number of login attempts allowed
            max_allowed_attempts = 5
            # count of invalid logins in db
            counter_login_attempts = UserFailedLogin.objects.filter(user_id=user.id).count()
            # check for number of allowed logins if it crosses limit do not login.
            if counter_login_attempts > max_allowed_attempts:
                # return HttpResponse("Your account is locked for multiple invalid logins, contact admin to unlock")
                messages.error(request,
                               'Your account is locked for multiple invalid logins, contact admin to unlock!')
                user_information['login_status'] = 'Successfully logged in'

                return HttpResponse('Login failed', status=409)

            # Is the account active? It could have been disabled.
            if user.is_active:

                if hasattr(user, 'usermoduleprofile'):
                    # user profile
                    user_profile = user.usermoduleprofile
                    if date.today() > user_profile.expired.date():
                        return HttpResponse('Login failed', status=409)
                    # if user and password is valid then
                    print user_profile.id
                    user_role = UserRoleMap.objects.filter(user_id=user_profile.id)
                    roles = [u.role.role for u in user_role]
                    # profile_organization = ProfileOrganization.objects.filter(profile_id = user_profile.id)

                    # organization_list = [pro.organization.organization for pro in profile_organization]
                    # user role
                    # print user_role
                    user_information = {

                    }
                    user_information['Name'] = user.first_name + " " + user.last_name
                    user_information['Email'] = user.email
                    user_information['is_superuser'] = str(user.is_superuser)
                    user_information['is_staff'] = str(user.is_staff)
                    user_information['IsAdmin'] = str(user_profile.admin)
                    # user_information['EmployeeId'] = str(user_profile.employee_id)
                    # user_information['Position'] = user_profile.position
                    user_information['Role'] = roles
                    user_information["farm_id"] = get_farm_id(user.id)
                    user_information["username"] = username
                    # user_information['Organizations'] = [pro.organization.organization for pro in profile_organization]
                    # user_information['Claims'] = mobile_access(request,username)

                    print user_information
                login(request, user)
                UserFailedLogin.objects.filter(user_id=user.id).delete()
                # return HttpResponseRedirect(request.POST['redirect_url'])
                return HttpResponse(json.dumps(user_information))



            else:
                # An inactive account was used - no logging in!
                # return HttpResponse("Your User account is disabled.")
                user_information['login_status'] = 'Your account is Inactive!'
                return HttpResponse('Login failed', status=409)

    return HttpResponse('Login failed', status=409)


def id_generator(size=8):
    return ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(size))


# mobile save user
@csrf_exempt
def save_user(request):
    """{
 "name":"Jon Snow",
 "phone":"01234567891",
 "occupation":"Farmer"
}


    """
    json_string = request.POST.get('data')
    print json_string
    # print json_string
    data = json.loads(json_string)
    submitted_data = {}
    submitted_data['username'] = data['phone']
    user = User.objects.filter(username=data['phone']).first()
    password = id_generator()
    # when login
    if user is not None:
        # password = id_generator()
        print user
        encrypted_password = make_password(password)
        user.password = encrypted_password
        user.save()
        profile = user.usermoduleprofile
        next_expiry_date = (datetime.today() + timedelta(minutes=5))

        profile.expired = next_expiry_date
        profile.save()

        passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
        passwordHistory.password = encrypted_password
        passwordHistory.save()

    # when signup
    else:
        submitted_data['contact_number'] = data['phone']

        submitted_data['first_name'] = data['name'][0].upper() + data['name'][1:]
        # submitted_data['last_name'] = data['LastName'][0].upper() + data['LastName'][1:]
        role = data['occupation']
        role_list = ['Farmer']
        '''
        if role != 'Farmer':
            role_list.append(role)
        '''
        user_roles = OrganizationRole.objects.filter(role__in=role_list)
        # submitted_data['role'] = Role.id

        submitted_data['password'] = password
        submitted_data['password_repeat'] = password
        submitted_data['organisation_name'] = 397

        #
        # if data['IsAdmin']:
        #     submitted_data['admin'] = True
        # else:
        #     submitted_data['admin'] = False
        # submitted_data['password'] = data['Password']
        # if 'Email' in data:
        #     submitted_data['email'] = data['Email']
        #     print data['Email']
        # if 'EmployeeId' in data:
        #     submitted_data['employee_id'] = data['EmployeeId']
        # if 'Position' in data:
        #     submitted_data['position'] = data['Position']
        # if data['IsUpdate']:
        #     user_update = True
        # else:
        #     user_update = False
        # user_form = UserForm(username=data['UserName'], email=data['Email'], password=data['Password'], password_repeat=data['Password'])

        user_form = UserForm(data=submitted_data)
        profile_form = UserProfileForm(data=submitted_data)
        userRole_flag = 0

        user_form = UserForm(data=submitted_data)
        profile_form = UserProfileForm(data=submitted_data)

        if user_form.is_valid() and profile_form.is_valid():

            user = user_form.save()
            form_bool_value = False

            encrypted_password = make_password(user.password)
            user.password = encrypted_password
            user.save()

            profile = profile_form.save(commit=False)

            profile.user = user

            expiry_months_delta = 3

            # next_expiry_date = (datetime.today() + timedelta(expiry_months_delta * 365 / 12))
            next_expiry_date = (datetime.today() + timedelta(minutes=5))

            profile.expired = next_expiry_date
            profile.admin = form_bool_value

            profile.save()
            # kobo main/models/UserProfile
            if userRole_flag == 0:
                main_user_profile = UserProfile(user=user)
                main_user_profile.save()

            registered = True

            passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()
            submitted_data['user'] = profile.id

            for role in user_roles:
                UserRoleMap(user=profile, role=role).save()
            # insert into farmer
            auth_user_id = user.id
            user_profile_id = profile.id
            farmer_name = data['name'][0].upper() + data['name'][1:]
            mobile = data['phone']
            #if data['occupation'] == 'Farmer':
            insert_q = "INSERT INTO public.farmer(id, farmer_name, mobile,submission_time,submitted_by)VALUES (DEFAULT, '" + farmer_name + "','" + mobile + "', NOW()," + str(
                auth_user_id) + ") returning id;"
            ##print insert_q
            f_id = views.__db_commit_query(insert_q)
            insert_q = "INSERT INTO public.user_farmer_map(id, user_id, farmer_id)VALUES (DEFAULT, " + str(
                user_profile_id) + ", " + str(f_id) + ");"
            views.__db_commit_query(insert_q)
            if data['occupation'] != 'Farmer':
                approval_q = "INSERT INTO public.approval_queue(id,name, mobile, role_name, status, submitted_by, submission_time)VALUES (DEFAULT, '"+farmer_name+"','"+mobile+"', '"+data['occupation']+"', 0, "+str(auth_user_id)+", NOW());"
                #print approval_q
                views.__db_commit_query(approval_q)

                ## Sending notification mail ----------- (Start) // we have imported (from django.core.mail import send_mail)

            # loggeusername = request.user.username
            # currentOwner = get_object_or_404(User, username__iexact=loggeusername)
            # sendermail = currentOwner.email
            receivermail = data['phone']

            send_mail(
                'User LogIn One Time Password',
                'Hi,\n\nWelcome to Shurokkha!!\n\nPlease use this Password given below  to access The shurokkha App.\n\n Password :' + password + '\n\n',
                'mpowersocial2018@gmail.com',
                ['mpowersocialent@gmail.com'],
                fail_silently=False
            )

            return HttpResponse(json.dumps({'password': password}), status=200)

        else:

            err = user_form.errors.as_text() + profile_form.errors.as_text()
            print err

            return HttpResponse(err, status=409)

    receivermail = data['phone']

    send_mail(
        'User LogIn One Time Password',
        'Hi,\n\nWelcome to Shurokkha!!\n\nPlease use this Password given below  to access The shurokkha App.\n\n Password :' + password + '\n\n',
        'mpowersocial2018@gmail.com',
        ['mpowersocialent@gmail.com'],
        fail_silently=False
    )
    return HttpResponse(json.dumps({'password': password}), status=200)


@csrf_exempt
def get_farmer_list(request):
    username = request.GET.get('username')
    q = "select *,(select count(*) from cattle where mobile = farmer.mobile) as no_cattle,string_to_array(gps,' ') gps_list,date(submission_time)::text as s_date from farmer where id in(with t1 as ((select id from farmer where submitted_by = (select id from auth_user where username='" + username + "')) union (select id from farmer where mobile = '" + username + "') union(select farmer_id from user_farmer_map where user_id = (select id from usermodule_usermoduleprofile where user_id = (select id from auth_user where username = '"+username+"')) ) )select * from t1) and deleted_at is null"
    dataset = views. __db_fetch_values_dict(q)
    data_list = []
    farmerprofileupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    farmerprofileupdate_form_owner = views.__db_fetch_single_value(farmerprofileupdate_form_owner_q)
    for temp in dataset:
        data_dict = {}
        data_dict['id'] = temp['id']
        data_dict['name'] = temp['farmer_name']
        data_dict['phone'] = temp['mobile']
        data_dict['no_of_cattle'] = temp['no_cattle']
        data_dict['division'] = temp['division']
        data_dict['district'] = temp['district']
        data_dict['upzilla'] = temp['upazila']
        data_dict['union'] = ''
        data_dict['village'] = ''
        if temp['gps_list']:
            gps = str(temp['gps_list'][0])+","+str(temp['gps_list'][1])
        else:
            gps = ""
        data_dict['gps'] = gps
        data_dict['submission_date'] = temp['s_date']
        img_path = None
        if temp['image'] is not None:
            img = temp['image']
            img_path = "media/" + farmerprofileupdate_form_owner + "/attachments/" + img
        data_dict['image_url'] = img_path
        data_list.append(data_dict.copy())
        data_dict.clear()
    return HttpResponse(json.dumps(data_list))



@csrf_exempt
def get_cattle_list(request):
    farmer_id = request.GET.get('farmer_id')
    q = " select *,date(created_date)::text as register_date ,(select label from vwcattle_type where value =cattle_type ) cattle_type_text,(select label from vwcattle_origin where value =cattle_origin ) cattle_origin_text from cattle where mobile like '"+farmer_id+"'"
    dataset = views.__db_fetch_values_dict(q)
    cattle_regi_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'cattle_registration'"
    cattle_regi_form_owner = views.__db_fetch_single_value(cattle_regi_form_owner_q)
    data_list = []
    for temp in dataset:
        data_dict = {}
        data_dict['id'] = temp['cattle_id']
        data_dict['name'] = temp['cattle_name']
        data_dict['farmer_phone'] = temp['mobile']
        data_dict['calf_age'] = temp['calf_age']
        data_dict['cattle_age'] = temp['cattle_age']
        data_dict['register_date'] = temp['register_date']
        data_dict['cattle_birth_date'] = temp['cattle_birth_date']
        data_dict['weight'] = temp['calf_birth_weight']
        data_dict['cattle_type'] = temp['cattle_type_text']
        data_dict['cattle_system_id'] = temp['cattle_system_id']
        img_path = None
        if temp['picture'] is not None:
            img = temp['picture']
            img_path = "media/" + cattle_regi_form_owner + "/attachments/" + img
        data_dict['image_url'] = img_path

        data_list.append(data_dict.copy())
        data_dict.clear()
    return HttpResponse(json.dumps(data_list))



@csrf_exempt
def delete_farmer(request):
    username = request.GET.get('username')
    user_id = views.__db_fetch_single_value("select id from auth_user where username = '" + username + "'")
    deleted_farmers = request.body
    deleted_farmer_list = json.loads(deleted_farmers)
    for temp in deleted_farmer_list:
        #farmer cannot be deleted by his/her own
        if username == temp:
            continue
        q = "update  farmer set deleted_at = NOW(),deleted_by = "+str(user_id)+"  where mobile='"+str(temp)+"'"
        views.__db_commit_query(q)
    return HttpResponse(json.dumps('Deleted successfully.'))



@csrf_exempt
def search_farmer(request):
    farmerprofileupdate_form_owner_q = "select (select username from auth_user where id = logger_xform.user_id limit 1) as user_name from public.logger_xform where id_string = 'farmer_profile_update'"
    farmerprofileupdate_form_owner = views.__db_fetch_single_value(farmerprofileupdate_form_owner_q)
    username = request.GET.get('username')
    farmer_id = request.GET.get('farmer_id')
    q = "select *,(select count(*) from cattle where mobile = farmer.mobile) as no_cattle,string_to_array(gps,' ') gps_list,date(submission_time)::text as s_date from farmer where mobile = '"+farmer_id+"' "
    dataset = views.__db_fetch_values_dict(q)
    msg = ""
    data_list = []
    if dataset:
        user_id = views.__db_fetch_single_value("select id from usermodule_usermoduleprofile where user_id = (select id from auth_user where username = '"+username+"')")
        farmer_id = views.__db_fetch_single_value("select id from farmer where mobile = '"+farmer_id+"'")
        duplicate_check_q = "select id from user_farmer_map where user_id = "+str(user_id)+" and farmer_id = "+str(farmer_id)
        data = views.__db_fetch_values_dict(duplicate_check_q)

        if data:
            msg = "Already assigned"
        else:
            insert_q = "INSERT INTO public.user_farmer_map(id, user_id, farmer_id)VALUES (DEFAULT, " + str(
                user_id) + ", " + str(farmer_id) + ");"
            views.__db_commit_query(insert_q)
            msg = "Assigned successfully"
        for temp in dataset:
            data_dict = {}
            data_dict['id'] = temp['id']
            data_dict['name'] = temp['farmer_name']
            data_dict['phone'] = temp['mobile']
            data_dict['no_of_cattle'] = temp['no_cattle']
            data_dict['division'] = temp['division']
            data_dict['district'] = temp['district']
            data_dict['upzilla'] = temp['upazila']
            data_dict['union'] = ''
            data_dict['village'] = ''
            if temp['gps_list']:
                gps = str(temp['gps_list'][0]) + "," + str(temp['gps_list'][1])
            else:
                gps = ""
            data_dict['gps'] = gps
            data_dict['submission_date'] = temp['s_date']
            img_path = None
            if temp['image'] is not None:
                img = temp['image']
                img_path = "media/" + farmerprofileupdate_form_owner + "/attachments/" + img
            data_dict['image_url'] = img_path
            data_list.append(data_dict.copy())
            data_dict.clear()
    else:
        msg = "No farmer exists."
    print(msg)
    return HttpResponse(json.dumps(data_list))


def decimal_date_default(obj):
    if isinstance(obj, decimal.Decimal):
        return float(obj)
    elif hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        return obj
    raise TypeError

def dictfetchall(cursor):
    desc = cursor.description
    return [
        OrderedDict(zip([col[0] for col in desc], row))
        for row in cursor.fetchall()]

def __db_fetch_values_dict(query):
    cursor = connection.cursor()
    cursor.execute(query)
    fetchVal = dictfetchall(cursor)
    cursor.close()
    return fetchVal

def cattle_info(request):
    data = []
    if len(request.GET):
        username = request.GET.get('username')
        query = "with health_records as( select * from get_health_records_mobile_report('"+str(username)+"'))select cattle_id,'Feeding Information' as title, string_agg(question || ': '|| val || '\n',' ') as content from health_records where question::text = any('{দৈনিক খাওয়ানো সবুজ ঘাসের পরিমান(কেজি),দৈনিক খাওয়ানো শুকনো খড়ের পরিমান (কেজি),দৈনিক খাওয়ানো দানাদার খাদ্যের পরিমান (কেজি),দানাদার খাদ্যের উপকরণ কি কি?,ভুষির পরিমাণ (কেজি),চালের কুঁড়ার পরিমাণ (কেজি),ভুট্টা ভাঙ্গা / আটার পরিমাণ (কেজি),খৈলের পরিমাণ (কেজি),লবণের পরিমাণ (গ্রাম),লালি/চিটাগুড়ের পরিমাণ (কেজি)}') group by cattle_id union all select cattle_id,'Milk Feeding' as title,string_agg(question || ': '|| val || '\n',' ') as content from health_records where question::text = any('{গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,কত দিন যাবৎ দুধ দোহন করা বন্ধ আছে?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') group by cattle_id union all select cattle_id,'Deworming & Vaccination' as title,string_agg(question || ': '|| val || '\n',' ') as content from health_records where question::text = any('{গরুটিকে ক্রিমিমুক্তকরন করা হয়েছে?,কত মাস পূর্বে কৃমিমুক্তকরন করেছিলেন? (সঠিক জানা না থাকলে আনুমানিক),সর্বশেষ ভিজিটের পর থেকে আজ পর্যন্ত এই গরুর জন্য নিম্নের কোন কোন কাজ করা হয়েছে?(তবে এটি প্রথম ভিজিট হলে, গরুটির এযাবৎ কালের সকল কাজের তথ্য দিন),কত মাস পূর্বে তড়কা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে গলাফুলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে ক্ষুরা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক),কত দিন পূর্বে বাদলা টীকা দিয়েছিলেন? (সঠিক জানা না থাকলে আনুমানিক)}') group by cattle_id union all select cattle_id,'Sickness' as title,string_agg(question || ': '|| val || '\n',' ') as content from get_sickness_mobile_report('"+str(username)+"') where question::text = any('{তাপমাত্রা (ফারেনহাইট),পুর্ববর্তী মোট বাছুরের সংখ্যা,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,গরুটির বর্তমান প্রজনন অবস্থা?,আপনার গরুকে প্রজনন করানো হয়েছে?,প্রজননের ধরন?,প্রজননের তারিখ?,গর্ভবস্থার কোন পর্যায়ে আছে?,গরুটির বর্তমান দুধ উৎপাদন অবস্থা?,গতকাল উৎপাদিত দুধের পরিমান ? (লিটার)}') group by cattle_id union all select cattle_id,'Reproduction' as title,string_agg(question || ': '|| val || '\n',' ') as content from get_reproduction_records_mobile_report('"+str(username)+"') where question::text = any('{প্রজননের তারিখ?,এই প্রজননটির পুর্বে গরুটিকে পরপর কত বার ব্যর্থ কৃত্রিম প্রজনন করা হয়েছে?,কৃত্রিম প্রজননে ব্যবহৃত বীজ-এর ধরণ?,অন্যান্য হলে, লিখুন,ষাঁড় -এর নাম্বার,ষাঁড় -এর বিদেশি জাতের %,বর্তমানে প্রজনন সংক্রান্ত কি সমস্যা আছে?,গরুটির বর্তমান গর্ভবস্থা,গর্ভ পরীক্ষা করিয়েছিলেন?,গর্ভ পরীক্ষার তারিখ,গর্ভের বয়স (মাস),পুর্ববর্তী মোট বাছুরের সংখ্যা,বাছুর প্রসবের তারিখ,কত মাস পূর্বে সর্বশেষ বাছুর প্রসব করেছিল?,বাছুরের লিঙ্গ,বাছুরের জন্মকালীন ওজন(কে.জি.),গাভীর কি গর্ভকালীন, বাছুর প্রসব কালীন ও পরবর্তী কি জটিলতা হয়েছিল?,অন্যান্য হলে, লিখুন}') group by cattle_id"
        data = json.dumps(__db_fetch_values_dict(query), default=decimal_date_default)
    return HttpResponse(data)
