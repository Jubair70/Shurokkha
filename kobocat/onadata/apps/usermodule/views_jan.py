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

import xlwt
# from django.utils import simplejson
import json
import logging
import sys
import operator
from django.core.urlresolvers import reverse
import csv

import os
from django.conf import settings

import simplejson as sjson

# Create your views here.
from django.db import (IntegrityError,transaction)
from django.db.models import ProtectedError
from django.shortcuts import redirect
from onadata.apps.main.models.user_profile import UserProfile
from onadata.apps.usermodule.forms import UserForm, UserProfileForm, ChangePasswordForm, UserEditForm,OrganizationForm,OrganizationDataAccessForm,ResetPasswordForm
from onadata.apps.usermodule.models import UserModuleProfile, UserPasswordHistory, UserFailedLogin,Organizations,OrganizationDataAccess,ProfileOrganization, UserRoleMap, OrganizationRole


from django.contrib.auth.decorators import login_required, user_passes_test
from django import forms
# Menu imports
from onadata.apps.usermodule.forms import MenuForm
from onadata.apps.usermodule.models import MenuItem
# Unicef Imports
from onadata.apps.logger.models import Instance,XForm
# Organization Roles Import
from onadata.apps.usermodule.models import OrganizationRole,MenuRoleMap,UserRoleMap
from django.contrib.auth.models import User
from onadata.apps.usermodule.forms import OrganizationRoleForm,RoleMenuMapForm,UserRoleMapForm,UserRoleMapfForm
from django.forms.models import inlineformset_factory,modelformset_factory
from django.forms.formsets import formset_factory

from django.core.exceptions import ObjectDoesNotExist
from django.views.decorators.csrf import csrf_exempt
from django.db import connection
import pandas
from django.shortcuts import render
from collections import OrderedDict
from django.core.files.storage import FileSystemStorage


from pymongo import Connection as mongoconnection



#decorator based library

from django.utils.decorators import available_attrs

from functools import wraps


from onadata.apps.main.decorator import custom_user_passes_test


def role_check(request):
    # getting url
    path = request.get_full_path()
    print path
    #user object
    user = request.user
    #user profile object
    current_user = UserModuleProfile.objects.filter(user=user)
    #user role object
    user_role_map = UserRoleMap.objects.filter(user=current_user)
    user_roles = [roles.role for roles in user_role_map]
    menu_list = []
    url_found = False
    # checking if the url in the role wise menu list
    for role in user_roles:
        all_menu = MenuRoleMap.objects.filter(role = role)
        menu_list = [ menu.menu for menu in all_menu]
        for menu in menu_list:
            if menu.url == path:
                print "user access permitted"
                return True

    return False


''' CUSTOM DECORATOR FUNCTION '''

def admin_check(user):
    current_user = UserModuleProfile.objects.filter(user=user)
    if current_user:
        current_user = current_user[0]
    else:
        return True    
    return current_user.admin

#change by ZINIA
@login_required
#@user_passes_test(admin_check,login_url='/')
def index(request):
    current_user = request.user
    user = UserModuleProfile.objects.filter(user_id=current_user.id)
    profile_org = {
    }
    admin = False
    if user:
        admin = user[0].admin
    if current_user.is_superuser:
        admin = True
        profile_organization = ProfileOrganization.objects.all()
        profile_list = [pro.profile_id for pro in profile_organization]
        users = UserModuleProfile.objects.filter(id__in=profile_list).order_by("user__username")
        for pro in profile_organization:
            if str(pro.profile_id) not in profile_org:
                profile_org[str(pro.profile_id)] = []
                profile_org[str(pro.profile_id)].append(pro.organization.organization)
            else:
                profile_org[str(pro.profile_id)].append(pro.organization.organization)
    else:
        org_id_list = get_organization_by_user(request.user)
        #change by zinia
        #getting profile organization mapping list
        profile_organization = ProfileOrganization.objects.filter(organization_id__in=org_id_list)
        profile_list = [pro.profile_id  for pro in profile_organization]
        users = UserModuleProfile.objects.filter(id__in=profile_list).order_by("user__username")
        # profile organization mapping
        admin = True
        for pro in profile_organization:
            if str(pro.profile_id) not in profile_org:
                profile_org[str(pro.profile_id)] = []
                profile_org[str(pro.profile_id)].append(pro.organization.organization)
            else:
                profile_org[str(pro.profile_id)].append(pro.organization.organization)
    # else:
    #     users = user
    #     admin = False

    template = loader.get_template('usermodule/index.html')
    context = RequestContext(request, {
            'users': users,
            'admin': admin,
             #change
            'profiles':profile_org,
            # 'json_posts' : json_posts
        })
    return HttpResponse(template.render(context))

@login_required
@user_passes_test(admin_check,login_url='/')
def register(request):
    # Like before, get the request's context.
    context = RequestContext(request)
    admin_check = UserModuleProfile.objects.filter(user=request.user)

    if request.user.is_superuser:
        admin_check = True
    elif admin_check:
        admin_check = admin_check[0].admin
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False
    
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST,admin_check=admin_check)

        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()
            
            form_bool = request.POST.get("admin", "xxx")
            if form_bool == "xxx":
                form_bool_value = False
            else:
                form_bool_value = True
            
            #encrypted password is saved so that it can be saved in password history table
            encrypted_password = make_password(user.password)
            user.password = encrypted_password
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            # profile.organisation_name = request.POST.get("organisation_name", "-1")
            profile.user = user
            expiry_months_delta = 3
            # Date representing the next expiry date
            next_expiry_date = (datetime.today() + timedelta(expiry_months_delta*365/12))
            profile.expired = next_expiry_date
            profile.admin = form_bool_value
            # Did the user provide a profile picture?
            # If so, we need to get it from the input form and put it in the UserProfile model.
            # if 'picture' in request.FILES:
            #     profile.picture = request.FILES['picture']

            # Now we save the UserProfile model instance.
            profile.save()

            # kobo main/models/UserProfile
            main_user_profile = UserProfile(user = user)
            main_user_profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

            #insert password into password history
            passwordHistory = UserPasswordHistory(user_id = user.id,date = datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()
            messages.success(request, '<i class="fa fa-check-circle"></i> New User has been registered successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/')

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors, profile_form.errors
            # profile_form = UserProfileForm(admin_check=admin_check)

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        # get request users org and the orgs he can see then pass it to model choice field
        org_id_list = get_organization_by_user(request.user)
        # org id list is not available for superuser's like kobo
        if not org_id_list:
            UserProfileForm.base_fields['organisation_name'] = forms.ModelChoiceField(queryset=Organizations.objects.all(),empty_label="Select a Organization")
        else:
            UserProfileForm.base_fields['organisation_name'] = forms.ModelChoiceField(queryset=Organizations.objects.filter(pk__in=org_id_list)
,empty_label="Select a Organization")
        profile_form = UserProfileForm(admin_check=admin_check)

    # Render the template depending on the context.
    return render_to_response(
            'usermodule/register.html',
            {'user_form': user_form, 'profile_form': profile_form, 'registered': registered},
            context)


def get_organization_by_user(user):
    # CHANGE BY ZINIA
    org_id_list = []
    profile = UserModuleProfile.objects.filter(user_id=user.id).first()
    organizations = ProfileOrganization.objects.filter(profile_id=profile.id)

    if organizations:
        for org in organizations:
            all_organizations = get_recursive_organization_children(org.organization,[])
            for org in all_organizations:
                org_id_list.append(org.id)

            print org_id_list
    return org_id_list


# must pass an empty organization_list initally otherwise produces bug.
def get_recursive_organization_children(organization,organization_list=[]):
    organization_list.append(organization)
    observables = Organizations.objects.filter(parent_organization = organization)
    for org in observables:
        if org not in organization_list:
            organization_list = list((set(get_recursive_organization_children(org,organization_list))))
    return list(set(organization_list))


@login_required
@user_passes_test(admin_check,login_url='/')
def organization_index(request):
    context = RequestContext(request)
    all_organizations = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name,[])
        all_organizations.remove(current_user.organisation_name)
    message = ""
    alert = ""
    org_del_message = request.GET.get('org_del_message')
    org_del_message2 = request.GET.get('org_del_message2')
    return render_to_response(
            'usermodule/organization_list.html',
            {'all_organizations':all_organizations,"message":message,"alert":alert,
            'org_del_message':org_del_message,'org_del_message2':org_del_message2,
            },
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def add_organization(request):
    # Like before, get the request's context.
    context = RequestContext(request)
    all_organizations = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(queryset=all_organizations,empty_label="Select a Organization",required=False)
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
     
        #all_organizations = get_recursive_organization_children(current_user.organisation_name,[])
        #org_id_list = [org.pk for org in all_organizations]
        # org_id_list = list(set(org_id_list))
        all_organizations = Organizations.objects.filter(organization='BRAC')
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(queryset=all_organizations ,empty_label="Select a Parent Organization")
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    is_added_organization = False
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        organization_form = OrganizationForm(data=request.POST)
        if organization_form.is_valid():
            organization_form.save()
            is_added_organization = True
            messages.success(request, '<i class="fa fa-check-circle"></i> New Organization has been added successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/organizations/')
        else:
            print organization_form.errors
            return render_to_response(
            'usermodule/add_organization.html',
            {'all_organizations':all_organizations,'organization_form': organization_form,'is_added_organization': is_added_organization},
            context)
    else:
        organization_form =  OrganizationForm()
    # Render the template depending on the context.
        return render_to_response(
            'usermodule/add_organization.html',
            {'all_organizations':all_organizations,'organization_form': organization_form,'is_added_organization': is_added_organization},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def edit_organization(request,org_id):
    context = RequestContext(request)
    edited = False
    organization = get_object_or_404(Organizations, id=org_id)
    all_organizations = []
    if request.user.is_superuser:
        all_organizations = Organizations.objects.filter(~Q(id = organization.pk))
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(queryset=all_organizations,empty_label="Select a Organization",required=False)
    else:
        current_user = UserModuleProfile.objects.filter(user_id=request.user.id)
        if current_user:
            current_user = current_user[0]
        all_organizations = get_recursive_organization_children(current_user.organisation_name,[])
        org_id_list = [org.pk for org in all_organizations]
        org_id_list.remove(organization.pk)
        OrganizationForm.base_fields['parent_organization'] = forms.ModelChoiceField(queryset=Organizations.objects.filter(pk__in=org_id_list),empty_label="Select a Parent Organization")
    
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        organization_form = OrganizationForm(data=request.POST,instance=organization)
        if organization_form.is_valid():
            organization_form.save()
            edited = True
            messages.success(request,
                             '<i class="fa fa-check-circle"></i> Organization has been updated successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/organizations/')
        else:
            print organization_form.errors
            return render_to_response(
            'usermodule/edit_organization.html',
            {'org_id':org_id,'organization_form': organization_form, 'edited': edited},
            context)
        # Not a HTTP POST, so we render our form using two ModelForm instances.
        # These forms will be blank, ready for user input.
    else:
        organization_form = OrganizationForm(instance=organization)
    return render_to_response(
            'usermodule/edit_organization.html',
            {'org_id':org_id,'organization_form': organization_form, 'edited': edited},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def delete_organization(request,org_id):
    context = RequestContext(request)
    org = Organizations.objects.get(pk = org_id)
    try:
        org.delete()
        messages.success(request,
                         '<i class="fa fa-check-circle"></i> Organization has been deleted successfully!',
                         extra_tags='alert-success crop-both-side')
    except ProtectedError:
        org_del_message = """User(s) are assigned to this organization,
        please delete those users or assign them a different organization
        before deleting this organization"""

        org_del_message2 = """Or, This Organization may be parent of 
        one or more organization(s), Change their parent to some other organization."""
        
        return HttpResponseRedirect('/usermodule/organizations/?org_del_message='+org_del_message+"&org_del_message2="+org_del_message2)
    return HttpResponseRedirect('/usermodule/organizations/')


# @login_required
# @user_passes_test(lambda u: u.is_superuser,login_url='/')
# def organization_mapping(request):
#     # Like before, get the request's context.
#     context = RequestContext(request)
#     mapped_organizations = OrganizationDataAccess.objects.all()
#     all_organizations = Organizations.objects.all()
#     has_added_mapping = False

#     # If it's a HTTP POST, we're interested in processing form data.
#     if request.method == 'POST':
#         organization_data_access_form = OrganizationDataAccessForm(data=request.POST)
#         # If the two forms are valid...
#         if organization_data_access_form.is_valid():
#             try:
#                 organization_access_map = organization_data_access_form.save();
#                 organization_access_map.observer_oraganization = request.POST.get("observer_oraganization", "-1")
#                 organization_access_map.observable_oraganization = request.POST.get("observable_oraganization", "-1")
#                 organization_access_map.save()
#                 has_added_mapping = True
#             except IntegrityError as e:
#                 transaction.rollback()
#                 message = "That entry already exists"                
#                 return render_to_response(
#             'usermodule/add_organization_access.html',
#             {'mapped_organizations':mapped_organizations,'all_organizations':all_organizations,"message":message,
#             'organization_data_access_form': organization_data_access_form,'has_added_mapping': has_added_mapping},
#             context)
#         else:
#             print organization_data_access_form.errors
#     # Not a HTTP POST, so we render our form using two ModelForm instances.
#     # These forms will be blank, ready for user input.
#     else:
#         organization_data_access_form =  OrganizationDataAccessForm()
    
#     # Render the template depending on the context.
#     return render_to_response(
#             'usermodule/add_organization_access.html',
#             {'mapped_organizations':mapped_organizations,'all_organizations':all_organizations,'organization_data_access_form': organization_data_access_form,'has_added_mapping': has_added_mapping},
#             context)


@login_required
@user_passes_test(admin_check,login_url='/')
def organization_access_list(request):
    param_user_id = request.POST['id']
    response_data = []
    observer = get_object_or_404(Organizations, id=param_user_id)
    all_organizations = get_recursive_organization_children(observer,[])
    for org in all_organizations:
        data = {}
        data["observer"] = observer.organization
        data["observable"] = org.organization
        response_data.append(data)
    return HttpResponse(json.dumps(response_data), content_type="application/json")

 
# @login_required
# @user_passes_test(admin_check,login_url='/')
# def delete_organization_mapping(request,org_id):
#     mappings = OrganizationDataAccess.objects.filter(id = org_id)
#     mappings.delete()
#     return HttpResponseRedirect('/usermodule/organizations/')


# def get_organization_name(organizations,id):
#     for arra in organizations:
#         if int(arra.id) == int(id):
#             return arra.oraganization
#     return None


#changed by zinia
@login_required
def edit_profile(request,user_id):
	context = RequestContext(request)
	edited = False
	user = get_object_or_404(User, id=user_id)
	profile = get_object_or_404(UserModuleProfile, user_id=user_id)

        # organization list


        org_id_list = get_organization_by_user(user)

        if not org_id_list:
            organization_list = Organizations.objects.all()
        else:
            organization_list = Organizations.objects.filter(pk__in=org_id_list)

        print "########################"
        print organization_list
        admin_check = UserModuleProfile.objects.filter(user=request.user)
        if request.user.is_superuser:
            admin_check = True
        elif admin_check:
            admin_check = admin_check[0].admin
        # If it's a HTTP POST, we're interested in processing form data.
        if request.method == 'POST':
            # Attempt to grab information from the raw form information.
            # Note that we make use of both UserForm and UserProfileForm.
            user_form = UserEditForm(data=request.POST,instance=user,user=request.user)
            profile_form = UserProfileForm(data=request.POST,instance=profile,admin_check=admin_check)
            # If the two forms are valid...
            if user_form.is_valid() and profile_form.is_valid():
                edited_user = user_form.save(commit=False);
                # password_new = request.POST['password']
                # if password_new:
                #     edited_user.set_password(password_new)
                edited_user.save()
                form_bool = request.POST.get("admin", "xxx")
                if form_bool == "xxx":
                    form_bool_value = False
                else:
                    form_bool_value = True
                # Now sort out the UserProfile instance.
                # Since we need to set the user attribute ourselves, we set commit=False.
                # This delays saving the model until we're ready to avoid integrity problems.
                profile = profile_form.save(commit=False)
                # profile.organisation_name = request.POST.get("organisation_name", "-1")
                # profile.admin = request.POST.get("admin", "False")
                profile.user = edited_user
                profile.admin = form_bool_value
                # Did the user provide a profile picture?
                # If so, we need to get it from the input form and put it in the UserProfile model.
                # if 'picture' in request.FILES:
                #     profile.picture = request.FILES['picture']

                # Now we save the UserProfile model instance.
                profile.save()

                # change profile organization mapping in profileorganization table
                organization = request.POST.getlist('organization_name')
                print "################## organization"
                print organization
                for org in organization:
                    profile_organization = ProfileOrganization.objects.filter(profile_id=profile.id, organization_id=int(org)).first()
                    if profile_organization is None:
                        profile_org = ProfileOrganization(profile_id=profile.id,organization_id=int(org))
                        profile_org.save()

                #for changing previous data which is not selected now
                profile_organizations = ProfileOrganization.objects.filter(profile_id=profile.id)
                for pro in profile_organizations:
                    if str(pro.organization_id) not in organization:
                        print pro.organization_id
                        pro.delete()

                # Update our variable to tell the template registration was successful.
                edited = True
                messages.success(request, '<i class="fa fa-check-circle"></i> User profile has been updated successfully!', extra_tags='alert-success crop-both-side')
                return HttpResponseRedirect('/usermodule/')

            # Invalid form or forms - mistakes or something else?
            # Print problems to the terminal.
            # They'll also be shown to the user.
            else:
                # profile_form = UserProfileForm(admin_check=admin_check)
                print user_form.errors, profile_form.errors

        # Not a HTTP POST, so we render our form using two ModelForm instances.
        # These forms will be blank, ready for user input.
        else:
            user_form = UserEditForm(instance=user,user=user)


            profile_form = UserProfileForm(instance = profile,admin_check=admin_check)
            profile_organization = ProfileOrganization.objects.filter(profile_id=profile.id)

        return render_to_response(
                'usermodule/edit_user.html',
                {'id':user_id, 'profile':profile,'user_form': user_form, 'profile_form': profile_form, 'edited': edited, 'organization_list':organization_list, 'profile_organization':profile_organization},
                context)





@login_required
@user_passes_test(admin_check,login_url='/')
def delete_user(request,user_id):
    context = RequestContext(request)
    user = User.objects.get(pk = user_id)
    # deletes the user from both user and rango
    user.delete()
    messages.success(request, '<i class="fa fa-check-circle"></i> This user has been deleted successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponseRedirect('/usermodule/')


def change_password(request):
    context = RequestContext(request)
    if request.GET.get('userid'):
        edit_user = get_object_or_404(User, pk = request.GET.get('userid')) 
        logged_in_user = edit_user.username
        change_password_form = ChangePasswordForm(logged_in_user=logged_in_user)
    else:
        change_password_form = ChangePasswordForm()
    # change_password_form = ChangePasswordForm()
    # Take the user back to the homepage.
    if request.method == 'POST':
        # expiry_months_delta: password change after how many months
        expiry_months_delta = 3
        # Date representing the next expiry date
        next_expiry_date = (datetime.today() + timedelta(expiry_months_delta*365/12))

        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        change_password_form = ChangePasswordForm(data=request.POST)
        username = request.POST['username']
        old_password = request.POST['old_password']
        new_password = request.POST['new_password']
        current_user = authenticate(username=username, password=old_password)
        if change_password_form.is_valid() and current_user is not None:
            """ current user is authenticated and also new password
             is available so change the password and redirect to
             home page with notification to user """
            encrypted_password = make_password(new_password)
            current_user.password = encrypted_password
            current_user.save()

            passwordHistory = UserPasswordHistory(user_id = current_user.id,date = datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            profile = get_object_or_404(UserModuleProfile, user_id=current_user.id)
            profile.expired = next_expiry_date
            profile.save()
            login(request,current_user)
            return HttpResponseRedirect('/usermodule/')
            # else:
                #     return HttpResponse('changed your own password buddy')
                # return HttpResponse( (datetime.now()+ timedelta(days=30)) )
        else:
            return render_to_response(
                    'usermodule/change_password.html',
                    {'change_password_form': change_password_form,'invalid':True},
                    context)

    return render_to_response(
                'usermodule/change_password.html',
                {'change_password_form': change_password_form},
                context)

@login_required
@user_passes_test(admin_check,login_url='/')
def reset_password(request,reset_user_id):
    context = RequestContext(request)
    reset_password_form = ResetPasswordForm()
    reset_user = get_object_or_404(User, pk=reset_user_id)
    reset_user_profile = get_object_or_404(UserModuleProfile,user=reset_user)
    if request.method == 'POST':
        # expiry_months_delta: password change after how many months
        expiry_months_delta = 3
        # Date representing the next expiry date
        next_expiry_date = (datetime.today() + timedelta(expiry_months_delta*365/12))

        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        reset_password_form = ResetPasswordForm(data=request.POST)
        
        if reset_password_form.is_valid() and reset_user is not None:
            """ current user is authenticated and also new password
             is available so change the password and redirect to
             home page with notification to user """
            encrypted_password = make_password(request.POST['new_password'])
            reset_user.password = encrypted_password
            reset_user.save()

            passwordHistory = UserPasswordHistory(user_id = reset_user.id,date = datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            reset_user_profile.expired = next_expiry_date
            reset_user_profile.save()
            messages.success(request, '<i class="fa fa-check-circle"></i> Your password has been updated successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/')
        else:
            return render_to_response(
                    'usermodule/reset_password.html',
                    {'reset_user':reset_user,'reset_password_form': reset_password_form,'invalid':True},
                    context)

    return render_to_response(
                'usermodule/reset_password.html',
                {'reset_password_form': reset_password_form,
                'reset_user':reset_user,'id':reset_user_id,
                },
                context)


def user_login(request):
    # Like before, obtain the context for the user's request.
    context = RequestContext(request)
    logger = logging.getLogger(__name__)
    # If the request is a HTTP POST, try to pull out the relevant information.
    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
        username = request.POST['username']
        password = request.POST['password']

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
                return HttpResponse("Your account is locked for multiple invalid logins, contact admin to unlock")

            # Is the account active? It could have been disabled.
            if user.is_active:
                if hasattr(user, 'usermoduleprofile'):
                    current_user = user.usermoduleprofile
                    if date.today() > current_user.expired.date():
                        return HttpResponseRedirect('/usermodule/change-password')
                login(request, user)
                UserFailedLogin.objects.filter(user_id=user.id).delete()
                return HttpResponseRedirect(request.POST['redirect_url'])
            else:
                # An inactive account was used - no logging in!
                # return HttpResponse("Your User account is disabled.")
                return error_page(request,"Your User account is disabled")
        else:
            # Bad login details were provided. So we c an't log the user in.
            # try:
            #     attempted_user_id = User.objects.get(username=username).pk
            # except User.DoesNotExist:
            #     return HttpResponse("Invalid login details supplied when login attempted.")
            # UserFailedLogin(user_id = attempted_user_id).save()
            # print "Invalid login details: {0}, {1}".format(username, password)
            # return HttpResponse("Invalid login details supplied.")
            return error_page(request,"Invalid login details supplied")

    # The request is not a HTTP POST, so display the login form.
    # This scenario would most likely be a HTTP GET.
    else:
        if request.GET.get('next'):
            print request.GET.get('next')
            redirect_url = request.GET.get('next')
        else:
            redirect_url = '/'
        # No context variables to pass to the template system, hence the
        # blank dictionary object...
        return render_to_response('usermodule/login.html', {'redirect_url':redirect_url}, context)


@login_required
@user_passes_test(admin_check,login_url='/')
def locked_users(request):
    # Since we know the user is logged in, we can now just log them out.
    current_user = request.user
    users = []
    message = ''
    max_failed_login_attempts = 5

    user = UserModuleProfile.objects.filter(user_id=current_user.id)
    admin = False
    if user:
        admin = user[0].admin

    if current_user.is_superuser or admin:
        failed_logins = UserFailedLogin.objects.all().values('user_id').annotate(total=Count('user_id')).order_by('user_id')
        for f_login in failed_logins:
            if f_login['total'] > max_failed_login_attempts:
                user = UserModuleProfile.objects.filter(user_id=f_login['user_id'])[0]
                users.append(user)
    else:
        return HttpResponseRedirect("/usermodule/")
    if not users:
        message = "All the user accounts are unlocked"

    # Take the user back to the homepage.
    template = loader.get_template('usermodule/locked_users.html')
    context = RequestContext(request, {
            'users': users,
            'message':message
        })
    return HttpResponse(template.render(context))


@csrf_exempt
def get_input_list(request,username):
    
    #username = request.GET.get('username', '')

    sql = "select json->>'info/hh_id', json->>'_xform_id_string', json->>'input_type', json->>'value_tk', json->>'date_input_distribution', json->>'input_type_other', (SELECT status FROM public.approval_instanceapproval where instance_id=logger_instance.id limit 1) status from logger_instance where xform_id=444 and user_id=(select id from auth_user where username='" + username + "') and deleted_at is null order by id"
    
    input_list = __db_fetch_values(sql)
    json_data_response_all = []
    if len(input_list) > 0:
        for input_item in input_list:
            json_data_response = {}
            json_data_response['hh_id'] = input_item[0]
            json_data_response['form_id'] = input_item[1]
            json_data_response['input_type'] = input_item[2]
            json_data_response['input_value'] = input_item[3]
            json_data_response['input_distribution_date'] = input_item[4]
            if input_item[5] is not None:
		json_data_response['input_name'] = input_item[5]
	    else:
		input_name_query = "select value_label from xform_extracted where xform_id = 444 and field_name = 'input_type' and value_text = '%s'" % (input_item[2])
                input_name_value = json.loads(row_query(input_name_query))
                json_data_response['input_name'] = input_name_value['Bangla']

            json_data_response['status'] = input_item[6]
            json_data_response_all.append(json_data_response)

    return HttpResponse(json.dumps(json_data_response_all))

@login_required
def unlock(request):
    param_user_id = request.POST['id']
    current_user = request.user
    response_data = {}
    
    user = UserModuleProfile.objects.filter(user_id=current_user.id)
    admin = False
    if user:
        admin = user[0].admin

    if current_user.is_superuser or admin:
        UserFailedLogin.objects.filter(user_id=param_user_id).delete()
        response_data['message'] = 'User unlocked'
    else:
        response_data['message'] = 'You are not authorized to unlock'

    return HttpResponse(json.dumps(response_data), content_type="application/json")


@login_required
def user_logout(request):
    # Since we know the user is logged in, we can now just log them out.
    logout(request)
    # Take the user back to the homepage.
    return HttpResponseRedirect('/login/')


# =======================================================================================
@login_required
@user_passes_test(admin_check,login_url='/')
def add_menu(request):
    context = RequestContext(request)
    all_menu = MenuItem.objects.all()
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    is_added_menu = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        menu_form = MenuForm(data=request.POST)
        # If the two forms are valid...
        if menu_form.is_valid():
            menu =menu_form.save()
            menu.save()
            is_added_menu = True
        else:
            print menu_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
        return HttpResponseRedirect('/usermodule/menu-list/')
    else:
        menu_form = MenuForm()
    
    # Render the template depending on the context.
        return render_to_response(
            'usermodule/add_menu.html',
            {'all_menu':all_menu,'menu_form': menu_form,
            'is_added_menu': is_added_menu},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def menu_index(request):
    context = RequestContext(request)
    all_menu = MenuItem.objects.all().order_by("sort_order")
    return render_to_response(
            'usermodule/menu_list.html',
            {'all_menu':all_menu},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def edit_menu(request,menu_id):
    context = RequestContext(request)
    edited = False
    menu = get_object_or_404(MenuItem, id=menu_id)
    
    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        menu_form = MenuForm(data=request.POST,instance=menu)
        
        # If the two forms are valid...
        if menu_form.is_valid():
            edited_user = menu_form.save(commit=False);
            edited_user.save()
            edited = True
            return HttpResponseRedirect('/usermodule/menu-list')
        else:
            print menu_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        menu_form = MenuForm(instance=menu)

    return render_to_response(
            'usermodule/edit_menu.html',
            {'id':menu_id, 'menu_form': menu_form,
            'edited': edited},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def delete_menu(request,menu_id):
    context = RequestContext(request)
    menu = MenuItem.objects.get(pk = menu_id)
    # deletes the user from both user and rango
    menu.delete()
    return HttpResponseRedirect('/usermodule/menu-list')


# =========================================================
# Roles based on Organization CRUD
@login_required
@user_passes_test(admin_check,login_url='/')
def add_role(request):
    context = RequestContext(request)
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    is_added_role = False

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        role_form = OrganizationRoleForm(data=request.POST)
        print role_form
        # If the two forms are valid...
        if role_form.is_valid():
            role_form.save()
            is_added_role = True
        else:
            print role_form.errors

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
        messages.success(request, '<i class="fa fa-check-circle"></i> New role has been added successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/usermodule/roles-list/')
    else:
        if request.user.is_superuser:
            OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.all(),empty_label="Select a Organization")
            role_form = OrganizationRoleForm()
        else:
            org_id_list = get_organization_by_user(request.user)

            #adding Generic option in the organization list
            generic_org = Organizations.objects.filter(organization = "Generic").first()
            org_id_list.append(generic_org.id)

            OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.filter(pk__in=org_id_list),empty_label="Select a Organization")
            role_form = OrganizationRoleForm()
    # Render the template depending on the context.
        return render_to_response(
            'usermodule/add_role.html',
            {'role_form': role_form,
            'is_added_role': is_added_role},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def roles_index(request):
    context = RequestContext(request)
    # filter orgs based on logged in user
    if request.user.is_superuser:
        all_roles = OrganizationRole.objects.all().order_by("organization")
    else:
        org_list = []

        # adding Generic option in the organization list
        generic_org = Organizations.objects.filter(organization="Generic").first()
        org_list.append(generic_org.id)

        user = get_object_or_404(UserModuleProfile, user=request.user)
        user_org = ProfileOrganization.objects.filter(profile_id=user.id)
        for org in user_org:
            org_qry="with recursive  cte as(select  id,COALESCE(parent_organization_id,id) parent_organization_id,organization,1 as level from usermodule_organizations where id = "+ str(org.organization_id) +" union all select  child.id,parent.parent_organization_id,child.organization,level + 1 from usermodule_organizations child join    cte parent on child.parent_organization_id = parent.id)select id from cte "

            cursor = connection.cursor()
            cursor.execute(org_qry)
            tmp_db_value = cursor.fetchall()


            if tmp_db_value is not None:
                for every in tmp_db_value:
                    org_list.append(every[0])

            cursor.close()
        all_roles = OrganizationRole.objects.filter(reduce(operator.or_, [Q(organization=c) for c in org_list]))
        #all_roles = OrganizationRole.objects.filter(organization = user.organisation_name)
    return render_to_response(
            'usermodule/roles_list.html',
            {'all_roles':all_roles},
            context)


@login_required
@user_passes_test(admin_check, login_url='/')
def edit_role(request, role_id):
    context = RequestContext(request)
    edited = False
    role = get_object_or_404(OrganizationRole, id=role_id)
    if request.method == 'POST':
        role_form = OrganizationRoleForm(data=request.POST,instance=role)
        if role_form.is_valid():
            role_form.save()
            edited = True
            messages.success(request, '<i class="fa fa-check-circle"></i> This role has been edited successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/roles-list')
        else:
            print role_form.errors
    else:
        if request.user.is_superuser:
            OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.all(),empty_label="Select a Organization")
            
        else:

            org_id_list = get_organization_by_user(request.user)

            # adding Generic option in the organization list
            generic_org = Organizations.objects.filter(organization="Generic").first()
            org_id_list.append(generic_org.id)

            OrganizationRoleForm.base_fields['organization'] = forms.ModelChoiceField(queryset=Organizations.objects.filter(pk__in=org_id_list),empty_label="Select a Organization")
        role_form = OrganizationRoleForm(instance=role,initial = {'organization': role.organization,'role': role.role })    
        # role_form = OrganizationRoleForm(instance=role)
    return render_to_response(
            'usermodule/edit_role.html',
            {'id':role_id, 'role_form': role_form,
            'edited': edited},
            context)


@login_required
@user_passes_test(admin_check,login_url='/')
def delete_role(request,role_id):
    context = RequestContext(request)
    role = OrganizationRole.objects.get(pk = role_id)
    # deletes the user from both user and rango
    role.delete()
    messages.success(request, '<i class="fa fa-check-circle"></i> This role has been deleted successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponseRedirect('/usermodule/roles-list')


# =========================================================

#change by ZINIA
@login_required
@user_passes_test(admin_check,login_url='/')
def role_menu_map_index(request):
    context = RequestContext(request)
    insertList = []
    menu_dict = {}
    # filter orgs based on logged in user
    if request.method == 'POST':
        new_menu = request.POST.getlist('menu_id')
        print new_menu
        for val in new_menu:
            splitVal = val.split("__")
            instance = MenuRoleMap(role_id=splitVal[0], menu_id=splitVal[1])
            insertList.append(instance)

        MenuRoleMap.objects.all().delete()
        MenuRoleMap.objects.bulk_create(insertList)
        messages.success(request, '<i class="fa fa-check-circle"></i> Access List has been updated successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/usermodule/role-menu-map-list/')
    else:
        if request.user.is_superuser:
            menu_items = MenuItem.objects.all()
            roles = OrganizationRole.objects.all()
            for role in roles:
                org_menu_list = MenuRoleMap.objects.filter(role=role.id).values_list('menu_id', flat=True)
                menu_dict[role.id] = org_menu_list
        else:
            user = request.user
            menu_items = MenuItem.objects.all()


            #organization list of tha user
            profile = UserModuleProfile.objects.filter(user_id = user.id).first()
            profile_org = ProfileOrganization.objects.filter(profile_id = profile.id)
            org_list = [pro.organization_id for pro in profile_org]

            # adding Generic option in the organization list
            generic_org = Organizations.objects.filter(organization="Generic").first()
            org_list.append(generic_org.id)
            roles = OrganizationRole.objects.filter(organization__in=org_list)





            # roles = OrganizationRole.objects.all()
            for role in roles:
                org_menu_list = MenuRoleMap.objects.filter(role = role.id).values_list('menu_id', flat=True)
                menu_dict[role.id] = org_menu_list

        return render_to_response(
            'usermodule/roles_menu_map_list.html',
            {'menu_items':menu_items, 'menu_dict':menu_dict,'roles':roles},
            context)


# Roles based on Organization CRUD
@login_required
@user_passes_test(admin_check,login_url='/')
def add_role_menu_map(request):
    context = RequestContext(request)
    is_added_role = False
    if request.method == 'POST':
        role_form = RoleMenuMapForm(data=request.POST)
        if role_form.is_valid():
            role_form.save()
            is_added_role = True
            messages.success(request, '<i class="fa fa-check-circle"></i> New access has been added successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/role-menu-map-list/')
        else:
            print role_form.errors
        return HttpResponseRedirect('/usermodule/role-menu-map-list/')
    else:
        if request.user.is_superuser:
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.all().order_by("organization"),empty_label="Select a Organization Role")
            
        else:
            org_id_list = get_organization_by_user(request.user)
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.filter(organization__in=org_id_list).order_by("organization"),empty_label="Select a Organization Role")
        role_form = RoleMenuMapForm()
        return render_to_response(
            'usermodule/add_role_menu_map.html',
            {'role_form': role_form,
            'is_added_role': is_added_role},
            context)


@login_required
@user_passes_test(admin_check, login_url='/')
def edit_role_menu_map(request, item_id):
    context = RequestContext(request)
    edited = False
    role_menu_map = get_object_or_404(MenuRoleMap, id=item_id)
    if request.method == 'POST':
        role_form = RoleMenuMapForm(data=request.POST,instance=role_menu_map)
        if role_form.is_valid():
            role_form.save()
            edited = True
            messages.success(request, '<i class="fa fa-check-circle"></i> This access has been edit successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/role-menu-map-list/')
        else:
            print role_form.errors
    else:
        if request.user.is_superuser:
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.all(),empty_label="Select a Organization Role")
        else:
            org_id_list = get_organization_by_user(request.user)
            RoleMenuMapForm.base_fields['role'] = forms.ModelChoiceField(queryset=OrganizationRole.objects.filter(organization__in=org_id_list),empty_label="Select a Organization Role")
        role_form = RoleMenuMapForm(instance=role_menu_map,initial = {'role': role_menu_map.role,'menu': role_menu_map.menu })
    return render_to_response(
            'usermodule/edit_role_menu_map.html',
            {'id':item_id, 'role_form': role_form,
            'edited': edited},
            context)


@login_required
@user_passes_test(admin_check, login_url='/')
def delete_role_menu_map(request, item_id):
    context = RequestContext(request)
    del_map_item = MenuRoleMap.objects.get(pk = item_id)
    del_map_item.delete()
    messages.success(request, '<i class="fa fa-check-circle"></i> This access has been deleted successfully!',
                     extra_tags='alert-success crop-both-side')
    return HttpResponseRedirect('/usermodule/role-menu-map-list')


# =========================================================
@login_required
@user_passes_test(admin_check, login_url='/')
def organization_roles(request):
    context = RequestContext(request)
    if request.user.is_superuser:
        all_organizations = Organizations.objects.all()
    else:    
        org_id_list = get_organization_by_user(request.user)
        all_organizations = Organizations.objects.filter(pk__in=org_id_list)
    message = None
    if len(all_organizations) == 0:    
        message = "You do not have any Organizations under your supervision."
    return render_to_response(
            'usermodule/organization_roles.html',
            {'all_organizations':all_organizations,"message":message},
            context)

#change by ZINIA
@login_required
@user_passes_test(admin_check, login_url='/')
def user_role_map(request, org_id=None):
    context = RequestContext(request)
    edited = False

    # adding Generic option in the organization list
    generic_org = Organizations.objects.filter(organization="Generic").first()

    roles = OrganizationRole.objects.filter(organization__in =[org_id, generic_org.id])

    # getting all profile of that organization
    profile_org = ProfileOrganization.objects.filter(organization_id = org_id)
    profiles = [pro.profile for pro in profile_org]
    print profiles
    users = UserModuleProfile.objects.filter(organisation_name=org_id)
    message = None
    if len(roles) == 0 or len(users) == 0:    
        message = "Your organization must have atleast one user and one role before assignment."
    return render_to_response(
            'usermodule/user_role_map.html',
            {'id':org_id,
            'users' : profiles,
            'roles' : roles,
            'message':message,
            'edited': edited},
            context)

#change by ZINIA
@login_required
@user_passes_test(admin_check, login_url='/')
def adjust_user_role_map(request, org_id=None):
    context = RequestContext(request)
    is_added = False

    # adding Generic option in the organization list
    generic_org = Organizations.objects.filter(organization="Generic").first()

    roles = OrganizationRole.objects.filter(organization__in =[org_id, generic_org.id])

    profile_org = ProfileOrganization.objects.filter(organization_id=org_id)
    profiles = [pro.profile for pro in profile_org]
    users = UserModuleProfile.objects.filter(organisation_name=org_id)
    initial_list = []
    for user_item in profiles:
        alist = UserRoleMap.objects.filter(user=user_item.pk).values('role')
        mist = []
        for i in alist:
            mist.append( i['role'])
        initial_list.append({'user': user_item.pk,'role':mist,'username': user_item.user.username})

    UserRoleMapfForm.base_fields['role'] = forms.ModelChoiceField(queryset=roles,empty_label=None)
    PermisssionFormSet = formset_factory(UserRoleMapfForm,max_num=len(users))
    new_formset = PermisssionFormSet(initial=initial_list)
    
    if request.method == 'POST':
        new_formset = PermisssionFormSet(data=request.POST)
        for idx,user_role_form in enumerate(new_formset):
            # user_role_form = UserRoleMapfForm(data=request.POST)
            u_id = request.POST['form-'+str(idx)+'-user']
            mist = initial_list[idx]['role']
            current_user = UserModuleProfile.objects.get(pk=u_id)
            results = map(int, request.POST.getlist('role-'+str(idx+1)))
            deleter = list(set(mist) - set(results))
            for role_id in results:
                roley = OrganizationRole.objects.get(pk=role_id)
                try:
                    UserRoleMap.objects.get(user=current_user,role=roley)
                except ObjectDoesNotExist as e:
                    UserRoleMap(user=current_user,role=roley).save()
            for dely in deleter:
                loly = OrganizationRole.objects.get(pk=dely)
                ob = UserRoleMap.objects.get(user=current_user,role=loly).delete()
        messages.success(request, '<i class="fa fa-check-circle"></i> Organization Roles have been adjusted successfully!',
                         extra_tags='alert-success crop-both-side')
        return HttpResponseRedirect('/usermodule/user-role-map/'+org_id)
    
    return render_to_response(
            'usermodule/add_user_role_map.html',
            {
            'id':org_id,
            # 'formset':formset,
            'new_formset':new_formset,
            'roles':roles,
            # 'users':users,
            },
            context)


def error_page(request,message = None):
    context = RequestContext(request)
    if not message:    
        message = "Something went wrong"
    return render_to_response(
            'usermodule/error_404.html',
            {'message':message,
            },
            context)

@csrf_exempt
#@login_required
def sent_datalist(request,username):
    content_user = get_object_or_404(User, username__iexact=str(username))
    print content_user.username
    cursor = connection.cursor()
    json_data_response = []
    #instance_data_json = {}
    try:
        passing_data  = [content_user.id]
        cursor.execute("BEGIN")
        cursor.callproc('get_submitted_data',passing_data)
        tmp_db_value = cursor.fetchall()
        cursor.execute("COMMIT")
	print (tmp_db_value)
        if tmp_db_value is not None:
            for every in tmp_db_value:
                instance_data_json = {}
                #event_type = switch_event_type_label(str(every[1]))
                instance_data_json['hh_id'] = str(every[0])
                instance_data_json['h_man'] = str(every[1])
                instance_data_json['uuid'] = str(every[2])
                instance_data_json['xform_id'] = every[4]
                instance_data_json['date_created'] = str(every[3])
                json_data_response.append(instance_data_json)

           # print json_data_response
        submission_status = 0
    except Exception, e:
        print "db insert error"
        print str(e)
        submission_status = 1
        # Rollback in case there is any error
        connection.rollback()
    finally:
        cursor.close()
        return_value = {
            'submission_status':submission_status,
        }
    return HttpResponse(json.dumps(json_data_response))



##################### GEO CATCHMENT AREA #############################
@login_required
def catchment_tree(request,user_id):
    query = "select * from geo_data where field_parent_id is null";
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    list_of_dictionary = []
    for each in id:
        create_dictionary(list_of_dictionary, each)
    datasource = json.dumps({'list_of_dictionary': list_of_dictionary})
    query = "select (SELECT  organization FROM public.usermodule_organizations where id = (select organisation_name_id from usermodule_usermoduleprofile where user_id = "+str(user_id)+")) ,(select employee_id from usermodule_usermoduleprofile where user_id = "+str(user_id)+"),(select country from usermodule_usermoduleprofile where user_id = "+str(user_id)+"),(select position from usermodule_usermoduleprofile where user_id = "+str(user_id)+"),username, email from auth_user where id="+str(user_id)+""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    organization = df.organization.tolist()[0]
    employee_id = df.employee_id.tolist()[0]
    country = df.country.tolist()[0]
    position = df.position.tolist()[0]
    username = df.username.tolist()[0]
    email = df.email.tolist()[0]

    check_nodes = get_check_nodes(user_id)

    return render(request, "usermodule/catchment_tree.html", {'datasource': datasource
                                                   ,'organization':organization
                                                   ,'employee_id':employee_id
                                                   ,'country': country
                                                   ,'position':position
                                                   ,'username':username
                                                   ,'email':email
                                                   ,'user_id':user_id
                                                   ,'check_nodes':check_nodes
                                                   })


def create_dictionary(list_of_dictionary, each):
    query = "select * from geo_data where id = " + str(each) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    name = df.field_name.tolist()[0]
    dict = {'id':each, 'text': name, 'children': []}
    query = "select * from geo_data where field_parent_id = " + str(each) + ""
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    for each in id:
        create_dictionary(dict['children'], each)
    list_of_dictionary.append(dict)


def database(query):
    cursor = connection.cursor()
    cursor.execute(query)
    connection.commit()
    cursor.close()


@login_required
def catchment_data_insert(request):
    result_set = request.POST.get('result_set').split(',')
    print result_set
    user_id = int(request.POST.get('user_id'))
    delete_prev_catchment_record(user_id)
    for each in result_set:
        if each:
            query = "INSERT INTO public.usermodule_catchment_area (user_id, geoid) VALUES("+str(user_id)+", "+str(each)+")"
            database(query)
    return HttpResponseRedirect('/usermodule/')


def get_check_nodes( user_id):
    query = "select * from usermodule_catchment_area where user_id = "+str(user_id)+""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    check_nodes = df.geoid.tolist()
    return check_nodes


def delete_prev_catchment_record(user_id):
    query = "delete from usermodule_catchment_area where user_id = "+str(user_id)+""
    database(query)


@login_required
def form_def(request):
    if request.POST:
        df = pandas.DataFrame()
        node_par = "select id from geo_definition where node_name = '" + str(request.POST.get('node_parent')) + "' "
        df = pandas.read_sql(node_par, connection)
        node = df.values.tolist()
        if len(node):
            query = "INSERT INTO geo_definition(node_name, node_parent)VALUES ('" + str(request.POST.get(
                'node_name')) + "' , " + str(node[0][0]) + ")"
        else:
            query = "INSERT INTO geo_definition(node_name)VALUES ('" + str(request.POST.get(
                'node_name')) + "' )"
        database(query)
	return HttpResponseRedirect('/usermodule/geo_def_data/')
    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_val = check.node_name
    return render(request, "usermodule/form_definition.html", {"node_val": node_val})

@login_required
def form(request):
    global parent
    if request.POST:
        if request.FILES:
            myfile = request.FILES['geojsonfile']
            url = "onadata/media/uploaded_files/"
            userName = request.user #"Jubair"
            fs = FileSystemStorage(location=url)
            myfile.name = str(datetime.now()) + "_" + str(userName) + "_" + str(myfile.name)
            filename = fs.save(myfile.name, myfile)
            full_file_path = "onadata/media/uploaded_files/" + myfile.name
            file = open(full_file_path, 'r')
            json_content = file.read()
            file.close()
        else:
            json_content = '{}'
            full_file_path = 'cd'
        parent = int(request.POST.get("parent_id"))
        if parent != -1:
            query = "INSERT INTO geo_data(field_name, field_parent_id,field_type_id,geocode,geojson,uploaded_file_path) VALUES('" + str(
                request.POST.get('field_name')) + "'," + str(
                request.POST.get('field_parent_' + str(parent) + '')) + "," + str(
                request.POST.get('field_type')) + ",'" + str(request.POST.get('geocode')) + "','" + str(
                json_content) + "','" + str(full_file_path) + "')"
        else:
            query = "INSERT INTO geo_data(field_name, field_type_id,geocode,geojson,uploaded_file_path) VALUES('" + str(
                request.POST.get('field_name')) + "'," + str(request.POST.get('field_type')) + "," + str(
                request.POST.get('geocode')) + ",'" + str(json_content) + "','" + str(full_file_path) + "')"
        database(query)
        return HttpResponseRedirect("/usermodule/geo_list/")
    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_val = check.node_name.tolist()
    node_id = check.id.tolist()
    node = json.dumps({"node_val": node_val, "node_id": node_id})
    list = zip(node_id, node_val)
    return render(request, 'usermodule/form.html', {'node': list})


@login_required
def form_drop(request):
    if request.POST:
        df = pandas.DataFrame()
        fb = str(request.POST.get('field_type'))
        field_name_query = "select * from geo_data where field_type_id = " + str(request.POST.get('field_type')) + ""
        df = pandas.read_sql(field_name_query, connection)
        field_name = df.field_name.tolist()
        field_id = df.id.tolist()
        field_type_name_query = "select * from geo_definition where id = " + str(request.POST.get('field_type')) + ""
        df = pandas.read_sql(field_type_name_query, connection)
        field_type_name = df.node_name.tolist()
    field_name = json.dumps({'field_name': field_name, 'field_id': field_id, 'field_type_name': field_type_name})
    return HttpResponse(field_name)


@login_required
def filtering(request):
    if request.POST:
        df = pandas.DataFrame()
        field_name_query = "select * from geo_data where field_type_id = " + str(
            request.POST.get('field_type_id')) + " and field_parent_id = " + str(
            request.POST.get('field_parent_id')) + ""
        df = pandas.read_sql(field_name_query, connection)
        field_name = df.field_name.tolist()
        field_id = df.id.tolist()
        field_type_query = "select * from geo_definition where id=" + str(request.POST.get('field_type_id')) + ""
        df = pandas.read_sql(field_type_query, connection)
        field_type = df.node_name.tolist()
    field_name = json.dumps({'field_name': field_name, 'field_id': field_id, 'field_type': field_type})
    return HttpResponse(field_name)


@login_required
def tree(request):
    id = int(request.POST.get('objet'))
    # print(id)
    list = []
    tree_construct(id, list)
    response_record = {}
    if len(list):
        for i in range(len(list) - 1):
            response_record[list[i]] = list[i + 1]
        response_record[list[len(list) - 1]] = id
        parent = list[len(list) - 1]
    else:
        parent = -1
    return HttpResponse(json.dumps({'response_record': response_record,'parent_id':parent}))


def tree_construct(id, list):
    query = "select * from geo_definition where id = " + str(id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    parent = df.node_parent.tolist()
    if parent[0] is None:
        return
    else:
        tree_construct(parent[0], list)
    list.append(parent[0])
    return


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

@login_required
def geo_def_list(request):
    geo_def_query = "with t as (select * from geo_definition) select t.id ,t.node_name , (select node_name from geo_definition where id = t.node_parent) as node_parent_name from t"
    geo_def_data = json.dumps(__db_fetch_values_dict(geo_def_query))
    return render(request,'usermodule/geo_def_list.html',{
      'geo_def_data':geo_def_data
    })

@login_required
def geo_list(request):
    query = "select id,field_name,geocode,(select node_name from geo_definition where id = field_type_id) as field_type from geo_data"
    geo_def_data = json.dumps(__db_fetch_values_dict(query))
    return render(request,'usermodule/geo_list.html',{
      'geo_def_data':geo_def_data
    })


@login_required
def edit_form_definition(request, form_definition_id):
    check = pandas.DataFrame()
    option = "select * from geo_definition"
    check = pandas.read_sql(option, connection)
    node_val = check.node_name
    query_specific = "with t as (select * from geo_definition) select t.id ,t.node_name , (select node_name from geo_definition where id = t.node_parent) as node_parent_name from t where t.id =" + str(
        form_definition_id) + ""
    check = pandas.read_sql(query_specific, connection)
    node_name = check.node_name.tolist()[0];
    node_parent_name = check.node_parent_name.tolist()[0];
    return render(request, "usermodule/edit_form_definition.html", {"node_val": node_val,
                                                                    'node_parent_name': node_parent_name,
                                                                    'node_name': node_name,
                                                                    "form_definition_id": form_definition_id})


@login_required
def update_form_definition(request):
    if request.POST:
        df = pandas.DataFrame()
        node_par = "select id from geo_definition where node_name = '" + str(request.POST.get('node_parent')) + "' "
        df = pandas.read_sql(node_par, connection)
        node = df.values.tolist()
        delete_query = "delete  from geo_definition where id=" + str(int(request.POST.get('form_definition_id'))) + ""
        database(delete_query)
        if len(node):
            query = "INSERT INTO geo_definition(id,node_name, node_parent)VALUES (" + str(
                int(request.POST.get('form_definition_id'))) + ",'" + str(request.POST.get('node_name')) + "' , " + str(
                node[0][0]) + ")"
        else:
            query = "INSERT INTO geo_definition(id,node_name)VALUES (" + str(
                int(request.POST.get('form_definition_id'))) + ",'" + str(request.POST.get('node_name')) + "' )"
        database(query)
    return HttpResponseRedirect("/usermodule/geo_def_data/")


@login_required
def delete_form_definition(request, form_definition_id):
    list_of_form_definition = []
    form_definition_calculation(list_of_form_definition, form_definition_id)
    print(list_of_form_definition)
    return HttpResponseRedirect("/usermodule/geo_def_data/")


def form_definition_calculation(list_of_form_definition, form_definition_id):
    list_of_form_definition.append(int(form_definition_id))
    query = "select * from geo_definition where node_parent=" + str(form_definition_id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    query = "select * from geo_data where field_type_id=" + str(form_definition_id) + ""
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    form_id = df.id.tolist()
    for each in form_id:
        delete_from_catchment_area = "delete from usermodule_catchment_area where geoid = " + str(each) + ""
        database(delete_from_catchment_area)
    delete_query = "delete from geo_definition where id =" + str(int(form_definition_id)) + ""
    database(delete_query)
    delete_query = "delete from geo_data where field_type_id =" + str(int(form_definition_id)) + ""
    database(delete_query)
    for each in id:
        form_definition_calculation(list_of_form_definition, each)


@login_required
def json_data_fetch(request):
    list_of_selected_node = request.POST.get('id')
    list_of_selected_node = list_of_selected_node[1:len(list_of_selected_node) - 1].split(',')
    json_content_dictionary = []
    for each in list_of_selected_node:
        if each:
            query_for_json = "select * from geo_data where id = " + str(each) + ""
            df = pandas.DataFrame()
            df = pandas.read_sql(query_for_json, connection)
            uploaded_file_path = df.uploaded_file_path.tolist()[0]
            if uploaded_file_path != "cd":
                file = open(uploaded_file_path, 'r')
                json_content = file.read()
                file.close()
            else:
                json_content = "{}"
            json_content_dictionary.append(json_content)
    return  HttpResponse(json.dumps({'json_content': json_content_dictionary}))


@login_required
def org_catchment_tree(request, org_id):
    query = "select * from geo_data where field_parent_id is null"
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    id = df.id.tolist()
    list_of_dictionary = []
    for each in id:
        create_dictionary(list_of_dictionary, each)
    datasource = json.dumps({'list_of_dictionary': list_of_dictionary})
    query = "select * from usermodule_organizations where id=" + str(org_id)
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    organization = df.organization.tolist()[0]
    check_nodes = get_org_check_nodes(org_id)
    return render(request, "usermodule/org_catchment_tree.html", {'datasource': datasource
        , 'organization_name': organization
        , 'check_nodes': check_nodes,'org_id':org_id})


def get_org_check_nodes(org_id):
    query = "select * from organization_catchment_area where org_id = " + str(org_id)
    df = pandas.DataFrame()
    df = pandas.read_sql(query, connection)
    check_nodes = df.geoid.tolist()
    return check_nodes


@login_required
def org_catchment_data_insert(request):
    result_set = request.POST.get('result_set').split(',')
    org_id = int(request.POST.get('org_id'))
    delete_prev_org_catchment_record(org_id)
    for each in result_set:
        if each:
            query = "INSERT INTO public.organization_catchment_area (org_id, geoid) VALUES(" + str(org_id) + ", " + str(
                each) + ")"
            database(query)
    return HttpResponseRedirect('/usermodule/organizations/')

    

def delete_prev_org_catchment_record(org_id):
    query = "delete from organization_catchment_area where org_id = " + str(org_id)
    database(query)
####################### GEO CATCHMENT AREA #############################


############################# FORM PERMISSION (ZINIA) #####################

"""Form settings Code"""

def single_query(query):
    """function for  query where result is single"""

    fetchVal = data_connection(query)
    strType = map(str, fetchVal[0])
    ans = strType[0]
    return ans

def data_connection(queryr):
    try:
        cursor = connection.cursor()
        cursor.execute(queryr)
        fetchVal = cursor.fetchall()
        # Commit the changes to the database_
        connection.commit()
        # Close communication with the PostgreSQL database
        cursor.close()
        return fetchVal
    except (Exception) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()


def get_role():
    query = "SELECT r.id, organization_id, role, organization FROM public.usermodule_organizationrole r, public.usermodule_organizations o where r.organization_id=o.id";
    fetchVal = data_connection(query)
    role_data = []
    for eachval in fetchVal:
        temp = list(eachval)
        role_data.append(temp)
    return role_data


def get_role_permission(id_string):
    query = "select id, xform_id, role_id, can_view, can_submit, can_edit, can_delete, can_setting from public.rolewiseform where xform_id = %d" % (
    id_string)
    
    permission_data = []
    fetchVal = data_connection(query)
    
    for eachval in fetchVal:
        temp = list(eachval)
        permission_data.append(temp)
    return permission_data


def checking_change_permission(view_list, edit_list, submit_list, delete_list, role_list, permission_list):
    """ """
    changed_role = {}
    print view_list
    #checking if permission of role has changed from its previous condition if changed then true else it will be false
    for p in permission_list:
        if str(p[2]) in view_list and p[3] == 0:
            print "view1"
            changed_role[p[2]] = True
        elif str(p[2]) in submit_list and p[4] == 0:
            print "submit1"
            changed_role[p[2]] = True
        elif str(p[2]) in edit_list and p[5] == 0:
            print "edit1"
            changed_role[p[2]] = True
        elif str(p[2]) in delete_list and p[6] == 0:
            print "delete1"
            changed_role[p[2]] = True
        elif str(p[2]) not in view_list and p[3] == 1:
            print str(p[2]) + " view2"
            changed_role[p[2]] = True
        elif str(p[2]) not in submit_list and p[4] == 1:
            print "submit2"
            changed_role[p[2]] = True
        elif str(p[2]) not in edit_list and p[5] == 1:
            print "edit2"
            changed_role[p[2]] = True
        elif str(p[2]) not in delete_list and p[6] == 1:
            print "delete2"
            changed_role[p[2]] = True
        else:
            changed_role[p[2]] = False
    return changed_role


def update_table(query):
    try:
        print query
        # create a new cursor
        cur = connection.cursor()
        # execute the UPDATE  statement
        cur.execute(query)
        # get the number of updated rows
        vendor_id = cur.fetchone()[0]
        print vendor_id
        # Commit the changes to the database_
        connection.commit()
        # Close communication with the PostgreSQL database
        cur.close()
    except (Exception) as error:
        print(error)
    finally:
        if connection is not None:
            connection.close()


@csrf_exempt
def startpage(request, username, id_string):
    query = "select id from logger_xform where id_string = '%s'" % (id_string)
    form_id = int(single_query(query))
    if request.method == 'POST':
        # id_string = request.POST.get('id_string');
        # query = "select id from logger_xform where id_string = '%s'" % (id_string)
        # form_id = int(single_query(query))
        view_list = request.POST.getlist('view_id[]');
        edit_list = request.POST.getlist('edit_id[]');
        submit_list = request.POST.getlist('submit_id[]');
        delete_list = request.POST.getlist('delete_id[]');
        role_list = get_role()
        permission_role = get_role_permission(form_id)
        changed_role = checking_change_permission(view_list, edit_list, submit_list, delete_list, role_list,
                                                  permission_role)
        for r in role_list:
            view_flag = edit_flag = delete_flag = submit_flag = 0
            if r[0] in changed_role and changed_role[r[0]] == True:
                if str(r[0]) in view_list:
                    view_flag = 1
                if str(r[0]) in edit_list:
                    edit_flag = 1
                if str(r[0]) in submit_list:
                    submit_flag = 1
                if str(r[0]) in delete_list:
                    delete_flag = 1
                query = "UPDATE public.rolewiseform SET can_view = %d, can_submit =  %d, can_edit= %d , can_delete=%d where xform_id = %d and role_id=%d" % (
                    view_flag, submit_flag, edit_flag, delete_flag, form_id, r[0])
                update_table(query)
            else:
                if str(r[0]) in view_list + edit_list + submit_list + delete_list and r[0] not in changed_role:
                    if str(r[0]) in view_list:
                        view_flag = 1
                    if str(r[0]) in edit_list:
                        edit_flag = 1
                    if str(r[0]) in submit_list:
                        submit_flag = 1
                    if str(r[0]) in delete_list:
                        delete_flag = 1
                    query = "INSERT INTO public.rolewiseform ( xform_id, role_id, can_view, can_submit, can_edit, can_delete, can_setting) VALUES (%d, %d, %d, %d, %d, %d, 0) RETURNING id;" % (
                        form_id, r[0], view_flag, submit_flag, edit_flag, delete_flag)
                    update_table(query)
	messages.success(request,'<i class="fa fa-check-circle"></i> Roles has been updated successfully!',extra_tags='alert-success crop-both-side')



    context = {
            'role_list': get_role(),
            'permission_data': get_role_permission(form_id),
            'id_string': id_string
        }
    return render(request, 'usermodule/startpage.html', context)


#####################################################################
@csrf_exempt
def get_hh_list(request,username):
    
    #username = request.GET.get('username', '')
    user = get_object_or_404(User, username=username)
    org_id_list = get_organization_by_user(user)
    org_list = org_id_list
    org_string = ' , '.join(str(x) for x in org_list)
    # query = 'select dist_code||up_code||union_code||spot_code as spot from vwbranchspotcoverage where id in (%s )'%(org_string)
    # spots_ = __db_fetch_values(query)
    # spot_list = ["'" + x[0] + "'" for x in spots_]
    # spot_string = ' , '.join(str(x) for x in spot_list)
    # if spot_string == '':
    #     spot_string = "'%'"
    # sql = 'SELECT hh_status_id,  hh_serial, hh_id, village_id, spot_id, hh_name, nid, hh_husband_father_name,wealth_rank,mobile,gps FROM public.household where village_id in (%s)'%(spot_string)
    sql = 'with t as(SELECT hh_status_id,  hh_serial, hh_id, village_id, spot_id, beneficiary_name, nid, hh_husband_father_name,wealth_rank,mobile,gps,(SELECT status FROM public.approval_instanceapproval where instance_id=household.last_instance_id limit 1) status, hh_name FROM public.household where branch_id in(%s)) select t.*, dist_code, district, up_code, upazila , union_code, union_name, village_code, village,spot_code,spot from t,vwspot where t.spot_id=vwspot.spot_id'%(org_string)
    print sql
    household_list = __db_fetch_values(sql)
    json_data_response_all = []
    if len(household_list) > 0:
        for household in household_list:
            json_data_response = {}
            # household_ = sjson.dumps(household[2])
            # household = sjson.loads(household_)
            # print household
            json_data_response['hh_id'] = household[2]
            json_data_response['hh_head'] = household[5]
            json_data_response['hh_serial'] = household[1]

            json_data_response['husband_father_name'] = household[7]
            json_data_response['wealth_rank'] = household[8]
            data = __db_fetch_values("select dist_code, district, up_code, upazila , union_code, union_name, village_code, village from vwvillage where village_id = '%s'" % (household[3]))
            if len(data)>0 and len(data[0])>0:
                datas = data[0]
                district = datas[0]
                district_label = datas[1]
                upazila = district+datas[2]
                upazila_label = datas[3]
                union = upazila+datas[4]
                union_label = datas[5]
                village = union+datas[6]
                village_label = datas[7]
                json_data_response['village_name'] = village_label
                json_data_response['district_name'] = district_label
                json_data_response['upazila_name'] = upazila_label
                json_data_response['union_name'] = union_label
                json_data_response['village_name'] = village_label
                json_data_response['district_id'] = district
                json_data_response['upazila_id'] = upazila
                json_data_response['union_id'] = union
                json_data_response['village_id'] = village
            spots = __db_fetch_values("select spot_code,spot from vwspot where village_id = '%s'" % (household[4]))
            if len(spots)>0:
                spot = village+spots[0][1]
                spot_label = spots[0][1]
                json_data_response['pra_id'] = spot
                json_data_response['pra_name'] = spot_label
            json_data_response['form_id'] = 'hh_registration'



            json_data_response_all.append(json_data_response)
    #print json.dumps(json_data_response)
    return HttpResponse(json.dumps(json_data_response_all))

@csrf_exempt
def get_village_list(request,username):
    user = get_object_or_404(User, username=username)
    org_id_list = get_organization_by_user(user)
    org_list = org_id_list
    org_string = ' , '.join(str(x) for x in org_list)

    query = 'select union_code from vwbranchunioncoverage where organization  = any (select organization from usermodule_organizations where id in (%s))'%(org_string )
    sql = "select json->>'village' item_id,json->>'_xform_id_string' form_id, json item_content,(SELECT status FROM public.approval_instanceapproval where instance_id=logger_instance.id limit 1) status from logger_instance where xform_id=456 and user_id=(select id from auth_user where username='" + username + "') and deleted_at is null order by id"
    json_data_response = {}
    union_data = __db_fetch_values(query)
    union_list = ["'"+x[0]+"'" for x in union_data]
    print union_list
    union_string = ' , '.join(x for x in union_list)
    print union_string
    json_data_response_all = []
    sql = 'select village_code, village, dist_code, district, up_code, upazila, union_code, union_name from vwvillage where union_code in (%s)'%(union_string)
    village_list = __db_fetch_values(sql)
    if len(village_list) > 0:
        for village in village_list:
            json_data_response = {}
            json_data_response['village_id'] = village[2]+village[4]+village[6]+village[0]
            json_data_response['village_name'] = village[1]
            json_data_response['district_id'] = village[2]
            json_data_response['district_name'] =village[3]
            json_data_response['upazila_id'] = village[2]+village[4]

            json_data_response['upazila_name'] = village[5]
            json_data_response['union_id'] = village[2]+village[4]+village[6]

            json_data_response['union_name'] = village[7]


            json_data_response_all.append(json_data_response)



    return HttpResponse(json.dumps(json_data_response_all))

@csrf_exempt
def get_pra_list(request,username):
    
    #username = request.GET.get('username', '')
    user = get_object_or_404(User, username=username)
    org_id_list = get_organization_by_user(user)
    org_list = org_id_list
    org_string = ' , '.join(str(x) for x in org_list)

    query = 'select union_code from vwbranchunioncoverage where organization  = any (select organization from usermodule_organizations where id in (%s))' % (
    org_string)
    sql = "select json->>'village' item_id,json->>'_xform_id_string' form_id, json item_content,(SELECT status FROM public.approval_instanceapproval where instance_id=logger_instance.id limit 1) status from logger_instance where xform_id=456 and user_id=(select id from auth_user where username='" + username + "') and deleted_at is null order by id"
    json_data_response = {}
    union_data = __db_fetch_values(query)
    union_list = ["'" + x[0] + "'" for x in union_data]
    print union_list
    union_string = ' , '.join(x for x in union_list)
    print union_string
    json_data_response_all = []

    sql = 'select village_code, village, dist_code, district, up_code, upazila, union_code, union_name ,spot_code, spot from vwspot where union_code in (%s)' % (
    union_string)
    pra_list = __db_fetch_values(sql)
    json_data_response = []
    if len(pra_list) > 0:
        for village in pra_list:
            json_data_response = {}
            json_data_response['pra_id'] = village[2] + village[4] + village[6] + village[0]+village[8]
            json_data_response['pra_code'] = village[9]
            json_data_response['village_id'] = village[2] + village[4] + village[6] + village[0]
            json_data_response['village_name'] = village[1]
            json_data_response['district_id'] = village[2]
            json_data_response['district_name'] = village[3]
            json_data_response['upazila_id'] = village[2] + village[4]

            json_data_response['upazila_name'] = village[5]
            json_data_response['union_id'] = village[2] + village[4] + village[6]

            json_data_response['union_name'] = village[7]
            json_data_response_all.append(json_data_response)

    #print json.dumps(json_data_response)	
    return HttpResponse(json.dumps(json_data_response_all))

@csrf_exempt
def get_training_list(request,username):
    
    #username = request.GET.get('username', '')

    sql = "select id item_id,json->>'_xform_id_string' form_id,json item_content,(SELECT status FROM public.approval_instanceapproval where instance_id=logger_instance.id limit 1) status from logger_instance where xform_id=465 and user_id=(select id from auth_user where username='" + username + "') and deleted_at is null order by id"

    cursor = connection.cursor()
    cursor.execute(sql)
    tmp_db_value = cursor.fetchall();
    cursor.close()
    json_data_response = []   
    #print tmp_db_value
    if tmp_db_value is not None:   
       for every in tmp_db_value: 
           instance_data_json = {}
           
           instance_data_json['item_id'] = str(every[0])
           instance_data_json['form_id'] = str(every[1])
	   instance_data_json['item_content'] = str(json.dumps(every[2]).encode('utf-8'))
           
           instance_data_json['status'] = str(every[3])
           json_data_response.append(instance_data_json)
    #print json.dumps(json_data_response)	
    return HttpResponse(json.dumps(json_data_response))


@csrf_exempt
def get_school_list(request,username):
    
    #username = request.GET.get('username', '')

    sql = "select json->>'school_id' id,json->>'school_name' school_name,json->>'headmaster_name' headmaster,json->>'headmaster_mobile' mobile,'New' status from logger_instance where xform_id=402 and user_id=(select id from auth_user where username='" + username + "') and deleted_at is null order by id"

    cursor = connection.cursor()
    cursor.execute(sql)
    tmp_db_value = cursor.fetchall();
    cursor.close()
    json_data_response = []   
    #print tmp_db_value
    if tmp_db_value is not None:   
       for every in tmp_db_value: 
           instance_data_json = {}
           instance_data_json['id'] = str(every[0])
           if every[1] != None:
           	instance_data_json['school_name'] = str(every[1].encode('utf-8'))
	   else:
		instance_data_json['school_name'] = str(every[1])
	   if every[2] != None:
           	instance_data_json['headmaster'] = str(every[2])
	   else:
		instance_data_json['headmaster'] = str(every[2])
           
           instance_data_json['mobile'] = str(every[3])
           instance_data_json['status'] = str(every[4])
           json_data_response.append(instance_data_json)
    #print json.dumps(json_data_response)	
    return HttpResponse(json.dumps(json_data_response))


def user_geoinfo(request,username):
    c = connection.cursor()
    try:
        c.execute("BEGIN")
        c.callproc("get_geo_detail", [username]) 
        results = c.fetchall()
        c.execute("COMMIT")
    finally:
        c.close()

    json_data_response = []   
    for every in results:
        instance_data_json = {}    
        if str(every[3])=="District":
            instance_data_json['district'] = str(every[2])
        elif str(every[3])=="Upazila":
            instance_data_json['upazila'] = str(every[2])
        elif str(every[3])=="Union":
            instance_data_json['union_name'] = str(every[2])
        else:
            instance_data_json[str(every[3])] = str(every[2])
        json_data_response.append(instance_data_json)

    return HttpResponse(json.dumps(json_data_response));


@csrf_exempt
def get_hh_datalist(request,username,hhid):
    
    #username = request.GET.get('username', '')
    #select id,json->>'_xform_id_string' id_string,date_created from logger_instance 

    sql = "select xml,json->>'_xform_id_string' id_string,to_char(date_created,'DD-Mon-YYYY') date_created from logger_instance where json->>'hh_id'='" + hhid + "' and deleted_at is null order by id"

    cursor = connection.cursor()
    cursor.execute(sql)
    tmp_db_value = cursor.fetchall();
    print tmp_db_value[0]
    cursor.close()
    json_data_response = []   
    print sql
    if tmp_db_value is not None:
       print 'here'   
       for every in tmp_db_value: 
           print every[0]
           instance_data_json = {}
           instance_data_json['xml'] = str(every[0])
           instance_data_json['id_string'] = str(every[1].encode('utf-8'))
           instance_data_json['submitted'] = str(every[2])
           print instance_data_json

           json_data_response.append(instance_data_json)
    #print json.dumps(json_data_response)	
    return HttpResponse(json.dumps(json_data_response))


def test_csv(request):
    """
    @zinia
    """
    sql = 'select _list_name list_name,_label_name "label",_name_text "name",_district district,_upazila upazila,_union_name union_name,_ward ward from get_geo_list()'
    data = []
    cursor = connection.cursor()
    cursor.execute(sql)
    tmp_db_value = cursor.fetchall();

    print tmp_db_value[0]
    cursor.close()
    for dt in tmp_db_value:
        data.append(list(dt))
    user_path_filename = os.path.join(settings.MEDIA_ROOT, request.user.username)
    user_path_filename = os.path.join(user_path_filename, "formid-media")
    if not os.path.exists(user_path_filename):
        os.makedirs(user_path_filename)
    
    filename = os.path.join(user_path_filename, 'itemsets_PO42e0f.csv')
    col_names = [i[0] for i in cursor.description]
    print "data"
    print data
    print "##333333333333333"
    print col_names
    df = pd.DataFrame(data,  columns = col_names)
    df.set_index('list_name', inplace=True)
    df.to_csv(filename)
    return HttpResponseRedirect('/usermodule/')


@csrf_exempt
def sent_rejecteddatalist(request,username):
    context = RequestContext(request)
    content_user = get_object_or_404(User, username__iexact=str(username))
    print content_user
    json_data_response = []
    #print content_user.id
    cursor = connection.cursor()
    options_query ="SELECT xml xml_url,'Rejected',json->>'_xform_id_string' form_name,json->>'hh_id' id,'Household' module_name  FROM logger_instance where id=any(SELECT instance_id FROM public.approval_instanceapproval where status=any(Array['PNGO Rejected']))and '"+ username +"'=any(select username from auth_user where id=logger_instance.user_id)" 
    print options_query
    cursor.execute(options_query)
    tmp_db_value = cursor.fetchall()
    if tmp_db_value is not None:
        for every in tmp_db_value:
            print str(every[0])
            instance_data_json = {}
            instance_data_json['xml_url'] = str(every[0])
            instance_data_json['status'] = str(every[1])
            instance_data_json['form_name'] = str(every[2])
            instance_data_json['id'] = str(every[3])
            instance_data_json['module_name'] = str(every[4])
            json_data_response.append(instance_data_json)
    cursor.close()
    return HttpResponse(json.dumps(json_data_response))


def __db_fetch_values(query):
    """
        Fetch database result set as list of tuples

        Args:
            query (str): raw query string

        Returns:
            str: Returns database result set as list of tuples
    """
    cursor = connection.cursor()
    cursor.execute(query)
    fetch_val = cursor.fetchall()
    cursor.close()
    data_list = []
    for each_val in fetch_val:
        data_list.append(list(each_val))

    return data_list

def get_user_role(username):
    user = get_object_or_404(User, username=username)
    profile = get_object_or_404(UserModuleProfile, user=user)
    print profile.id
    userrole = UserRoleMap.objects.filter(user_id=profile.id).first()
    role = userrole.role
    return role.role


@csrf_exempt
def get_hh_profile(request,username,hhid):
    
    #username = request.GET.get('username', '')
    #select id,json->>'_xform_id_string' id_string,date_created from logger_instance
    ben_query = "select json->>'husband_father_name' , json->>'beneficiary_name', json->>'member_info', json->>'mobile', json->>'group_selected_assessment', json->>'picture', json->>'username' from vwlogger_instance where xform_id = 457 and json->>'info/hh_id' = '%s'" % (
        hhid)
    enterprise_query = "select json->>'enterprise_name',json->>'enterprise_option',json->>'enterprise_type' from vwlogger_instance where xform_id = 464 and json->>'info/hh_id' = '%s'" % (
        hhid)
    group_query = "select json->>'group'::text , json->>'username' from vwlogger_instance where xform_id = 458 and json->>'info/hh_id' = '%s'" % (
        hhid)
    bene_list = __db_fetch_values(ben_query)
    json_data_response = {}
    if len(bene_list) > 0:
        json_data_response['husband_father_name'] = bene_list[0][0]
        json_data_response['beneficiary_name'] = bene_list[0][1]

        member_info = json.loads(bene_list[0][2])
        json_data_response['member'] = json.loads(bene_list[0][2])
        json_data_response['mobile'] = bene_list[0][3]
        json_data_response['group_selected_assessment'] = bene_list[0][4]
        json_data_response['picture'] = bene_list[0][5]
        ben_username=bene_list[0][6]
    # group selection
    group_list = __db_fetch_values(group_query)
    group_list.append([json_data_response['group_selected_assessment'],ben_username])
    if len(group_list) > 0:
        group_role_list = []
        for g in group_list:
            group_id = g[0]
            username = g[1]
            group_value_query = "select value_label from xform_extracted where xform_id = 458 and field_name = 'group' and value_text = '%s'" % (
                group_id)
            role = get_user_role(username)
            group_value = json.loads(row_query(group_value_query))
            if role =='PO':
                json_data_response['group_selected_po'] = group_value['Bangla']
            if role =='BM':
                json_data_response['group_selected_bm'] = group_value['Bangla']
            if role == 'RM':
                json_data_response['group_selected_rm'] = group_value['Bangla']
            else:
                json_data_response['group_selected_initial'] = group_value['Bangla']
    # enterprise info
    enterprise = __db_fetch_values(enterprise_query)
    if len(enterprise) > 0:
        if enterprise[0][2] is not None:
            enterprise_type_query = "select label from  enterprise_type where id = %s" % (int(enterprise[0][2]))
            enterprise_type = row_query(enterprise_type_query)
            json_data_response['enterprise_type_id'] = int(enterprise[0][2])
            json_data_response['enterprise_type_name'] = enterprise_type
        if enterprise[0][1] is not None:
            enterprise_name_query = "select name from  enterprise where id = %s" % (int(enterprise[0][1]))
            enterprise_name = row_query(enterprise_name_query)
            json_data_response['enterprise_name_id'] = int(enterprise[0][1])
            json_data_response['enterprise_name_name'] = enterprise_name
        if enterprise[0][0] is not None:
            enterprise_option_query = "select option_name from  enterprise_option where id = %s" % (int(enterprise[0][0]))
            enterprise_option = row_query(enterprise_option_query)
            json_data_response['enterprise_option_id'] = int(enterprise[0][0])
            json_data_response['enterprise_option_name'] = enterprise_option

    return HttpResponse(json.dumps(json_data_response))


def row_query(query):
    """function for  query where result is single"""

    fetchVal = __db_fetch_values(query)
    if len(fetchVal) == 0:
        return None

    strType = map(str, fetchVal[0][0].encode('utf-8')
)

    ans = fetchVal[0][0].encode('utf-8')
    return ans

#mobile login verify

@csrf_exempt
def login_verify(request):

    if request.method == 'POST':
        # Gather the username and password provided by the user.
        # This information is obtained from the login form.
	print "check1"
	print request.body
        json_string = request.body
	print "check2" +json_string
        data = json.loads(json_string)
	print "check3 "
        username = data['UserName']
        password = data['Password']
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
                    #user profile
                    user_profile = user.usermoduleprofile
                    # if date.today() > current_user.expired.date():
                    #     return HttpResponseRedirect('/usermodule/change-password')
                    # if user and password is valid then
                    print user_profile.id
                    user_role = UserRoleMap.objects.filter(user_id=user_profile.id).first()

                    profile_organization = ProfileOrganization.objects.filter(profile_id = user_profile.id)

                    organization_list = [pro.organization.organization for pro in profile_organization]
                    #user role
                    #print user_role
                    user_information = {

                    }
                    user_information['Name']=user.first_name + " " + user.last_name
                    user_information['Email'] = user.email
                    user_information['is_superuser'] = str(user.is_superuser)
                    user_information['is_staff'] = str(user.is_staff)
                    user_information['IsAdmin'] = str(user_profile.admin)
                    user_information['EmployeeId'] = str(user_profile.employee_id)
                    user_information['Position'] = user_profile.position
                    user_information['Role'] =  user_role.role.role
                    user_information['Organizations'] = [pro.organization.organization for pro in profile_organization]
                    
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

#mobile save user
@csrf_exempt
def save_user(request):
    """data = {
                "UserName" : "tup_2",
                "FirstName" : "Md.",
                "LastName" : "Asaduzzaman",
                "Email" : "asad@mpower-social.com",
                "Password" : "12345678",
                "Organizations" : ["BRAC"],
                "Country" : "BGD",
                "IsAdmin" : 0
                }


    """

    
    json_string = request.body
    # json_string = data
    # print json_string
    data = json.loads(json_string)
    submitted_data = {}
    submitted_data['username'] = data['UserName']
    submitted_data['password_repeat'] = data['Password']
    
    submitted_data['first_name'] = data['FirstName'][0].upper() + data['FirstName'][1:]
    submitted_data['last_name'] = data['LastName'][0].upper() + data['LastName'][1:]
    submitted_data['country'] = data['Country']
    submitted_data['organization'] = data['Organizations']
    if data['IsAdmin']:
        submitted_data['admin'] = True
    else:
        submitted_data['admin'] = False
    submitted_data['password'] = data['Password']
    if 'Email' in data:
    	  submitted_data['email'] = data['Email']

		

    # user_form = UserForm(username=data['UserName'], email=data['Email'], password=data['Password'], password_repeat=data['Password'])
    user_form = UserForm(data=submitted_data)
    profile_form = UserProfileForm(data=submitted_data, admin_check=True)

    if user_form.is_valid() and profile_form.is_valid():

        user = user_form.save()
        form_bool_value = False

        encrypted_password = make_password(user.password)
        user.password = encrypted_password
        user.save()

        profile = profile_form.save(commit=False)

        profile.user = user
        expiry_months_delta = 3

        next_expiry_date = (datetime.today() + timedelta(expiry_months_delta * 365 / 12))
        profile.expired = next_expiry_date
        profile.admin = form_bool_value

        profile.save()

        main_user_profile = UserProfile(user=user)
        main_user_profile.save()

        registered = True

        passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
        passwordHistory.password = encrypted_password
        passwordHistory.save()

        
        for org in submitted_data['organization']:
            organization = Organizations.objects.filter(organization = org).first()
            profile_organization = ProfileOrganization(profile_id=profile.id, organization=organization)
            profile_organization.save()



        return HttpResponse('success', status=200)

    else:
        print user_form
        print "###################"
        print user_form.errors
        print profile_form.errors
        return HttpResponse('User creation failed', status=409)

    print data
    return HttpResponse('no action', status=409)

@login_required
@user_passes_test(admin_check,login_url='/')
def user_register(request):
    # Like before, get the request's context.
    context = RequestContext(request)
    admin_check = UserModuleProfile.objects.filter(user=request.user)

    if request.user.is_superuser:
        admin_check = True
    elif admin_check:
        admin_check = admin_check[0].admin
    # A boolean value for telling the template whether the registration was successful.
    # Set to False initially. Code changes value to True when registration succeeds.
    registered = False

    #organization list
    org_id_list = get_organization_by_user(request.user)

    if not org_id_list:
        organization_list = Organizations.objects.all()
    else:
        organization_list = Organizations.objects.filter(pk__in=org_id_list)

    print "########################"
    print organization_list

    # If it's a HTTP POST, we're interested in processing form data.
    if request.method == 'POST':
        # Attempt to grab information from the raw form information.
        # Note that we make use of both UserForm and UserProfileForm.
        user_form = UserForm(data=request.POST)
        profile_form = UserProfileForm(data=request.POST, admin_check=admin_check)

        # If the two forms are valid...
        if user_form.is_valid() and profile_form.is_valid():
            user = user_form.save()

            form_bool = request.POST.get("admin", "xxx")
            if form_bool == "xxx":
                form_bool_value = False
            else:
                form_bool_value = True

            # encrypted password is saved so that it can be saved in password history table
            encrypted_password = make_password(user.password)
            user.password = encrypted_password
            user.save()

            # Now sort out the UserProfile instance.
            # Since we need to set the user attribute ourselves, we set commit=False.
            # This delays saving the model until we're ready to avoid integrity problems.
            profile = profile_form.save(commit=False)
            # profile.organisation_name = request.POST.get("organisation_name", "-1")
            profile.user = user
            expiry_months_delta = 3
            # Date representing the next expiry date
            next_expiry_date = (datetime.today() + timedelta(expiry_months_delta * 365 / 12))
            profile.expired = next_expiry_date
            profile.admin = form_bool_value
            # Did the user provide a profile picture?
            # If so, we need to get it from the input form and put it in the UserProfile model.
            # if 'picture' in request.FILES:
            #     profile.picture = request.FILES['picture']

            # Now we save the UserProfile model instance.
            profile.save()

            # kobo main/models/UserProfile
            main_user_profile = UserProfile(user=user)
            main_user_profile.save()

            # Update our variable to tell the template registration was successful.
            registered = True

            # insert password into password history
            passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
            passwordHistory.password = encrypted_password
            passwordHistory.save()

            # insert profile organization mapping in profileorganization table
            organization = request.POST.getlist('organization_name')
            print "##################"
            print organization
            for org in organization:
                profile_organization = ProfileOrganization(profile_id = profile.id, organization_id = int(org) )
                profile_organization.save()



            messages.success(request, '<i class="fa fa-check-circle"></i> New User has been registered successfully!',
                             extra_tags='alert-success crop-both-side')
            return HttpResponseRedirect('/usermodule/')

        # Invalid form or forms - mistakes or something else?
        # Print problems to the terminal.
        # They'll also be shown to the user.
        else:
            print user_form.errors, profile_form.errors
            # profile_form = UserProfileForm(admin_check=admin_check)

    # Not a HTTP POST, so we render our form using two ModelForm instances.
    # These forms will be blank, ready for user input.
    else:
        user_form = UserForm()
        # get request users org and the orgs he can see then pass it to model choice field



        profile_form = UserProfileForm(admin_check=admin_check)

    # Render the template depending on the context.
    return render_to_response(
        'usermodule/register.html',
        {'user_form': user_form, 'profile_form': profile_form, 'registered': registered, 'organization_list':organization_list},
        context)


def create_po_csv(request, username):

    user = get_object_or_404(User, username=username)
    # organization of user
    org_id_list = get_organization_by_user(user)
    # all user of those organization
    organizations = ProfileOrganization.objects.filter(organization_id__in=org_id_list)
    all_profiles_id = [ org.profile_id for org in organizations]
    # filtering users whose role is PO
    role = OrganizationRole.objects.filter(role ='PO')

    po_users = UserRoleMap.objects.filter(user_id__in = all_profiles_id , role = role)
    # po_profile_list = [po.user for po in po_users]
    po_name_list = [po.user.user.username for po in po_users]
    po_label_list = [po.user.user.first_name+' '+po.user.user.last_name for po in po_users]

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="po_list.csv"'

    writer = csv.writer(response)
    writer.writerow(['po_name', 'po_label'])

    for i in range(len(po_name_list)):
        writer.writerow([po_name_list[i], po_label_list[i]])
    return response


def upload_csv(request):
    data = {}


    # if not GET, then proceed
    if "POST" == request.method:
        csv_file = request.FILES["csv_file"]
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File is not CSV type')
            return HttpResponseRedirect("/usermodule/upload/csv")
        # if file is too large, return
        if csv_file.multiple_chunks():
            messages.error(request, "Uploaded file is too big (%.2f MB)." % (csv_file.size / (1000 * 1000),))
            return HttpResponseRedirect(reverse("usermodule:upload_csv"))

        file_data = csv_file.read().decode("utf-8")

        lines = file_data.split("\n")
        # loop over the lines and save them in db. If error , store as string and then display

        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="user_reject_list.csv"'
        writer = csv.writer(response)
        writer.writerow(str(lines[0]).split(",")+['Error'])

        print len(lines)
        for line in lines[1:]:

            fields = str(line).split(",")
            if len(fields)<10:
                return response
            submitted_data = {}
            submitted_data['username'] = str(fields[0])
            print fields[1]
            submitted_data['first_name'] = str(fields[1])
            submitted_data['last_name'] = str(fields[2])
            submitted_data['email'] = str(fields[3])
            submitted_data['password'] = str(fields[4])
            submitted_data['password_repeat'] = str(fields[5])
            submitted_data['country'] = str(fields[9])
            organization = str(fields[8])
            org = Organizations.objects.filter(organization = organization).first()
            if org is not None:
                submitted_data['organization_id'] = org.id
            submitted_data['admin'] = str(fields[6])
            submitted_data['employee_id'] = str(fields[7])
            submitted_data['position'] = str(fields[10])

            try:
                print "user creation started"
                user_form = UserForm(submitted_data)
                profile_form = UserProfileForm(submitted_data)
                if user_form.is_valid() and profile_form.is_valid():
                    user = user_form.save()
                    if submitted_data['admin'].lower() == 'false':
                        form_bool_value = False
                    else:
                        form_bool_value = True

                    # encrypted password is saved so that it can be saved in password history table
                    encrypted_password = make_password(user.password)
                    user.password = encrypted_password
                    user.save()
                    profile = profile_form.save(commit=False)
                    # profile.organisation_name = request.POST.get("organisation_name", "-1")
                    profile.user = user
                    expiry_months_delta = 3
                    # Date representing the next expiry date
                    next_expiry_date = (datetime.today() + timedelta(expiry_months_delta * 365 / 12))
                    profile.expired = next_expiry_date
                    profile.admin = form_bool_value

                    profile.save()

                    # kobo main/models/UserProfile
                    main_user_profile = UserProfile(user=user)
                    main_user_profile.save()

                    # Update our variable to tell the template registration was successful.
                    registered = True

                    # insert password into password history
                    passwordHistory = UserPasswordHistory(user_id=user.id, date=datetime.now())
                    passwordHistory.password = encrypted_password
                    passwordHistory.save()

                    print "user created"
                    print user_form
                else:

                    error_string = ','.join(user_form.error_class.as_text(v) for k, v in user_form.errors.items())

                    error_string += ','.join(profile_form.error_class.as_text(v) for k, v in profile_form.errors.items())
                    print error_string

                    writer.writerow(fields+[error_string])
            except Exception as e:

                print "checking"
                print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(e).__name__, e)

        return response
                # pass

    return render(request, "usermodule/user_creation.html", data)


def writedata(request):
    dbconnection = mongoconnection()
    db = dbconnection['tup']
    instance = db.instances
    print instance.find_one()

    query = 'select * from vwupazila'
    cursor = connection.cursor()
    cursor.execute(query)
    fetch_val = cursor.fetchall()
    col_names = [desc[0] for desc in cursor.description]
    cursor.close()
    data_list = []
    for each_val in fetch_val:
        data_list.append(list(each_val))
    wb = xlwt.Workbook()
    ws = wb.add_sheet("My Sheet", cell_overwrite_ok=True)
    print("writing data in excel file\n")
    for j, col in enumerate(col_names):
                #writing column name
        ws.write(0, j, col)
    countLine=1
    for rowdata in data_list:
        colLine=0
        for row in rowdata:
            ws.write(countLine, colLine, row)
            colLine+=1
        countLine+=1
    wb.save("data2.xls")
